"""ScenarioOrchestrator — timeline loading, adaptation merge, tick commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from skymind_core.models import AdaptationSignal, SimulatorCommand
from skymind_core.orchestrator.env_events import ENV_EVENT_TYPES, merge_environment
from skymind_core.orchestrator.scenario import ScenarioTimeline

_FAILURE_ID_MAP = {
    "engine_failure": "engine_failure",
    "attitude_failure": "attitude_failure",
    "comms_failure": "comms_failure",
    "hydraulic_leak": "hydraulic_leak",
}


def _default_schema_path() -> Path:
    return _repo_root() / "schemas" / "scenario.schema.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_profiler_config() -> dict[str, Any]:
    path = _repo_root() / "configs" / "profiler.yaml"
    if not path.is_file():
        return {"struggling_threshold": 0.4, "min_failure_spacing_s": 10}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class ScenarioOrchestrator:
    """Load scenario JSON, merge profiler adaptations, emit simulator commands."""

    def __init__(
        self,
        schema_path: str | Path | None = None,
        profiler_config_path: str | Path | None = None,
    ) -> None:
        schema_path = Path(schema_path) if schema_path else _default_schema_path()
        with schema_path.open(encoding="utf-8") as fh:
            self._schema = json.load(fh)
        self._profiler_cfg = _default_profiler_config()
        if profiler_config_path:
            with Path(profiler_config_path).open(encoding="utf-8") as fh:
                self._profiler_cfg.update(yaml.safe_load(fh) or {})
        self._timeline: ScenarioTimeline | None = None
        self._hold_injections = False
        self._profiler_score = 1.0
        self._gust_scale_factor = 1.0

    def load_scenario(self, doc: dict) -> ScenarioTimeline:
        jsonschema.validate(doc, self._schema)
        self._timeline = ScenarioTimeline.from_doc(doc)
        self._hold_injections = False
        self._profiler_score = 1.0
        self._gust_scale_factor = 1.0
        return self._timeline

    def set_profiler_score(self, score: float) -> None:
        self._profiler_score = score

    def apply_adaptation(self, signal: AdaptationSignal) -> None:
        if self._timeline is None:
            return
        self._hold_injections = signal.hold_injections
        self._gust_scale_factor = signal.gust_scale_factor
        if signal.delay_next_failure_s > 0:
            self._apply_to_next_failure(delay_s=signal.delay_next_failure_s)
        if signal.advance_next_failure_s > 0:
            self._apply_to_next_failure(advance_s=signal.advance_next_failure_s)

    def tick(self, sim_time_s: float) -> list[SimulatorCommand]:
        if self._timeline is None:
            return []
        commands: list[SimulatorCommand] = []
        struggling = float(self._profiler_cfg.get("struggling_threshold", 0.4))
        min_spacing = float(self._profiler_cfg.get("min_failure_spacing_s", 10))

        for event in self._timeline.events:
            if event.fired:
                continue
            if event.is_failure and self._hold_injections and self._profiler_score < struggling:
                continue
            if sim_time_s < event.effective_time_s:
                continue
            if event.is_failure:
                prev_time = self._last_fired_time(event)
                if prev_time is not None and event.effective_time_s - prev_time < min_spacing:
                    continue
            cmd = self._build_command(event)
            if cmd is not None:
                commands.append(cmd)
            event.fired = True
        return commands

    def get_timeline_view(self) -> dict:
        if self._timeline is None:
            return {"events": []}
        return {
            "scenario_id": self._timeline.scenario_id,
            "events": [
                {
                    "type": e.type,
                    "time_offset_s": e.time_offset_s,
                    "effective_time_s": e.effective_time_s,
                    "fired": e.fired,
                    "delay_s": e.delay_s,
                    "advance_s": e.advance_s,
                }
                for e in self._timeline.events
            ],
        }

    def _apply_to_next_failure(self, *, delay_s: float = 0.0, advance_s: float = 0.0) -> None:
        assert self._timeline is not None
        for event in self._timeline.events:
            if event.fired or not event.is_failure:
                continue
            if delay_s:
                event.delay_s += delay_s
            if advance_s:
                event.advance_s += advance_s
            break

    def _last_fired_time(self, current: Any) -> float | None:
        assert self._timeline is not None
        fired_times = [
            e.effective_time_s for e in self._timeline.events if e.fired and e is not current
        ]
        return max(fired_times) if fired_times else None

    def _build_command(self, event: Any) -> SimulatorCommand | None:
        assert self._timeline is not None
        if event.type in _FAILURE_ID_MAP:
            return SimulatorCommand(
                kind="failure",
                params={
                    "failure_id": _FAILURE_ID_MAP[event.type],
                    **event.params,
                },
            )
        if event.type in ENV_EVENT_TYPES:
            env = merge_environment(self._timeline.environment_initial, event.type, event.params)
            gust = env.gust_factor * self._gust_scale_factor
            env = env.model_copy(update={"gust_factor": gust})
            return SimulatorCommand(
                kind="environment",
                params={"environment": env.model_dump(), **{k: v for k, v in event.params.items() if k not in env.model_dump()}},
            )
        return None
