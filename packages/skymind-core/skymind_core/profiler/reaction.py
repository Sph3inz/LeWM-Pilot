"""Failure reaction timer state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ReactionPhase(str, Enum):
    IDLE = "idle"
    PENDING = "pending"
    MEASURED = "measured"


@dataclass
class ReactionTimer:
    phase: ReactionPhase = ReactionPhase.IDLE
    failure_time_s: float = 0.0
    baseline_throttle: float = 0.0
    baseline_heading_deg: float = 0.0
    reaction_time_s: float | None = None
    feather_pressed: bool = field(default=False)

    def on_failure(self, sim_time_s: float, throttle: float, heading_deg: float) -> None:
        self.phase = ReactionPhase.PENDING
        self.failure_time_s = sim_time_s
        self.baseline_throttle = throttle
        self.baseline_heading_deg = heading_deg
        self.reaction_time_s = None
        self.feather_pressed = False

    def observe(
        self,
        sim_time_s: float,
        throttle: float,
        heading_deg: float,
        *,
        feather: bool = False,
    ) -> None:
        if self.phase != ReactionPhase.PENDING:
            return
        heading_delta = abs((heading_deg - self.baseline_heading_deg + 180) % 360 - 180)
        throttle_delta = abs(throttle - self.baseline_throttle)
        if throttle_delta > 0.1 or feather or heading_delta > 5.0:
            self.reaction_time_s = max(0.0, sim_time_s - self.failure_time_s)
            self.phase = ReactionPhase.MEASURED

    def consume_measurement(self) -> float | None:
        if self.phase != ReactionPhase.MEASURED:
            return self.reaction_time_s if self.phase == ReactionPhase.IDLE else None
        rt = self.reaction_time_s
        self.phase = ReactionPhase.IDLE
        self.reaction_time_s = rt
        return rt

    def reset_to_idle(self) -> None:
        if self.phase == ReactionPhase.MEASURED:
            self.phase = ReactionPhase.IDLE
