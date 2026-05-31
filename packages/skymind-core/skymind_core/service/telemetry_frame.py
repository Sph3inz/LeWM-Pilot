"""TelemetryFrame DTO for WebSocket broadcast."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from skymind_core.service.adaptation_log import AdaptationLogEntry
from skymind_sim.models import TelemetrySnapshot


class TelemetryFrame(BaseModel):
    type: Literal["telemetry"] = "telemetry"
    session_id: str
    timestamp_ns: int
    sim_time_s: float
    aircraft_id: str
    position: dict[str, float]
    lat_deg: float | None = None
    lon_deg: float | None = None
    alt_ft: float
    ias_kt: float
    heading_deg: float
    pitch_deg: float
    roll_deg: float
    vs_fpm: float
    pilot_score: float
    score_band: str
    active_failures: list[str] = Field(default_factory=list)
    scenario_events_pending: int = 0
    adaptation_log: list[AdaptationLogEntry] = Field(default_factory=list)
    timeline: dict = Field(default_factory=dict)
    environment: dict = Field(default_factory=dict)


def build_telemetry_frame(
    *,
    session_id: str,
    telemetry: TelemetrySnapshot,
    pilot_score: float,
    score_band: str,
    adaptation_log: list[dict],
    timeline_view: dict,
    timestamp_ns: int | None = None,
) -> TelemetryFrame:
    import time

    ts = timestamp_ns if timestamp_ns is not None else time.time_ns()
    failures: list[str] = []
    if telemetry.failure_engine:
        failures.append("engine_failure")
    if telemetry.failure_attitude:
        failures.append("attitude_failure")
    if telemetry.failure_comms:
        failures.append("comms_failure")
    if telemetry.failure_hydraulic:
        failures.append("hydraulic_leak")

    pending = sum(1 for e in timeline_view.get("events", []) if not e.get("fired", False))
    log_entries = [AdaptationLogEntry(**e) for e in adaptation_log[-20:]]

    return TelemetryFrame(
        session_id=session_id,
        timestamp_ns=ts,
        sim_time_s=telemetry.sim_time_s,
        aircraft_id=telemetry.aircraft_id,
        position={"x_m": telemetry.pos_x_m, "y_m": telemetry.pos_y_m},
        lat_deg=telemetry.lat_deg,
        lon_deg=telemetry.lon_deg,
        alt_ft=telemetry.alt_ft,
        ias_kt=telemetry.ias_kt,
        heading_deg=telemetry.heading_deg,
        pitch_deg=telemetry.pitch_deg,
        roll_deg=telemetry.roll_deg,
        vs_fpm=telemetry.vs_fpm,
        pilot_score=pilot_score,
        score_band=score_band,
        active_failures=failures,
        scenario_events_pending=pending,
        adaptation_log=log_entries,
        timeline=timeline_view,
        environment=telemetry.environment.model_dump(),
    )
