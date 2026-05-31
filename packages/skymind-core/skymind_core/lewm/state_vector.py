"""LeWM state-vector encoding for flight telemetry."""

from __future__ import annotations

from typing import Any

import numpy as np

STATE_DIM = 52
ACTION_DIM = 8
ENV_DIM = 5
LATENT_DIM = 192

# Fixed scales for stable LeWM training (Phase 1)
_OBS_SCALES = np.array(
    [
        1e4, 1e4, 1e4,  # pos x,y alt
        180.0, 180.0, 360.0, 360.0,  # pitch roll yaw heading
        200.0, 2000.0,  # rates block
        90.0, 180.0,  # lat lon approx
        36000.0,  # sim time
        200.0, 2000.0, 1e4,  # ias vs alt repeat block
        1.0, 1.0, 1.0, 1.0,  # controls
        100.0, 100.0,  # engine
        1.0, 1.0, 1.0, 1.0,  # flags
        *[1.0] * (STATE_DIM - 25),
    ],
    dtype=np.float32,
)[:STATE_DIM]


def _scale_obs(obs: np.ndarray) -> np.ndarray:
    scales = _OBS_SCALES[: len(obs)]
    return obs / np.maximum(scales, 1e-6)


def frame_to_obs(frame: dict[str, Any]) -> np.ndarray:
    """Convert a telemetry frame dict to a fixed 52-d observation vector."""
    action = frame.get("action_vector") or [0.0] * ACTION_DIM
    if hasattr(action, "tolist"):
        action = action.tolist()

    obs = np.zeros(STATE_DIM, dtype=np.float32)
    obs[0] = float(frame.get("pos_x_m", 0.0))
    obs[1] = float(frame.get("pos_y_m", 0.0))
    obs[2] = float(frame.get("alt_ft", 0.0))
    obs[3] = float(frame.get("pitch_deg", 0.0))
    obs[4] = float(frame.get("roll_deg", 0.0))
    obs[5] = float(frame.get("yaw_deg", frame.get("heading_deg", 0.0)))
    obs[6] = float(frame.get("heading_deg", 0.0))
    obs[7] = float(frame.get("ias_kt", 0.0))
    obs[8] = float(frame.get("vs_fpm", 0.0))
    obs[9] = float(frame.get("lat_deg") or 0.0)
    obs[10] = float(frame.get("lon_deg") or 0.0)
    obs[11] = float(frame.get("sim_time_s", 0.0))
    obs[12] = float(frame.get("ias_kt", 0.0))
    obs[13] = float(frame.get("vs_fpm", 0.0))
    obs[14] = float(frame.get("alt_ft", 0.0))
    obs[15] = float(action[0]) if len(action) > 0 else 0.0
    obs[16] = float(action[1]) if len(action) > 1 else 0.0
    obs[17] = float(action[2]) if len(action) > 2 else 0.0
    obs[18] = float(action[3]) if len(action) > 3 else 0.0
    obs[19] = float(frame.get("engine_n1") or 0.0)
    obs[20] = float(frame.get("engine_n2") or 0.0)
    obs[21] = 1.0 if frame.get("on_ground") else 0.0
    obs[22] = 1.0 if frame.get("failure_engine") else 0.0
    obs[23] = 1.0 if frame.get("failure_attitude") else 0.0
    obs[24] = 1.0 if frame.get("failure_comms") else 0.0
    return _scale_obs(obs)


def frame_to_action(frame: dict[str, Any]) -> np.ndarray:
    action = frame.get("action_vector") or [0.0] * ACTION_DIM
    if hasattr(action, "tolist"):
        action = action.tolist()
    out = np.zeros(ACTION_DIM, dtype=np.float32)
    for i, v in enumerate(action[:ACTION_DIM]):
        out[i] = float(v)
    return out


def environment_to_vector(env: dict[str, Any] | None) -> np.ndarray:
    env = env or {}
    raw = np.array(
        [
            float(env.get("crosswind_kt", 0.0)),
            float(env.get("gust_factor", 0.0)),
            float(env.get("turbulence_index", 0.0)),
            float(env.get("visibility_sm", 10.0)),
            float(env.get("ceiling_ft", 10000.0)),
        ],
        dtype=np.float32,
    )
    scales = np.array([20.0, 1.0, 1.0, 10.0, 10000.0], dtype=np.float32)
    return raw / scales
