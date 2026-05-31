"""Difficulty estimation from latent rollouts."""

from __future__ import annotations

import numpy as np


def estimate_difficulty(latent_trajectory: list[np.ndarray]) -> float:
    """Higher value = harder predicted flight state."""
    if not latent_trajectory:
        return 0.0
    stacked = np.stack([np.asarray(z, dtype=np.float32).reshape(-1) for z in latent_trajectory])
    return float(np.std(stacked) + 0.1 * np.mean(np.abs(stacked)))


def map_difficulty_to_score(difficulty: float, *, scale: float = 2.5) -> float:
    """Map difficulty proxy to predicted performance score in [0, 1]."""
    return float(np.clip(1.0 - difficulty * scale, 0.0, 1.0))
