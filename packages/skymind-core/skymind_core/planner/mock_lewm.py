"""Deterministic mock LeWM for CPU-only planner tests."""

from __future__ import annotations

import numpy as np

from skymind_core.lewm.state_vector import ACTION_DIM, ENV_DIM, LATENT_DIM, STATE_DIM


class MockLeWMEngine:
    """Lightweight latent rollout backend for CEM unit tests."""

    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)
        self._proj = self._rng.standard_normal((LATENT_DIM, STATE_DIM)).astype(np.float32) * 0.01

    def encode(self, obs: np.ndarray) -> np.ndarray:
        x = np.asarray(obs, dtype=np.float32).reshape(-1)
        if x.size < STATE_DIM:
            padded = np.zeros(STATE_DIM, dtype=np.float32)
            padded[: x.size] = x
            x = padded
        latent = self._proj @ x[:STATE_DIM]
        if latent.shape[0] < LATENT_DIM:
            out = np.zeros(LATENT_DIM, dtype=np.float32)
            out[: latent.shape[0]] = latent
            return out
        return latent[:LATENT_DIM].astype(np.float32)

    def predict(
        self,
        latent: np.ndarray,
        action: np.ndarray,
        env: np.ndarray,
    ) -> np.ndarray:
        z = np.asarray(latent, dtype=np.float32).reshape(-1)
        a = np.asarray(action, dtype=np.float32).reshape(-1)
        e = np.asarray(env, dtype=np.float32).reshape(-1)
        if e.size < ENV_DIM:
            padded = np.zeros(ENV_DIM, dtype=np.float32)
            padded[: e.size] = e
            e = padded
        delta = 0.02 * float(e.sum()) + 0.005 * float(a[: min(len(a), ACTION_DIM)].sum())
        noise = self._rng.normal(0.0, 0.001, size=z.shape)
        out = z + delta + noise
        if out.shape[0] < LATENT_DIM:
            padded = np.zeros(LATENT_DIM, dtype=np.float32)
            padded[: out.shape[0]] = out
            return padded
        return out[:LATENT_DIM].astype(np.float32)
