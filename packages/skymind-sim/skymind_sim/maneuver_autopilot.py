"""Maneuver-aware autopilot for catalog data collection."""

from __future__ import annotations

from skymind_sim.autopilot import HoldHeadingAltitudePID
from skymind_sim.maneuver_catalog import (
    ManeuverDefinition,
    active_phase,
    phase_heading,
)
from skymind_sim.models import TelemetrySnapshot


class ManeuverAutopilot:
    """Select PID targets from maneuver phase definitions."""

    def __init__(self, maneuver: ManeuverDefinition) -> None:
        self.maneuver = maneuver
        self._pid = HoldHeadingAltitudePID(
            target_heading_deg=maneuver.initial_heading_deg,
            target_alt_ft=maneuver.initial_alt_ft,
        )
        self._engine_out = False
        self._session_sim_time_s = 0.0

    @property
    def engine_out(self) -> bool:
        return self._engine_out

    def reset(self) -> None:
        self._pid.reset()
        self._engine_out = False

    def set_engine_out(self, active: bool) -> None:
        self._engine_out = active
        self._pid.set_engine_out(active)

    def set_session_sim_time(self, sim_time_s: float) -> None:
        self._session_sim_time_s = sim_time_s

    def advance_sim_time(self, delta_s: float) -> None:
        self._session_sim_time_s += max(0.0, delta_s)

    @property
    def session_sim_time_s(self) -> float:
        return self._session_sim_time_s

    def compute(self, telemetry: TelemetrySnapshot) -> list[float]:
        phase = active_phase(self.maneuver, self._session_sim_time_s)
        self._pid.target_alt_ft = phase.target_alt_ft
        self._pid.target_ias_kt = phase.target_ias_kt
        self._pid.target_vs_fpm = phase.target_vs_fpm
        self._pid.target_heading_deg = phase_heading(
            phase,
            self._session_sim_time_s,
            phase.target_heading_deg,
        )
        if self._engine_out:
            self._pid.set_engine_out(True)
        return self._pid.compute(telemetry)
