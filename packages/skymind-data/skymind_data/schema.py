"""Lance frame schema v1 — telemetry only (no PNG / latent)."""

from __future__ import annotations

from typing import Any

import numpy as np

ACTION_DIM = 8
SCHEMA_VERSION = "1"

REQUIRED_FRAME_FIELDS = ("alt_ft", "ias_kt", "heading_deg", "sim_time_s")
ALT_FT_MIN = -1000.0
ALT_FT_MAX = 60000.0
IAS_KT_MIN = 0.0
IAS_KT_MAX = 400.0


class SchemaValidationError(ValueError):
    """Raised when a telemetry frame fails schema validation."""


def validate_frame(frame: dict[str, Any]) -> None:
    """Validate a telemetry frame dict before persistence."""
    for field in REQUIRED_FRAME_FIELDS:
        if field not in frame:
            raise SchemaValidationError(f"Missing required field: {field}")

    alt_ft = float(frame["alt_ft"])
    if not ALT_FT_MIN <= alt_ft <= ALT_FT_MAX:
        raise SchemaValidationError(
            f"alt_ft out of range [{ALT_FT_MIN}, {ALT_FT_MAX}]: {alt_ft}"
        )

    ias_kt = float(frame["ias_kt"])
    if not IAS_KT_MIN <= ias_kt <= IAS_KT_MAX:
        raise SchemaValidationError(
            f"ias_kt out of range [{IAS_KT_MIN}, {IAS_KT_MAX}]: {ias_kt}"
        )

    heading_deg = float(frame["heading_deg"])
    if not 0.0 <= heading_deg < 360.0:
        raise SchemaValidationError(
            f"heading_deg out of range [0, 360): {heading_deg}"
        )

    action = frame.get("action_vector")
    if action is not None and len(action) != ACTION_DIM:
        raise SchemaValidationError(
            f"action_vector length must be {ACTION_DIM}, got {len(action)}"
        )

# Fixed column order for Lance / PyArrow
FRAME_COLUMNS: list[str] = [
    "session_id",
    "frame_index",
    "timestamp_ns",
    "sim_time_s",
    "aircraft_id",
    "lat_deg",
    "lon_deg",
    "pos_x_m",
    "pos_y_m",
    "alt_ft",
    "ias_kt",
    "heading_deg",
    "pitch_deg",
    "roll_deg",
    "yaw_deg",
    "vs_fpm",
    "throttle",
    "elevator",
    "aileron",
    "rudder",
    "engine_n1",
    "engine_n2",
    "on_ground",
    "failure_engine",
    "failure_attitude",
    "failure_comms",
    "action_vector",
]


def frame_to_row(frame: dict[str, Any]) -> dict[str, Any]:
    """Convert a telemetry frame dict to a Lance-ready row."""
    action = frame.get("action_vector", [0.0] * ACTION_DIM)
    if len(action) != ACTION_DIM:
        padded = [0.0] * ACTION_DIM
        for i, v in enumerate(action[:ACTION_DIM]):
            padded[i] = float(v)
        action = padded

    return {
        "session_id": str(frame["session_id"]),
        "frame_index": int(frame["frame_index"]),
        "timestamp_ns": int(frame["timestamp_ns"]),
        "sim_time_s": float(frame["sim_time_s"]),
        "aircraft_id": str(frame["aircraft_id"]),
        "lat_deg": _optional_float(frame.get("lat_deg")),
        "lon_deg": _optional_float(frame.get("lon_deg")),
        "pos_x_m": float(frame.get("pos_x_m", 0.0)),
        "pos_y_m": float(frame.get("pos_y_m", 0.0)),
        "alt_ft": float(frame["alt_ft"]),
        "ias_kt": float(frame["ias_kt"]),
        "heading_deg": float(frame["heading_deg"]),
        "pitch_deg": float(frame.get("pitch_deg", 0.0)),
        "roll_deg": float(frame.get("roll_deg", 0.0)),
        "yaw_deg": float(frame.get("yaw_deg", 0.0)),
        "vs_fpm": float(frame.get("vs_fpm", 0.0)),
        "throttle": float(frame.get("throttle", 0.0)),
        "elevator": float(frame.get("elevator", 0.0)),
        "aileron": float(frame.get("aileron", 0.0)),
        "rudder": float(frame.get("rudder", 0.0)),
        "engine_n1": _optional_float(frame.get("engine_n1")),
        "engine_n2": _optional_float(frame.get("engine_n2")),
        "on_ground": bool(frame.get("on_ground", False)),
        "failure_engine": bool(frame.get("failure_engine", False)),
        "failure_attitude": bool(frame.get("failure_attitude", False)),
        "failure_comms": bool(frame.get("failure_comms", False)),
        "action_vector": np.array(action, dtype=np.float32),
    }


def row_to_frame(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a Lance row back to a telemetry frame dict."""
    action = row["action_vector"]
    if hasattr(action, "tolist"):
        action = action.tolist()

    return {
        "session_id": row["session_id"],
        "frame_index": int(row["frame_index"]),
        "timestamp_ns": int(row["timestamp_ns"]),
        "sim_time_s": float(row["sim_time_s"]),
        "aircraft_id": row["aircraft_id"],
        "lat_deg": row.get("lat_deg"),
        "lon_deg": row.get("lon_deg"),
        "pos_x_m": float(row["pos_x_m"]),
        "pos_y_m": float(row["pos_y_m"]),
        "alt_ft": float(row["alt_ft"]),
        "ias_kt": float(row["ias_kt"]),
        "heading_deg": float(row["heading_deg"]),
        "pitch_deg": float(row["pitch_deg"]),
        "roll_deg": float(row["roll_deg"]),
        "yaw_deg": float(row["yaw_deg"]),
        "vs_fpm": float(row["vs_fpm"]),
        "throttle": float(row["throttle"]),
        "elevator": float(row["elevator"]),
        "aileron": float(row["aileron"]),
        "rudder": float(row["rudder"]),
        "engine_n1": row.get("engine_n1"),
        "engine_n2": row.get("engine_n2"),
        "on_ground": bool(row["on_ground"]),
        "failure_engine": bool(row["failure_engine"]),
        "failure_attitude": bool(row["failure_attitude"]),
        "failure_comms": bool(row["failure_comms"]),
        "action_vector": list(action),
    }


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    return float(value)
