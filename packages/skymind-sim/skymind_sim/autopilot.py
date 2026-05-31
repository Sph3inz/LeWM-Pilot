"""Minimal PID autopilot for data collection."""

from __future__ import annotations

from skymind_data.schema import ACTION_DIM
from skymind_sim.models import TelemetrySnapshot


class HoldHeadingAltitudePID:
    """Hold target heading, altitude, and IAS via surface controls + throttle."""

    def __init__(
        self,
        target_heading_deg: float = 270.0,
        target_alt_ft: float = 5000.0,
        target_ias_kt: float = 100.0,
        target_vs_fpm: float = 0.0,
    ) -> None:
        self.target_heading_deg = target_heading_deg
        self.target_alt_ft = target_alt_ft
        self.target_ias_kt = target_ias_kt
        self.target_vs_fpm = target_vs_fpm
        self._integral_alt = 0.0
        self._integral_ias = 0.0
        self._engine_out = False

    def reset(self) -> None:
        self._integral_alt = 0.0
        self._integral_ias = 0.0

    def set_engine_out(self, active: bool) -> None:
        self._engine_out = active
        if active:
            self.target_ias_kt = min(self.target_ias_kt, 65.0)

    def compute(self, telemetry: TelemetrySnapshot) -> list[float]:
        heading_err = _angle_diff(self.target_heading_deg, telemetry.heading_deg)
        alt_err = self.target_alt_ft - telemetry.alt_ft
        vs_err = self.target_vs_fpm - telemetry.vs_fpm

        self._integral_alt = _clamp(self._integral_alt + alt_err * 0.005, -200, 200)

        # Gentle gains to stay within jsbgym altitude deviation limits
        aileron = _clamp(0.015 * heading_err, -0.35, 0.35)
        elevator = _clamp(
            -0.0008 * alt_err - 0.00003 * self._integral_alt - 0.0002 * vs_err,
            -0.25,
            0.25,
        )
        rudder = _clamp(0.008 * heading_err, -0.2, 0.2)

        if self._engine_out:
            throttle = 0.0
            feather = 1.0
            elevator = _clamp(elevator - 0.05, -0.3, 0.1)
        else:
            ias_err = self.target_ias_kt - telemetry.ias_kt
            self._integral_ias = _clamp(self._integral_ias + ias_err * 0.01, -50, 50)
            throttle = _clamp(0.65 + 0.008 * ias_err + 0.0005 * self._integral_ias, 0.4, 0.95)
            feather = 0.0

        action = [throttle, elevator, aileron, rudder, feather, 0.0, 0.0, 0.0]
        return action[:ACTION_DIM]


def _angle_diff(target: float, current: float) -> float:
    return (target - current + 180.0) % 360.0 - 180.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
