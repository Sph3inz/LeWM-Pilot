"""Load and query the maneuver catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from skymind_sim.models import EnvironmentState


class ManeuverPhase(BaseModel):
    until_s: float
    target_alt_ft: float
    target_heading_deg: float
    target_ias_kt: float = 100.0
    target_vs_fpm: float = 0.0
    heading_sweep_deg: float = 0.0
    sweep_period_s: float = 120.0


class ManeuverFailure(BaseModel):
    failure_id: str
    at_s: float


class ManeuverDefinition(BaseModel):
    maneuver_id: str = ""
    duration_s: float
    initial_alt_ft: float = 3000.0
    initial_heading_deg: float = 270.0
    phases: list[ManeuverPhase]
    failures: list[ManeuverFailure] = Field(default_factory=list)
    environment: EnvironmentState = Field(default_factory=EnvironmentState)


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        path = Path(__file__).resolve().parents[3] / "configs" / "maneuver_catalog.yaml"
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data


def get_maneuver_ids(catalog_name: str, path: str | Path | None = None) -> list[str]:
    data = load_catalog(path)
    ids = data.get("catalogs", {}).get(catalog_name)
    if not ids:
        raise ValueError(f"Unknown catalog preset: {catalog_name}")
    return list(ids)


def get_maneuver(maneuver_id: str, path: str | Path | None = None) -> ManeuverDefinition:
    data = load_catalog(path)
    raw = data.get("maneuvers", {}).get(maneuver_id)
    if raw is None:
        raise ValueError(f"Unknown maneuver: {maneuver_id}")
    return ManeuverDefinition(maneuver_id=maneuver_id, **raw)


def active_phase(maneuver: ManeuverDefinition, sim_time_s: float) -> ManeuverPhase:
    for phase in maneuver.phases:
        if sim_time_s <= phase.until_s:
            return phase
    return maneuver.phases[-1]


def phase_heading(phase: ManeuverPhase, sim_time_s: float, base_heading: float) -> float:
    if phase.heading_sweep_deg <= 0:
        return phase.target_heading_deg
    import math

    period = max(phase.sweep_period_s, 1.0)
    offset = phase.heading_sweep_deg * math.sin(2 * math.pi * sim_time_s / period)
    return (base_heading + offset) % 360.0
