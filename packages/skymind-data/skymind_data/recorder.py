"""Persist flight sessions to on-disk datasets (Parquet; Lance-compatible layout)."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from skymind_data.schema import SCHEMA_VERSION, frame_to_row, row_to_frame, validate_frame


class SessionRecorder:
    """Append telemetry frames to a per-session Parquet dataset."""

    def __init__(
        self,
        lance_root: str | Path = "data/lance/sessions",
        flush_every_n: int = 50,
    ) -> None:
        self.lance_root = Path(lance_root)
        self.flush_every_n = flush_every_n
        self._session_id: str | None = None
        self._aircraft_id: str = "c172"
        self._frame_index: int = 0
        self._buffer: list[dict[str, Any]] = []
        self._session_dir: Path | None = None
        self._parquet_path: Path | None = None
        self._started_at: float | None = None
        self._writer: pq.ParquetWriter | None = None
        self._session_metadata: dict[str, Any] = {}

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def start_session(self, metadata: dict[str, Any] | None = None) -> str:
        metadata = metadata or {}
        self._session_id = str(metadata.get("session_id") or uuid.uuid4())
        self._aircraft_id = str(metadata.get("aircraft_id", "c172"))
        self._session_metadata = {
            k: v
            for k, v in metadata.items()
            if k not in ("session_id", "aircraft_id")
        }
        self._frame_index = 0
        self._buffer = []
        self._started_at = time.time()

        self._session_dir = self.lance_root / self._session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._parquet_path = self._session_dir / "frames.parquet"
        self._writer = None
        return self._session_id

    def append_frame(self, frame: dict[str, Any]) -> None:
        if self._session_id is None:
            raise RuntimeError("Call start_session() before append_frame()")

        frame = dict(frame)
        frame["session_id"] = self._session_id
        frame["frame_index"] = self._frame_index
        frame.setdefault("aircraft_id", self._aircraft_id)
        if "timestamp_ns" not in frame:
            frame["timestamp_ns"] = time.time_ns()

        validate_frame(frame)
        self._buffer.append(frame_to_row(frame))
        self._frame_index += 1

        if len(self._buffer) >= self.flush_every_n:
            self._flush_buffer()

    def finalize_session(self) -> str:
        if self._session_id is None or self._session_dir is None:
            raise RuntimeError("No active session to finalize")

        self._flush_buffer()
        if self._writer is not None:
            self._writer.close()
            self._writer = None

        duration_s = 0.0
        if self._started_at is not None:
            duration_s = time.time() - self._started_at

        manifest: dict[str, Any] = {
            "manifest_version": "1",
            "session_id": self._session_id,
            "aircraft_id": self._aircraft_id,
            "schema_version": SCHEMA_VERSION,
            "storage_format": "parquet",
            "frame_count": self._frame_index,
            "duration_s": round(duration_s, 2),
            "lance_uri": str(self._session_dir),
            "frames_file": "frames.parquet",
        }
        for key in ("maneuver_id", "collection_run_id", "environment"):
            if key in self._session_metadata:
                manifest[key] = self._session_metadata[key]
        manifest_path = self._session_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        uri = str(self._session_dir)
        self._session_id = None
        self._session_dir = None
        self._parquet_path = None
        self._buffer = []
        self._session_metadata = {}
        return uri

    def _flush_buffer(self) -> None:
        if not self._buffer or self._parquet_path is None:
            return

        table = pa.Table.from_pylist(self._buffer)
        if self._writer is None:
            self._writer = pq.ParquetWriter(
                self._parquet_path,
                table.schema,
                compression="zstd",
            )
        self._writer.write_table(table)
        self._buffer = []

    @staticmethod
    def read_session(session_path: str | Path) -> list[dict[str, Any]]:
        path = Path(session_path)
        parquet_file = path / "frames.parquet"
        if not parquet_file.exists():
            raise FileNotFoundError(f"No frames.parquet in {path}")
        table = pq.read_table(parquet_file)
        return [row_to_frame(r) for r in table.to_pylist()]

    @staticmethod
    def frame_count(session_path: str | Path) -> int:
        path = Path(session_path)
        manifest = path / "manifest.json"
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return int(data.get("frame_count", 0))
        return len(SessionRecorder.read_session(path))

    @staticmethod
    def read_manifest(session_path: str | Path) -> dict[str, Any]:
        path = Path(session_path)
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"No manifest.json in {path}")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    @staticmethod
    def query_sessions(
        lance_root: str | Path,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Scan session manifests under lance_root matching optional filters."""
        root = Path(lance_root)
        if not root.exists():
            return []

        filters = filters or {}
        results: list[dict[str, Any]] = []
        for manifest_path in sorted(root.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            match = True
            for key, value in filters.items():
                if manifest.get(key) != value:
                    match = False
                    break
            if match:
                results.append(manifest)
        return results
