"""Adaptation log ring buffer for WebSocket frames."""

from __future__ import annotations

from collections import deque

from pydantic import BaseModel

from skymind_core.models import AdaptationSignal, EnvironmentDelta, ProfilerState


class AdaptationLogEntry(BaseModel):
    sim_time_s: float
    message: str
    source: str  # profiler | planner | llm | instructor


class AdaptationLog:
    """Rolling adaptation event log (max 100 entries)."""

    def __init__(self, max_entries: int = 100) -> None:
        self._entries: deque[AdaptationLogEntry] = deque(maxlen=max_entries)

    def add(self, sim_time_s: float, message: str, source: str) -> None:
        self._entries.append(
            AdaptationLogEntry(sim_time_s=sim_time_s, message=message, source=source)
        )

    def log_profiler(self, sim_time_s: float, state: ProfilerState, signal: AdaptationSignal) -> None:
        if signal.delay_next_failure_s > 0:
            self.add(
                sim_time_s,
                f"Score {state.score:.2f} ({state.band}) → delaying next failure +{signal.delay_next_failure_s:.0f}s",
                "profiler",
            )
        elif signal.advance_next_failure_s > 0:
            self.add(
                sim_time_s,
                f"Score {state.score:.2f} ({state.band}) → advancing next failure {signal.advance_next_failure_s:.0f}s",
                "profiler",
            )
        elif signal.hold_injections:
            self.add(sim_time_s, f"Score {state.score:.2f} → holding failure injections", "profiler")
        else:
            self.add(sim_time_s, f"Score {state.score:.2f} ({state.band})", "profiler")

    def log_planner(self, sim_time_s: float, target: float, delta: EnvironmentDelta) -> None:
        self.add(
            sim_time_s,
            (
                f"Planner target {target:.2f}: "
                f"Δwind {delta.crosswind_delta_kt:+.1f} kt, "
                f"Δgust {delta.gust_factor_delta:+.2f}, "
                f"Δturb {delta.turbulence_delta:+.2f}, "
                f"Δvis {delta.visibility_delta_sm:+.1f} sm, "
                f"Δceil {delta.ceiling_delta_ft:+.0f} ft"
            ),
            "planner",
        )

    def log_llm(self, sim_time_s: float, scenario_id: str) -> None:
        self.add(sim_time_s, f"Loaded scenario '{scenario_id}' from LLM", "llm")

    def log_instructor(self, sim_time_s: float, message: str) -> None:
        self.add(sim_time_s, message, "instructor")

    def snapshot(self) -> list[dict]:
        return [e.model_dump() for e in self._entries]
