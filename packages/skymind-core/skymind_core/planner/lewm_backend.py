"""LeWM backend protocol and real engine wrapper."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from skymind_core.lewm.engine import LeWMEngine


class LeWMBackend(Protocol):
    def encode(self, obs: np.ndarray) -> np.ndarray: ...
    def predict(self, latent: np.ndarray, action: np.ndarray, env: np.ndarray) -> np.ndarray: ...


class RealLeWMBackend:
    """Wraps LeWMEngine for planner rollouts."""

    def __init__(self, engine: LeWMEngine) -> None:
        self._engine = engine

    def encode(self, obs: np.ndarray) -> np.ndarray:
        return self._engine.encode(obs)

    def predict(self, latent: np.ndarray, action: np.ndarray, env: np.ndarray) -> np.ndarray:
        return self._engine.predict(latent, action, env)
