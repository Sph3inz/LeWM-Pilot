"""CEM inverse planner for environment difficulty."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from skymind_core.lewm.state_vector import ACTION_DIM, ENV_DIM, environment_to_vector
from skymind_core.models import EnvironmentDelta
from skymind_core.planner.difficulty import estimate_difficulty, map_difficulty_to_score
from skymind_core.planner.lewm_backend import LeWMBackend
from skymind_core.planner.mock_lewm import MockLeWMEngine
from skymind_sim.models import EnvironmentState

_DEFAULT_CONFIG: dict[str, Any] = {
    "cem_population": 128,
    "cem_elite_frac": 0.1,
    "cem_iterations": 3,
    "horizon_steps": 5,
    "max_crosswind_delta_kt": 5,
    "max_gust_delta": 0.15,
    "max_turbulence_delta": 0.2,
    "max_visibility_delta_sm": 2.0,
    "max_ceiling_delta_ft": 1500,
    "plan_interval_s": 10,
    "plan_on_score_out_of_band": True,
    "score_band_low": 0.35,
    "score_band_high": 0.75,
    "budget_ms": 8000,
    "difficulty_scale": 2.5,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_planner_config(config_path: str | Path | None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _repo_root() / "configs" / "planner.yaml"
    merged = dict(_DEFAULT_CONFIG)
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            merged.update(yaml.safe_load(fh) or {})
    return merged


def _delta_bounds(cfg: dict[str, Any]) -> np.ndarray:
    return np.array(
        [
            float(cfg["max_crosswind_delta_kt"]),
            float(cfg["max_gust_delta"]),
            float(cfg["max_turbulence_delta"]),
            float(cfg["max_visibility_delta_sm"]),
            float(cfg["max_ceiling_delta_ft"]),
        ],
        dtype=np.float32,
    )


def _delta_to_env_vector(base_env: EnvironmentState, delta: np.ndarray) -> np.ndarray:
    env = EnvironmentState(
        crosswind_kt=base_env.crosswind_kt + float(delta[0]),
        gust_factor=base_env.gust_factor + float(delta[1]),
        turbulence_index=base_env.turbulence_index + float(delta[2]),
        visibility_sm=base_env.visibility_sm + float(delta[3]),
        ceiling_ft=base_env.ceiling_ft + float(delta[4]),
    )
    return environment_to_vector(env.model_dump())


class Planner:
    """CEM inverse planner over latent LeWM rollouts."""

    def __init__(
        self,
        backend: LeWMBackend | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self._cfg = _load_planner_config(config_path)
        self._backend: LeWMBackend = backend or MockLeWMEngine()
        self._neutral_action = np.zeros(ACTION_DIM, dtype=np.float32)
        bounds = _delta_bounds(self._cfg)
        self._mean = np.zeros(5, dtype=np.float32)
        self._std = bounds * 0.25

    def plan_forward(self, latent: np.ndarray, horizon: int, goal: dict) -> list[np.ndarray]:
        _ = goal
        trajectory = [np.asarray(latent, dtype=np.float32)]
        z = trajectory[0]
        base_env = np.zeros(ENV_DIM, dtype=np.float32)
        for _ in range(horizon):
            z = self._backend.predict(z, self._neutral_action, base_env)
            trajectory.append(z)
        return trajectory

    def inverse_plan(
        self,
        latent: np.ndarray,
        target_score: float,
        current_env: EnvironmentState,
    ) -> EnvironmentDelta:
        target = float(np.clip(target_score, 0.4, 0.7))
        bounds = _delta_bounds(self._cfg)
        pop = int(self._cfg["cem_population"])
        elite_n = max(1, int(pop * float(self._cfg["cem_elite_frac"])))
        horizon = int(self._cfg["horizon_steps"])
        iterations = int(self._cfg["cem_iterations"])
        budget_ms = float(self._cfg["budget_ms"])
        scale = float(self._cfg.get("difficulty_scale", 2.5))
        start = time.perf_counter()

        best_delta = np.zeros(5, dtype=np.float32)
        best_cost = float("inf")
        mean = self._mean.copy()
        std = np.maximum(self._std, bounds * 0.05)

        for _ in range(iterations):
            if (time.perf_counter() - start) * 1000.0 >= budget_ms:
                break
            samples = self._rng_population(mean, std, pop, bounds)
            costs = np.zeros(pop, dtype=np.float32)
            for i, delta in enumerate(samples):
                traj = self._rollout(latent, delta, current_env, horizon)
                difficulty = estimate_difficulty(traj)
                predicted = map_difficulty_to_score(difficulty, scale=scale)
                costs[i] = abs(predicted - target)
                if costs[i] < best_cost:
                    best_cost = float(costs[i])
                    best_delta = delta.copy()
            elite_idx = np.argsort(costs)[:elite_n]
            elite = samples[elite_idx]
            mean = elite.mean(axis=0)
            std = elite.std(axis=0)
            std = np.minimum(std, bounds)
            std = np.maximum(std, bounds * 0.02)

        self._mean = mean
        self._std = std
        best_delta = np.clip(best_delta, -bounds, bounds)
        return EnvironmentDelta(
            crosswind_delta_kt=float(best_delta[0]),
            gust_factor_delta=float(best_delta[1]),
            turbulence_delta=float(best_delta[2]),
            visibility_delta_sm=float(best_delta[3]),
            ceiling_delta_ft=float(best_delta[4]),
        )

    def encode_obs(self, obs: np.ndarray) -> np.ndarray:
        return self._backend.encode(obs)

    def should_replan(self, current_score: float, sim_time_s: float, last_plan_s: float) -> bool:
        interval = float(self._cfg["plan_interval_s"])
        elapsed = sim_time_s - last_plan_s
        if elapsed >= interval:
            return True
        if not self._cfg.get("plan_on_score_out_of_band", True):
            return False
        if elapsed < min(5.0, interval):
            return False
        low = float(self._cfg["score_band_low"])
        high = float(self._cfg["score_band_high"])
        return current_score < low or current_score > high

    def apply_delta(self, delta: EnvironmentDelta, adapter: Any) -> None:
        current = adapter.get_environment()
        bounds = _delta_bounds(self._cfg)
        d0 = float(np.clip(delta.crosswind_delta_kt, -bounds[0], bounds[0]))
        d1 = float(np.clip(delta.gust_factor_delta, -bounds[1], bounds[1]))
        d2 = float(np.clip(delta.turbulence_delta, -bounds[2], bounds[2]))
        d3 = float(np.clip(delta.visibility_delta_sm, -bounds[3], bounds[3]))
        d4 = float(np.clip(delta.ceiling_delta_ft, -bounds[4], bounds[4]))
        env = EnvironmentState(
            crosswind_kt=max(0.0, current.crosswind_kt + d0),
            gust_factor=max(0.0, min(1.0, current.gust_factor + d1)),
            turbulence_index=max(0.0, min(1.0, current.turbulence_index + d2)),
            visibility_sm=max(0.1, current.visibility_sm + d3),
            ceiling_ft=max(100.0, current.ceiling_ft + d4),
        )
        adapter.set_environment(env)

    def _rollout(
        self,
        latent: np.ndarray,
        delta: np.ndarray,
        current_env: EnvironmentState,
        horizon: int,
    ) -> list[np.ndarray]:
        env_vec = _delta_to_env_vector(current_env, delta)
        z = np.asarray(latent, dtype=np.float32)
        trajectory = [z.copy()]
        for _ in range(horizon):
            z = self._backend.predict(z, self._neutral_action, env_vec)
            trajectory.append(z.copy())
        return trajectory

    @staticmethod
    def _rng_population(
        mean: np.ndarray,
        std: np.ndarray,
        pop: int,
        bounds: np.ndarray,
    ) -> np.ndarray:
        rng = np.random.default_rng()
        samples = rng.normal(mean, std, size=(pop, 5)).astype(np.float32)
        return np.clip(samples, -bounds, bounds)
