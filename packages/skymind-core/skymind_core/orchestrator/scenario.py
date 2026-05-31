"""Scenario timeline models."""

from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, Field

FAILURE_EVENT_TYPES = frozenset(
    {"engine_failure", "attitude_failure", "comms_failure", "hydraulic_leak"}
)
from skymind_core.orchestrator.env_events import ENV_EVENT_TYPES


class ScenarioEvent(BaseModel):
    time_offset_s: float
    type: str
    params: dict = Field(default_factory=dict)
    fired: bool = False
    delay_s: float = 0.0
    advance_s: float = 0.0

    @property
    def effective_time_s(self) -> float:
        return max(0.0, self.time_offset_s + self.delay_s - self.advance_s)

    @property
    def is_failure(self) -> bool:
        return self.type in FAILURE_EVENT_TYPES


class ScenarioTimeline(BaseModel):
    scenario_id: str = ""
    aircraft_id: str = "c172"
    description: str = ""
    environment_initial: dict = Field(default_factory=dict)
    events: list[ScenarioEvent] = Field(default_factory=list)
    baseline_events: list[ScenarioEvent] = Field(default_factory=list)

    def reset_fired(self) -> None:
        for event, baseline in zip(self.events, self.baseline_events, strict=True):
            event.fired = baseline.fired
            event.delay_s = baseline.delay_s
            event.advance_s = baseline.advance_s

    @classmethod
    def from_doc(cls, doc: dict) -> ScenarioTimeline:
        events = [
            ScenarioEvent(
                time_offset_s=float(e["time_offset_s"]),
                type=str(e["type"]),
                params=dict(e.get("params") or {}),
            )
            for e in doc.get("events") or []
        ]
        baseline = deepcopy(events)
        return cls(
            scenario_id=str(doc.get("scenario_id", "")),
            aircraft_id=str(doc.get("aircraft_id", "c172")),
            description=str(doc.get("description", "")),
            environment_initial=dict(doc.get("environment_initial") or {}),
            events=events,
            baseline_events=baseline,
        )
