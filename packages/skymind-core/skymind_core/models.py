"""Shared DTOs for profiler, orchestrator, and planner."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AdaptationSignal(BaseModel):
    delay_next_failure_s: float = 0.0
    advance_next_failure_s: float = 0.0
    hold_injections: bool = False
    gust_scale_factor: float = 1.0


class ProfilerState(BaseModel):
    score: float
    delta_v_kt: float
    delta_h_ft: float
    reaction_time_s: float | None
    band: Literal["struggling", "moderate", "excellent"]


class EnvironmentDelta(BaseModel):
    crosswind_delta_kt: float = 0.0
    gust_factor_delta: float = 0.0
    turbulence_delta: float = 0.0
    visibility_delta_sm: float = 0.0
    ceiling_delta_ft: float = 0.0


class SimulatorCommand(BaseModel):
    kind: Literal["failure", "environment", "reset"]
    params: dict = Field(default_factory=dict)
