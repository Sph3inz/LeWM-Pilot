"""Environment event presets and merge helpers for scenario timeline."""

from __future__ import annotations

from skymind_sim.models import EnvironmentState

ENV_EVENT_TYPES = frozenset(
    {
        "weather_imc",
        "weather_ifr",
        "weather_mvfr",
        "weather_vfr",
        "environment_change",
        "turbulence_burst",
        "wind_increase",
        "phase_change",
    }
)

WEATHER_PRESETS: dict[str, dict[str, float]] = {
    "weather_imc": {"visibility_sm": 0.5, "ceiling_ft": 200},
    "weather_ifr": {"visibility_sm": 1.0, "ceiling_ft": 500},
    "weather_mvfr": {"visibility_sm": 3.0, "ceiling_ft": 1500},
    "weather_vfr": {"visibility_sm": 10.0, "ceiling_ft": 12000},
    "turbulence_burst": {"turbulence_index": 0.4, "gust_factor": 0.3},
    "wind_increase": {"crosswind_kt": 15.0, "gust_factor": 0.25},
}

_ENV_KEYS = frozenset(
    {"crosswind_kt", "gust_factor", "turbulence_index", "visibility_sm", "ceiling_ft"}
)


def merge_environment(initial: dict, event_type: str, params: dict) -> EnvironmentState:
    """Build EnvironmentState from scenario initial + event preset + params."""
    merged = dict(initial or {})
    preset = WEATHER_PRESETS.get(event_type, {})
    merged.update(preset)
    for key, value in (params or {}).items():
        if key in _ENV_KEYS:
            merged[key] = value
    return EnvironmentState(
        crosswind_kt=float(merged.get("crosswind_kt", 0.0)),
        gust_factor=float(merged.get("gust_factor", 0.0)),
        turbulence_index=float(merged.get("turbulence_index", 0.0)),
        visibility_sm=float(merged.get("visibility_sm", 10.0)),
        ceiling_ft=float(merged.get("ceiling_ft", 10000.0)),
    )
