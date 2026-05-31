"""AICoreService — orchestrates sim, profiler, planner, LLM, telemetry."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal

from skymind_core.lewm.engine import LeWMEngine
from skymind_core.lewm.state_vector import frame_to_obs
from skymind_core.orchestrator.orchestrator import ScenarioOrchestrator
from skymind_core.planner.lewm_backend import RealLeWMBackend
from skymind_core.planner.mock_lewm import MockLeWMEngine
from skymind_core.planner.planner import Planner
from skymind_core.profiler.skill_profiler import SkillProfiler
from skymind_core.service.adaptation_log import AdaptationLog
from skymind_core.service.telemetry_frame import TelemetryFrame, build_telemetry_frame
from skymind_sim.adapter import SimulatorAdapter
from skymind_sim.autopilot import HoldHeadingAltitudePID
from skymind_sim.keyboard import KeyboardPilot, NullKeyboardPilot
from skymind_sim.models import EnvironmentState, ScenarioConfig, TelemetrySnapshot

logger = logging.getLogger(__name__)

ControlMode = Literal["human_keyboard", "autopilot"]


class SessionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


class AICoreService:
    """Wire sim thread + adaptive AI modules; emit TelemetryFrames."""

    def __init__(
        self,
        *,
        sim_hz: float = 10.0,
        broadcast_hz: float = 20.0,
        mock_planner: bool = True,
        checkpoint_path: Path | None = None,
        planner_device: str = "cpu",
        llm_orchestrator: Any | None = None,
        use_keyboard: bool = False,
    ) -> None:
        self.sim_hz = sim_hz
        self.broadcast_hz = broadcast_hz
        self._state = SessionState.IDLE
        self._adapter: SimulatorAdapter | None = None
        self._profiler = SkillProfiler()
        self._orchestrator = ScenarioOrchestrator()
        self._adapt_log = AdaptationLog()
        self._planner: Planner | None = None
        self._llm = llm_orchestrator
        self._session_id: str | None = None
        self._control_mode: ControlMode = "autopilot"
        self._autopilot = HoldHeadingAltitudePID(target_ias_kt=100.0, target_alt_ft=5000.0)
        self._keyboard = KeyboardPilot() if use_keyboard else NullKeyboardPilot()
        self._telemetry_queue: queue.Queue[TelemetrySnapshot] = queue.Queue(maxsize=8)
        self._sim_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_profiler_s = -1e9
        self._last_plan_s = -1e9
        self._last_score = 0.5
        self._last_band = "moderate"
        self._cmd_target = {"ias_cmd": 100.0, "alt_cmd": 5000.0}
        self._scenario_doc: dict | None = None
        self._listeners: list[Callable[[TelemetryFrame], None]] = []
        self._mock_planner = mock_planner
        self._checkpoint_path = checkpoint_path or repo_root() / "checkpoints" / "lewm_flight_v1.pt"
        self._planner_device = planner_device
        self._planner_backend = self._resolve_planner_backend()

    @property
    def planner_backend(self) -> str:
        """Active or configured planner: ``lewm`` or ``mock``."""
        if self._planner is not None:
            return self._planner_backend
        return self._resolve_planner_backend()

    @property
    def planner_device(self) -> str:
        return self._planner_device

    def _resolve_planner_backend(self) -> str:
        if self._mock_planner or not self._checkpoint_path.is_file():
            return "mock"
        return "lewm"

    def add_frame_listener(self, callback: Callable[[TelemetryFrame], None]) -> None:
        self._listeners.append(callback)

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def session_id(self) -> str | None:
        return self._session_id

    async def start_session(self, config: dict | None = None) -> str:
        config = config or {}
        scenario_path = config.get("scenario_path")
        if scenario_path:
            with Path(scenario_path).open(encoding="utf-8") as fh:
                doc = json.load(fh)
        elif config.get("scenario"):
            doc = config["scenario"]
        elif self._llm and config.get("vibe_prompt"):
            doc = await asyncio.to_thread(
                self._llm.generate_scenario, config["vibe_prompt"], config.get("context", {})
            )
            self._adapt_log.log_llm(0.0, doc.get("scenario_id", "generated"))
        else:
            fallback = repo_root() / "configs" / "scenarios" / "demo_long_adaptive.json"
            with fallback.open(encoding="utf-8") as fh:
                doc = json.load(fh)

        self._scenario_doc = doc
        timeline = self._orchestrator.load_scenario(doc)
        env_initial = timeline.environment_initial
        aircraft_id = timeline.aircraft_id
        self._cmd_target = {
            "ias_cmd": float(config.get("ias_cmd", 100.0)),
            "alt_cmd": float(config.get("alt_cmd", env_initial.get("alt_ft", 5000.0))),
        }

        self._adapter = SimulatorAdapter(sim_hz=self.sim_hz, aircraft_id=aircraft_id)
        scenario_cfg = ScenarioConfig(
            aircraft_id=aircraft_id,
            episode_time_s=float(config.get("episode_time_s", 1380.0)),
            environment=EnvironmentState(**env_initial),
        )
        self._session_id = self._adapter.reset(scenario_cfg)
        self._autopilot = HoldHeadingAltitudePID(
            target_ias_kt=self._cmd_target["ias_cmd"],
            target_alt_ft=self._cmd_target["alt_cmd"],
        )
        self._init_planner()
        self._last_profiler_s = -1e9
        self._last_plan_s = -1e9
        self._stop_event.clear()
        self._state = SessionState.RUNNING
        self._sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
        self._sim_thread.start()
        return self._session_id

    def _init_planner(self) -> None:
        if self._mock_planner:
            backend = MockLeWMEngine()
            self._planner_backend = "mock"
            logger.info("Planner using mock LeWM (SKYMIND_MOCK_PLANNER=1)")
        elif not self._checkpoint_path.is_file():
            backend = MockLeWMEngine()
            self._planner_backend = "mock"
            logger.warning(
                "LeWM checkpoint missing at %s — falling back to mock planner",
                self._checkpoint_path,
            )
        else:
            engine = LeWMEngine(device=self._planner_device)
            engine.load_checkpoint(self._checkpoint_path)
            backend = RealLeWMBackend(engine)
            self._planner_backend = "lewm"
            logger.info(
                "Planner using real LeWM from %s on %s",
                self._checkpoint_path,
                self._planner_device,
            )
        self._planner = Planner(backend=backend)

    async def stop_session(self) -> dict:
        self._state = SessionState.STOPPED
        self._stop_event.set()
        if self._sim_thread and self._sim_thread.is_alive():
            self._sim_thread.join(timeout=5.0)
        if self._adapter:
            self._adapter.close()
        self._keyboard.close()
        summary = {
            "session_id": self._session_id,
            "final_score": self._last_score,
            "timeline": self._orchestrator.get_timeline_view(),
        }
        self._adapter = None
        self._session_id = None
        return summary

    async def pause(self) -> None:
        self._state = SessionState.PAUSED

    async def resume(self) -> None:
        if self._adapter is not None:
            self._state = SessionState.RUNNING

    async def handle_vibe_prompt(self, text: str) -> str:
        if self._llm is None:
            raise RuntimeError("LLM orchestrator not configured")
        doc = await asyncio.to_thread(self._llm.generate_scenario, text, {})
        self._orchestrator.load_scenario(doc)
        self._scenario_doc = doc
        self._adapt_log.log_llm(
            self._adapter.get_telemetry().sim_time_s if self._adapter else 0.0,
            doc.get("scenario_id", "generated"),
        )
        return doc.get("scenario_id", "generated")

    async def handle_manual_failure(self, failure_id: str, params: dict | None = None) -> None:
        if not self._adapter:
            return
        self._adapter.inject_failure(failure_id, params)
        self._profiler.on_failure_injected(failure_id, self._adapter.get_telemetry().sim_time_s)
        self._adapt_log.log_instructor(
            self._adapter.get_telemetry().sim_time_s,
            f"Manual failure injected: {failure_id}",
        )

    async def reset_scenario(self) -> None:
        if self._scenario_doc:
            self._orchestrator.load_scenario(self._scenario_doc)

    def set_control_mode(self, mode: ControlMode) -> None:
        self._control_mode = mode
        if self._adapter:
            self._adapter.set_control_mode(mode)

    def _sim_loop(self) -> None:
        assert self._adapter is not None
        assert self._planner is not None
        step_interval = 1.0 / self.sim_hz
        while not self._stop_event.is_set():
            if self._state != SessionState.RUNNING:
                time.sleep(0.05)
                continue
            telem = self._adapter.get_telemetry()
            if self._control_mode == "autopilot":
                action = self._autopilot.compute(telem)
            else:
                action = self._keyboard.poll()
                self._cmd_target["feather_pressed"] = self._keyboard.feather_pressed()

            telem, done = self._adapter.step(action)
            sim_time = telem.sim_time_s

            if sim_time - self._last_profiler_s >= 5.0:
                state = self._profiler.update(telem, self._cmd_target)
                self._last_score = state.score
                self._last_band = state.band
                signal = self._profiler.get_adaptation_signal()
                self._orchestrator.set_profiler_score(state.score)
                self._orchestrator.apply_adaptation(signal)
                self._adapt_log.log_profiler(sim_time, state, signal)
                self._last_profiler_s = sim_time

            cmds = self._orchestrator.tick(sim_time)
            for cmd in cmds:
                if cmd.kind == "failure":
                    fid = cmd.params.get("failure_id", "engine_failure")
                    self._adapter.inject_failure(fid, cmd.params)
                    self._profiler.on_failure_injected(fid, sim_time)
                    if fid == "engine_failure":
                        self._autopilot.set_engine_out(True)
                elif cmd.kind == "environment":
                    env_dict = cmd.params.get("environment", {})
                    self._adapter.set_environment(EnvironmentState(**env_dict))

            if self._planner.should_replan(self._last_score, sim_time, self._last_plan_s):
                frame = telem.to_frame_dict(action)
                latent = self._planner.encode_obs(frame_to_obs(frame))
                target = min(0.7, max(0.4, self._last_score))
                delta = self._planner.inverse_plan(
                    latent,
                    target_score=target,
                    current_env=self._adapter.get_environment(),
                )
                self._planner.apply_delta(delta, self._adapter)
                self._adapt_log.log_planner(sim_time, target, delta)
                self._last_plan_s = sim_time

            try:
                self._telemetry_queue.put_nowait(telem)
            except queue.Full:
                try:
                    self._telemetry_queue.get_nowait()
                except queue.Empty:
                    pass
                self._telemetry_queue.put_nowait(telem)

            if done and self._adapter._config:
                self._adapter.reset_episode(self._adapter._config)

            time.sleep(step_interval)

    async def run_broadcast_loop(self) -> None:
        """Async loop: drain telemetry queue and notify listeners at broadcast_hz."""
        interval = 1.0 / self.broadcast_hz
        while self._state in (SessionState.RUNNING, SessionState.PAUSED):
            telem: TelemetrySnapshot | None = None
            try:
                while True:
                    telem = self._telemetry_queue.get_nowait()
            except queue.Empty:
                pass

            if telem is not None and self._session_id:
                frame = build_telemetry_frame(
                    session_id=self._session_id,
                    telemetry=telem,
                    pilot_score=self._last_score,
                    score_band=self._last_band,
                    adaptation_log=self._adapt_log.snapshot(),
                    timeline_view=self._orchestrator.get_timeline_view(),
                )
                for listener in self._listeners:
                    listener(frame)

            await asyncio.sleep(interval)

    def build_status_frame(self) -> TelemetryFrame | None:
        if not self._adapter or not self._session_id:
            return None
        telem = self._adapter.get_telemetry()
        return build_telemetry_frame(
            session_id=self._session_id,
            telemetry=telem,
            pilot_score=self._last_score,
            score_band=self._last_band,
            adaptation_log=self._adapt_log.snapshot(),
            timeline_view=self._orchestrator.get_timeline_view(),
        )
