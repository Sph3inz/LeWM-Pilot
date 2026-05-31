"""AutopilotCollector — run maneuver catalog and produce collection manifest."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from skymind_data.recorder import SessionRecorder
from skymind_data.schema import SCHEMA_VERSION
from skymind_sim.maneuver_autopilot import ManeuverAutopilot
from skymind_sim.maneuver_catalog import get_maneuver, get_maneuver_ids
from skymind_sim.models import ScenarioConfig


class SimAdapterProtocol(Protocol):
    def reset(self, config: ScenarioConfig, *, new_session: bool = True) -> str: ...
    def reset_episode(self, config: ScenarioConfig | None = None) -> None: ...
    def step(self, action: list[float]) -> tuple[Any, bool]: ...
    def get_telemetry(self) -> Any: ...
    def inject_failure(self, failure_id: str, params: dict | None = None) -> None: ...
    def set_environment(self, env: Any) -> None: ...
    def close(self) -> None: ...


class AutopilotCollector:
    """Run weighted round-robin maneuvers until target sim hours collected."""

    def __init__(
        self,
        adapter: SimAdapterProtocol,
        lance_root: str | Path = "data/lance/sessions",
        sim_hz: float = 10.0,
        real_time: bool = True,
    ) -> None:
        self.adapter = adapter
        self.lance_root = Path(lance_root)
        self.sim_hz = sim_hz
        self.real_time = real_time
        self.dt = 1.0 / sim_hz

    def run(
        self,
        hours: float,
        catalog: str = "full",
        aircraft_id: str = "c172",
        catalog_path: str | Path | None = None,
        collection_run_id: str | None = None,
        resume: bool = False,
        manifest_name: str = "collection_manifest.json",
    ) -> dict[str, Any]:
        target_seconds = hours * 3600.0
        target_frames = int(target_seconds * self.sim_hz)
        maneuver_ids = get_maneuver_ids(catalog, catalog_path)
        run_id = collection_run_id or str(uuid.uuid4())
        manifest_path = self.lance_root.parent / manifest_name

        session_ids: list[str] = []
        maneuver_counts: dict[str, int] = {m: 0 for m in maneuver_ids}
        failure_injections = 0
        total_frames = 0
        environment_presets: set[str] = set()
        started_at = datetime.now(timezone.utc).isoformat()
        mi = 0
        last_progress_hr = 0.0

        if resume and manifest_path.exists():
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if existing.get("collection_run_id") == run_id:
                session_ids = list(existing.get("session_ids", []))
                maneuver_counts.update(existing.get("maneuver_counts", {}))
                failure_injections = int(existing.get("failure_injections", 0))
                total_frames = int(existing.get("total_frames", 0))

        self.lance_root.mkdir(parents=True, exist_ok=True)
        free_gb = shutil.disk_usage(self.lance_root).free / (1024**3)
        if free_gb < 1.5:
            print(f"WARNING: only {free_gb:.1f} GB free on data volume")

        while total_frames < target_frames:
            maneuver_id = maneuver_ids[mi % len(maneuver_ids)]
            mi += 1
            maneuver = get_maneuver(maneuver_id, catalog_path)
            remaining_s = target_seconds - total_frames / self.sim_hz
            if remaining_s <= 0:
                break
            session_duration_s = min(maneuver.duration_s, remaining_s)

            scenario = ScenarioConfig(
                aircraft_id=aircraft_id,  # type: ignore[arg-type]
                initial_alt_ft=maneuver.initial_alt_ft,
                initial_heading_deg=maneuver.initial_heading_deg,
                episode_time_s=session_duration_s + 120,
                environment=maneuver.environment,
            )

            autopilot = ManeuverAutopilot(maneuver)
            recorder = SessionRecorder(lance_root=self.lance_root)
            session_id = self.adapter.reset(scenario)
            recorder.start_session(
                {
                    "session_id": session_id,
                    "aircraft_id": aircraft_id,
                    "maneuver_id": maneuver_id,
                    "collection_run_id": run_id,
                    "environment": maneuver.environment.model_dump(),
                }
            )

            env_key = _environment_key(maneuver.environment.model_dump())
            environment_presets.add(env_key)

            steps = max(1, int(session_duration_s * self.sim_hz))
            failures_applied: set[str] = set()
            session_frames = 0

            for step_i in range(steps):
                maneuver_sim_time_s = step_i * self.dt
                autopilot.set_session_sim_time(maneuver_sim_time_s)

                for fail in maneuver.failures:
                    key = f"{fail.failure_id}@{fail.at_s}"
                    if key not in failures_applied and maneuver_sim_time_s >= fail.at_s:
                        self.adapter.inject_failure(fail.failure_id)
                        if fail.failure_id == "engine_failure":
                            autopilot.set_engine_out(True)
                        failures_applied.add(key)
                        failure_injections += 1

                telem = self.adapter.get_telemetry()
                action = autopilot.compute(telem)
                telem, done = self.adapter.step(action)
                row = telem.to_frame_dict(action_vector=action)
                row["sim_time_s"] = total_frames / self.sim_hz + self.dt
                row["timestamp_ns"] = time.time_ns()
                recorder.append_frame(row)
                total_frames += 1
                session_frames += 1

                total_hr = total_frames / self.sim_hz / 3600.0
                if total_hr - last_progress_hr >= 1.0 / 6.0:
                    last_progress_hr = total_hr
                    print(
                        f"  progress: {total_hr:.2f}/{hours:.2f} hr "
                        f"maneuver={maneuver_id} frames={total_frames}"
                    )

                if done:
                    engine_was_out = autopilot.engine_out
                    autopilot.reset()
                    if engine_was_out:
                        autopilot.set_engine_out(True)
                    self.adapter.reset_episode(scenario)

                if self.real_time:
                    time.sleep(self.dt)

            recorder.finalize_session()
            session_ids.append(session_id)
            maneuver_counts[maneuver_id] = maneuver_counts.get(maneuver_id, 0) + 1
            print(
                f"Maneuver {maneuver_id} done: {session_frames} frames "
                f"({total_frames/self.sim_hz/3600:.2f}/{hours:.2f} hr total)"
            )

        total_hours = total_frames / self.sim_hz / 3600.0
        ended_at = datetime.now(timezone.utc).isoformat()
        checksum = _checksum_sessions(self.lance_root, session_ids)
        manifest: dict[str, Any] = {
            "manifest_version": "1",
            "collection_run_id": run_id,
            "aircraft_id": aircraft_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "total_hours": round(total_hours, 3),
            "total_frames": total_frames,
            "session_ids": session_ids,
            "maneuver_counts": maneuver_counts,
            "failure_injections": failure_injections,
            "environment_presets": sorted(environment_presets),
            "lance_uri": str(self.lance_root),
            "schema_version": SCHEMA_VERSION,
            "checksum_sha256": checksum,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest


def _environment_key(env: dict[str, Any]) -> str:
    return (
        f"vis={env.get('visibility_sm')} ceil={env.get('ceiling_ft')} "
        f"xwind={env.get('crosswind_kt')} turb={env.get('turbulence_index')}"
    )


def _checksum_sessions(lance_root: Path, session_ids: list[str]) -> str:
    h = hashlib.sha256()
    for sid in sorted(session_ids):
        parquet = lance_root / sid / "frames.parquet"
        if parquet.exists():
            h.update(parquet.read_bytes())
    return h.hexdigest()
