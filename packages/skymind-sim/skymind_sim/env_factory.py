"""Create jsbgym / JSBSim Gymnasium environments."""

from __future__ import annotations

import re
from typing import Any, Literal

import gymnasium as gym

T6_ENV_ID = "JSBSim-HeadingControl-T6Texan2-NoFG-v0"

_t6_registered = False


def _ensure_jsbgym_registered() -> None:
    try:
        import jsbgym  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "jsbgym is not installed. Install with:\n"
            "  pip install git+https://github.com/sryu1/jsbgym.git\n"
            "Also ensure jsbsim is installed and MSVC redistributable is present on Windows."
        ) from exc


def register_t6_envs() -> str:
    """Register T-6 Texan II HeadingControl env if not already present."""
    global _t6_registered
    _ensure_jsbgym_registered()
    if T6_ENV_ID in gym.envs.registry:
        _t6_registered = True
        return T6_ENV_ID

    from jsbgym.aircraft import Aircraft
    from jsbgym.tasks import HeadingControlTask, Shaping

    t6 = Aircraft("t6texan2", "t6texan2", "T6", 150)
    gym.register(
        id=T6_ENV_ID,
        entry_point="jsbgym.environment:NoFGJsbSimEnv",
        kwargs=dict(
            aircraft=t6,
            task_type=HeadingControlTask,
            shaping=Shaping.STANDARD,
        ),
    )
    _t6_registered = True
    return T6_ENV_ID


def discover_c172_env_id() -> str:
    """Find first registered env id that looks like a C172 / 172 task."""
    _ensure_jsbgym_registered()
    pattern = re.compile(r"(172|c172)", re.IGNORECASE)
    candidates: list[str] = []
    for env_id in gym.envs.registry.keys():
        if pattern.search(env_id):
            candidates.append(env_id)
    if not candidates:
        raise RuntimeError(
            "No C172 jsbgym environment found in Gymnasium registry. "
            "Set jsbgym_env_id explicitly in configs/sim.yaml."
        )
    no_fg = [c for c in candidates if "NoFG" in c or "noFG" in c]
    if no_fg:
        candidates = no_fg
    for preferred in ("Heading", "heading", "Control"):
        for cid in candidates:
            if preferred in cid:
                return cid
    return sorted(candidates)[0]


def discover_t6_env_id() -> str:
    return register_t6_envs()


def resolve_env_id(
    aircraft_id: Literal["c172", "t6"] = "c172",
    env_id: str | None = None,
) -> str:
    if env_id:
        return env_id
    if aircraft_id == "t6":
        return discover_t6_env_id()
    return discover_c172_env_id()


def make_env(
    env_id: str | None = None,
    aircraft_id: Literal["c172", "t6"] = "c172",
    render_mode: str | None = None,
) -> gym.Env:
    _ensure_jsbgym_registered()
    resolved = resolve_env_id(aircraft_id, env_id)
    kwargs: dict[str, Any] = {}
    if render_mode is not None:
        kwargs["render_mode"] = render_mode
    try:
        return gym.make(resolved, **kwargs)
    except Exception as exc:
        raise RuntimeError(f"Failed to create environment '{resolved}': {exc}") from exc
