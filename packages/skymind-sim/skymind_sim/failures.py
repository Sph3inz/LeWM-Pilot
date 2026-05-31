"""JSBSim failure injection helpers."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

ENGINE_PATHS = (
    "propulsion/engine[0]/set-running",
    "propulsion/set-running",
    "propulsion/engine/set-running",
)

N1_PATHS = (
    "propulsion/engine[0]/n1",
    "propulsion/engine/n1",
    "propulsion/engine[0]/n2",
)


def apply_engine_failure(sim: Any) -> bool:
    """Cut engine power via JSBSim property manager."""
    applied = False
    for path in ENGINE_PATHS:
        try:
            sim[path] = 0.0
            applied = True
            break
        except Exception:
            continue
    for path in (
        "fcs/throttle-cmd-norm",
        "fcs/throttle-cmd-norm[0]",
        "propulsion/engine[0]/throttle-cmd-norm",
    ):
        try:
            sim[path] = 0.0
            applied = True
        except Exception:
            continue
    return applied


def read_engine_n1(sim: Any) -> float | None:
    for path in N1_PATHS:
        try:
            return float(sim[path])
        except Exception:
            continue
    return None


def apply_wind(sim: Any, crosswind_kt: float, heading_deg: float) -> bool:
    """Set steady crosswind from crosswind magnitude and aircraft heading."""
    crosswind_fps = crosswind_kt * 1.68781
    hdg_rad = heading_deg * 3.141592653589793 / 180.0
    # Crosswind from the right -> wind from east when heading north
    wind_north = -crosswind_fps * __import__("math").cos(hdg_rad)
    wind_east = crosswind_fps * __import__("math").sin(hdg_rad)
    try:
        sim["atmosphere/wind-north-fps"] = wind_north
        sim["atmosphere/wind-east-fps"] = wind_east
        return True
    except Exception as exc:
        logger.debug("Wind property set failed: %s", exc)
        return False


def apply_turbulence(sim: Any, turbulence_index: float, gust_factor: float) -> bool:
    """Apply turbulence intensity and gust multiplier to JSBSim atmosphere."""
    applied = False
    turb = max(0.0, min(1.0, turbulence_index))
    gust = max(0.0, min(1.0, gust_factor))
    for path in (
        "atmosphere/turbulence/magnitude-norm",
        "atmosphere/turb-type",
        "environment/turbulence/magnitude-norm",
    ):
        try:
            sim[path] = turb
            applied = True
            break
        except Exception:
            continue
    for path in (
        "atmosphere/turbulence/gust-norm",
        "atmosphere/gust-wind-norm",
    ):
        try:
            sim[path] = gust
            applied = True
        except Exception:
            continue
    return applied


def apply_environment(sim: Any, env: Any, heading_deg: float) -> None:
    """Apply full SkyMind environment state to JSBSim (wind + turbulence)."""
    apply_wind(sim, float(getattr(env, "crosswind_kt", 0.0)), heading_deg)
    apply_turbulence(
        sim,
        float(getattr(env, "turbulence_index", 0.0)),
        float(getattr(env, "gust_factor", 0.0)),
    )
