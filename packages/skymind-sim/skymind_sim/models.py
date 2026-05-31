"""Pydantic models for simulator I/O."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EnvironmentState(BaseModel):
    crosswind_kt: float = 0.0
    gust_factor: float = 0.0
    turbulence_index: float = 0.0
    visibility_sm: float = 10.0
    ceiling_ft: float = 10000.0


class ScenarioConfig(BaseModel):
    aircraft_id: Literal["c172", "t6"] = "c172"
    initial_heading_deg: float = 270.0
    initial_alt_ft: float = 5000.0
    episode_time_s: float = 600.0
    environment: EnvironmentState = Field(default_factory=EnvironmentState)


class TelemetrySnapshot(BaseModel):
    sim_time_s: float = 0.0
    aircraft_id: str = "c172"
    lat_deg: float | None = None
    lon_deg: float | None = None
    pos_x_m: float = 0.0
    pos_y_m: float = 0.0
    alt_ft: float = 0.0
    ias_kt: float = 0.0
    heading_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    yaw_deg: float = 0.0
    vs_fpm: float = 0.0
    throttle: float = 0.0
    elevator: float = 0.0
    aileron: float = 0.0
    rudder: float = 0.0
    engine_n1: float | None = None
    engine_n2: float | None = None
    on_ground: bool = False
    failure_engine: bool = False
    failure_attitude: bool = False
    failure_comms: bool = False
    failure_hydraulic: bool = False
    environment: EnvironmentState = Field(default_factory=EnvironmentState)

    def to_frame_dict(self, action_vector: list[float] | None = None) -> dict:
        from skymind_data.schema import ACTION_DIM

        d = self.model_dump()
        d["action_vector"] = action_vector or ([0.0] * ACTION_DIM)
        return d
