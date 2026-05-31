from skymind_data.recorder import SessionRecorder
from skymind_data.schema import (
    ACTION_DIM,
    SCHEMA_VERSION,
    SchemaValidationError,
    frame_to_row,
    row_to_frame,
    validate_frame,
)


def __getattr__(name: str):
    if name == "AutopilotCollector":
        from skymind_data.collection import AutopilotCollector

        return AutopilotCollector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AutopilotCollector",
    "SessionRecorder",
    "ACTION_DIM",
    "SCHEMA_VERSION",
    "SchemaValidationError",
    "frame_to_row",
    "row_to_frame",
    "validate_frame",
]
