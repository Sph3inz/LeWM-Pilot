"""Parquet session loader for LeWM fine-tuning."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

from skymind_core.lewm.state_vector import (
    environment_to_vector,
    frame_to_action,
    frame_to_obs,
)
from skymind_data.recorder import SessionRecorder


def load_manifest_session_ids(manifest_path: str | Path) -> list[str]:
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    return list(data.get("session_ids", []))


def split_sessions(
    session_ids: list[str],
    lance_root: str | Path,
    val_fraction: float = 0.15,
    seed: int = 42,
) -> tuple[list[str], list[str]]:
    lance_root = Path(lance_root)
    failure_sessions: list[str] = []
    normal_sessions: list[str] = []

    for sid in session_ids:
        manifest_path = lance_root / sid / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        maneuver = manifest.get("maneuver_id", "")
        if "engine_out" in maneuver or "partial_panel" in maneuver:
            failure_sessions.append(sid)
        else:
            normal_sessions.append(sid)

    rng = random.Random(seed)
    rng.shuffle(failure_sessions)
    rng.shuffle(normal_sessions)

    n_val = max(1, int(len(session_ids) * val_fraction))
    val_ids = failure_sessions[: max(1, n_val // 2)]
    remaining = n_val - len(val_ids)
    val_ids.extend(normal_sessions[:remaining])
    train_ids = [s for s in session_ids if s not in val_ids]
    return train_ids, val_ids


def build_transitions(
    session_ids: list[str],
    lance_root: str | Path,
    max_samples: int | None = None,
) -> list[dict[str, np.ndarray]]:
    lance_root = Path(lance_root)
    transitions: list[dict[str, np.ndarray]] = []

    for sid in session_ids:
        session_path = lance_root / sid
        if not (session_path / "frames.parquet").exists():
            continue
        manifest: dict = {}
        manifest_path = session_path / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        env_vec = environment_to_vector(manifest.get("environment"))

        frames = SessionRecorder.read_session(session_path)
        for i in range(len(frames) - 1):
            transitions.append(
                {
                    "obs": frame_to_obs(frames[i]),
                    "action": frame_to_action(frames[i]),
                    "env": env_vec,
                    "next_obs": frame_to_obs(frames[i + 1]),
                }
            )
            if max_samples and len(transitions) >= max_samples:
                return transitions
    return transitions


class LeWMDataset:
    def __init__(self, transitions: list[dict[str, np.ndarray]]) -> None:
        self.transitions = transitions

    def __len__(self) -> int:
        return len(self.transitions)

    def __getitem__(self, idx: int) -> dict[str, np.ndarray]:
        return self.transitions[idx]

    @classmethod
    def from_manifests(
        cls,
        manifest_paths: list[str | Path],
        lance_root: str | Path,
        val_fraction: float = 0.15,
        max_train_samples: int | None = None,
        max_val_samples: int | None = None,
    ) -> tuple["LeWMDataset", "LeWMDataset"]:
        lance_root = Path(lance_root)
        all_ids: list[str] = []
        for mp in manifest_paths:
            all_ids.extend(load_manifest_session_ids(mp))
        all_ids = list(dict.fromkeys(all_ids))
        train_ids, val_ids = split_sessions(all_ids, lance_root, val_fraction)
        train_t = build_transitions(train_ids, lance_root, max_train_samples)
        val_t = build_transitions(val_ids, lance_root, max_val_samples)
        return cls(train_t), cls(val_t)
