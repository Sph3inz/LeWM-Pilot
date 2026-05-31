"""SkillProfiler — performance scoring and adaptation signals."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from skymind_core.models import AdaptationSignal, ProfilerState
from skymind_core.profiler.reaction import ReactionTimer
from skymind_sim.models import TelemetrySnapshot

_DEFAULT_CONFIG: dict[str, Any] = {
    "max_allowed_airspeed_error_kt": 15,
    "max_allowed_altitude_error_ft": 200,
    "max_allowed_reaction_time_s": 8,
    "update_interval_s": 5,
    "struggling_threshold": 0.4,
    "excellent_threshold": 0.7,
    "delay_on_struggling_s": 30,
    "advance_on_excellent_s": 15,
    "min_failure_spacing_s": 10,
    "gust_reduce_factor": 0.8,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_profiler_config(config_path: str | Path | None) -> dict[str, Any]:
    if config_path is None:
        config_path = _repo_root() / "configs" / "profiler.yaml"
    path = Path(config_path)
    if not path.is_file():
        return dict(_DEFAULT_CONFIG)
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    merged = dict(_DEFAULT_CONFIG)
    merged.update(data)
    return merged


class SkillProfiler:
    """Compute pilot performance score and emit timeline adaptation signals."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._cfg = _load_profiler_config(config_path)
        self._score = 0.5
        self._last_update_s = -1e9
        self._state = ProfilerState(
            score=0.5,
            delta_v_kt=0.0,
            delta_h_ft=0.0,
            reaction_time_s=None,
            band="moderate",
        )
        self._reaction = ReactionTimer()
        self._last_telemetry = TelemetrySnapshot()

    def update(self, telemetry: TelemetrySnapshot, cmd_target: dict | None = None) -> ProfilerState:
        self._last_telemetry = telemetry
        cmd_target = cmd_target or {}
        self._reaction.observe(
            telemetry.sim_time_s,
            telemetry.throttle,
            telemetry.heading_deg,
            feather=bool(cmd_target.get("feather_pressed", False)),
        )

        interval = float(self._cfg["update_interval_s"])
        if telemetry.sim_time_s - self._last_update_s < interval and self._last_update_s > -1e8:
            return self._state

        self._last_update_s = telemetry.sim_time_s
        ias_cmd = float(cmd_target.get("ias_cmd", telemetry.ias_kt))
        alt_cmd = float(cmd_target.get("alt_cmd", telemetry.alt_ft))

        delta_v = abs(ias_cmd - telemetry.ias_kt)
        delta_h = abs(alt_cmd - telemetry.alt_ft)
        max_v = float(self._cfg["max_allowed_airspeed_error_kt"])
        max_h = float(self._cfg["max_allowed_altitude_error_ft"])
        max_rt = float(self._cfg["max_allowed_reaction_time_s"])

        delta_v_norm = min(delta_v / max(max_v, 1e-6), 1.0)
        delta_h_norm = min(delta_h / max(max_h, 1e-6), 1.0)

        reaction_time = self._reaction.reaction_time_s
        if self._reaction.phase.value == "measured":
            reaction_time = self._reaction.consume_measurement()
        reaction_norm = (
            min(reaction_time / max(max_rt, 1e-6), 1.0) if reaction_time is not None else 0.0
        )

        perf_v = 1.0 - delta_v_norm
        perf_h = 1.0 - delta_h_norm
        perf_r = 1.0 - reaction_norm
        score = 0.4 * perf_v + 0.4 * perf_h + 0.2 * perf_r
        self._score = score

        band = self._band_for_score(score)
        self._state = ProfilerState(
            score=score,
            delta_v_kt=delta_v,
            delta_h_ft=delta_h,
            reaction_time_s=reaction_time,
            band=band,
        )
        return self._state

    def get_score(self) -> float:
        return self._score

    def on_failure_injected(self, failure_id: str, sim_time_s: float) -> None:
        _ = failure_id
        t = self._last_telemetry
        self._reaction.on_failure(
            sim_time_s if sim_time_s >= 0 else t.sim_time_s,
            t.throttle,
            t.heading_deg,
        )

    def get_adaptation_signal(self) -> AdaptationSignal:
        struggling = float(self._cfg["struggling_threshold"])
        excellent = float(self._cfg["excellent_threshold"])
        if self._score < struggling:
            return AdaptationSignal(
                delay_next_failure_s=float(self._cfg["delay_on_struggling_s"]),
                hold_injections=True,
                gust_scale_factor=float(self._cfg["gust_reduce_factor"]),
            )
        if self._score >= excellent:
            return AdaptationSignal(
                advance_next_failure_s=float(self._cfg["advance_on_excellent_s"]),
            )
        return AdaptationSignal()

    def _band_for_score(self, score: float) -> Literal["struggling", "moderate", "excellent"]:
        if score < float(self._cfg["struggling_threshold"]):
            return "struggling"
        if score >= float(self._cfg["excellent_threshold"]):
            return "excellent"
        return "moderate"
