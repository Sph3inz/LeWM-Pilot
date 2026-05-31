"""SimulatorAdapter — jsbgym wrapper for SkyMind."""

from __future__ import annotations

import math
import uuid
from typing import Any, Literal

import numpy as np

from skymind_data.schema import ACTION_DIM
from skymind_sim.env_factory import make_env
from skymind_sim.failures import apply_engine_failure, apply_environment, read_engine_n1
from skymind_sim.models import EnvironmentState, ScenarioConfig, TelemetrySnapshot


class SimulatorAdapter:
    """Wraps a Gymnasium jsbgym environment with unified telemetry."""

    def __init__(
        self,
        env_id: str | None = None,
        sim_hz: float = 10.0,
        aircraft_id: Literal["c172", "t6"] = "c172",
    ) -> None:
        self._env_id = env_id
        self._aircraft_id = aircraft_id
        self._sim_hz = sim_hz
        self._env = None
        self._session_id: str | None = None
        self._config: ScenarioConfig | None = None
        self._step_count = 0
        self._last_sim_time_s = 0.0
        self._last_telemetry = TelemetrySnapshot()
        self._control_mode: Literal["human_keyboard", "autopilot"] = "autopilot"
        self._failure_flags = {
            "failure_engine": False,
            "failure_attitude": False,
            "failure_comms": False,
            "failure_hydraulic": False,
        }
        self._state_field_names: list[str] = []
        self._environment = EnvironmentState()

    def _resolve_sim_time_s(self, sim: Any | None) -> float:
        """Monotonic sim clock — never accept a mid-flight time drop from JSBSim."""
        step_time = self._step_count / self._sim_hz if self._step_count > 0 else 0.0
        if sim is None:
            return max(step_time, self._last_sim_time_s)

        try:
            jsb_time = float(sim.jsbsim["simulation/sim-time-sec"])
            # Normal forward tick
            if jsb_time >= self._last_sim_time_s - 0.05:
                self._last_sim_time_s = jsb_time
                return jsb_time
            # Episode rollover: sim restarted near zero while step counter also reset
            if jsb_time < 2.0 and self._step_count <= 2 and self._last_sim_time_s > 30.0:
                self._last_sim_time_s = jsb_time
                return jsb_time
        except Exception:
            pass

        resolved = max(step_time, self._last_sim_time_s)
        self._last_sim_time_s = resolved
        return resolved

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def reset(self, config: ScenarioConfig, *, new_session: bool = True) -> str:
        if self._env is not None:
            self._env.close()
        self._aircraft_id = config.aircraft_id
        self._env = make_env(self._env_id, aircraft_id=config.aircraft_id)
        self._config = config
        if new_session or self._session_id is None:
            self._session_id = str(uuid.uuid4())
        self._step_count = 0
        self._last_sim_time_s = 0.0
        self._clear_failure_flags()
        self._cache_state_fields()

        self._apply_episode_limits(config.episode_time_s)
        obs, info = self._env.reset()
        self._last_telemetry = self._obs_to_telemetry(obs, info, action=None)
        self._last_telemetry.aircraft_id = config.aircraft_id
        if config.environment:
            self.set_environment(config.environment)
        return self._session_id

    def reset_episode(self, config: ScenarioConfig | None = None) -> None:
        """Reset sim for episode rollover without creating a new session ID."""
        if self._env is None:
            raise RuntimeError("Call reset() before reset_episode()")
        if config is not None:
            self._config = config
            self._apply_episode_limits(config.episode_time_s)
        self._step_count = 0
        self._last_sim_time_s = 0.0
        self._clear_failure_flags()
        obs, info = self._env.reset()
        self._last_telemetry = self._obs_to_telemetry(obs, info, action=None)
        if self._config:
            self._last_telemetry.aircraft_id = self._config.aircraft_id
            if self._config.environment:
                self.set_environment(self._config.environment)

    def step(self, action: list[float]) -> tuple[TelemetrySnapshot, bool]:
        if self._env is None:
            raise RuntimeError("Call reset() before step()")

        action_arr = self._format_action(action)
        obs, _reward, terminated, truncated, info = self._env.step(action_arr)
        self._step_count += 1
        done = bool(terminated or truncated)
        self._last_telemetry = self._obs_to_telemetry(obs, info, action=action)
        if self._config:
            self._last_telemetry.aircraft_id = self._config.aircraft_id
        return self._last_telemetry, done

    def get_telemetry(self) -> TelemetrySnapshot:
        return self._last_telemetry

    def inject_failure(self, failure_id: str, params: dict | None = None) -> None:
        _ = params
        key = {
            "engine_failure": "failure_engine",
            "attitude_failure": "failure_attitude",
            "comms_failure": "failure_comms",
            "hydraulic_leak": "failure_hydraulic",
        }.get(failure_id)
        if not key:
            return
        self._failure_flags[key] = True
        setattr(self._last_telemetry, key, True)
        if failure_id == "engine_failure":
            sim = self._get_sim()
            if sim is not None:
                apply_engine_failure(sim)

    def get_environment(self) -> EnvironmentState:
        return self._environment.model_copy()

    def set_environment(self, env: EnvironmentState) -> None:
        self._environment = env
        sim = self._get_sim()
        if sim is None:
            return
        apply_environment(sim, env, self._last_telemetry.heading_deg)

    def set_control_mode(self, mode: Literal["human_keyboard", "autopilot"]) -> None:
        self._control_mode = mode

    def close(self) -> None:
        if self._env is not None:
            self._env.close()
            self._env = None

    def _apply_episode_limits(self, episode_time_s: float) -> None:
        if self._env is None:
            return
        task = getattr(self._env.unwrapped, "task", None)
        if task is not None:
            if hasattr(task, "max_time_s"):
                task.max_time_s = float(episode_time_s)
            if hasattr(task, "max_altitude_deviation_ft"):
                task.max_altitude_deviation_ft = max(
                    float(getattr(task, "max_altitude_deviation_ft", 1000)),
                    1500.0,
                )

    def _clear_failure_flags(self) -> None:
        self._failure_flags = {
            "failure_engine": False,
            "failure_attitude": False,
            "failure_comms": False,
            "failure_hydraulic": False,
        }

    def _cache_state_fields(self) -> None:
        self._state_field_names = []
        task = getattr(self._env.unwrapped, "task", None) if self._env else None
        if task is not None and hasattr(task, "state_variables"):
            self._state_field_names = [
                p.get_legal_name() for p in task.state_variables
            ]

    def _get_sim(self) -> Any | None:
        if self._env is None:
            return None
        return getattr(self._env.unwrapped, "sim", None)

    def _format_action(self, action: list[float]) -> np.ndarray:
        """Map SkyMind action vector to jsbgym [aileron, elevator, rudder]."""
        a = [float(np.clip(v, -1.0, 1.0)) for v in action[:ACTION_DIM]]
        while len(a) < 4:
            a.append(0.0)
        # action: [throttle, elevator, aileron, rudder, ...]
        return np.array([a[2], a[1], a[3]], dtype=np.float32)

    def _obs_to_telemetry(
        self,
        obs: Any,
        info: dict,
        action: list[float] | None,
    ) -> TelemetrySnapshot:
        sim = self._get_sim()
        t = TelemetrySnapshot(sim_time_s=self._resolve_sim_time_s(sim))

        if isinstance(obs, np.ndarray) and self._state_field_names:
            state = {
                name: float(obs[i])
                for i, name in enumerate(self._state_field_names)
                if i < len(obs)
            }
            t = self._telemetry_from_jsbgym_state(state, t)
        elif isinstance(obs, np.ndarray):
            arr = obs.flatten().astype(float)
            if arr.size >= 1:
                t.alt_ft = float(arr[0])
            if arr.size >= 4:
                fps = float(math.sqrt(arr[3] ** 2 + (arr[4] ** 2 if arr.size > 4 else 0) ** 2))
                t.ias_kt = fps * 0.592484

        t = self._fill_from_simulation(t)

        if action is not None and len(action) >= 3:
            t.throttle = float(action[0]) if len(action) > 4 else 0.8
            t.elevator = float(action[1])
            t.aileron = float(action[2])
            t.rudder = float(action[3]) if len(action) > 3 else 0.0

        t.failure_engine = self._failure_flags["failure_engine"]
        t.failure_attitude = self._failure_flags["failure_attitude"]
        t.failure_comms = self._failure_flags["failure_comms"]
        t.failure_hydraulic = self._failure_flags.get("failure_hydraulic", False)
        t.environment = self._environment.model_copy()
        return t

    def _telemetry_from_jsbgym_state(
        self, state: dict[str, float], t: TelemetrySnapshot
    ) -> TelemetrySnapshot:
        t.alt_ft = state.get("position_h_sl_ft", t.alt_ft)
        t.pitch_deg = math.degrees(state.get("attitude_pitch_rad", 0.0))
        t.roll_deg = math.degrees(state.get("attitude_roll_rad", 0.0))
        u = state.get("velocities_u_fps", 0.0)
        v = state.get("velocities_v_fps", 0.0)
        w = state.get("velocities_w_fps", 0.0)
        fps = math.sqrt(u * u + v * v + w * w)
        t.ias_kt = fps * 0.592484
        t.vs_fpm = state.get("velocities_h_dot_fps", 0.0) * 60.0
        if "velocities_h_dot_fps" not in state:
            t.vs_fpm = -state.get("velocities_w_fps", 0.0) * 60.0
        return t

    def _fill_from_simulation(self, t: TelemetrySnapshot) -> TelemetrySnapshot:
        if self._env is None:
            return t
        try:
            from jsbgym import properties as prp

            unwrapped = self._env.unwrapped
            sim = getattr(unwrapped, "sim", None)
            if sim is None:
                return t

            t.alt_ft = float(sim[prp.altitude_sl_ft])
            t.heading_deg = float(sim[prp.heading_deg]) % 360.0
            t.yaw_deg = t.heading_deg
            t.pitch_deg = math.degrees(float(sim[prp.pitch_rad]))
            t.roll_deg = math.degrees(float(sim[prp.roll_rad]))
            t.lat_deg = float(sim[prp.lat_geod_deg])
            t.lon_deg = float(sim[prp.lng_geoc_deg])
            u = float(sim[prp.u_fps])
            v = float(sim[prp.v_fps])
            w = float(sim[prp.w_fps])
            fps = math.sqrt(u * u + v * v + w * w)
            t.ias_kt = fps * 0.592484
            t.vs_fpm = float(sim[prp.altitude_rate_fps]) * 60.0
            t.sim_time_s = self._resolve_sim_time_s(sim)
            n1 = read_engine_n1(sim)
            if n1 is not None:
                t.engine_n1 = n1
        except Exception:
            pass
        return t
