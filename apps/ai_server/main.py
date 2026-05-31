"""SkyMind AI server — FastAPI + WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from skymind_llm.env import load_dotenv

load_dotenv()

from ai_server.core_holder import get_service, init_service, shutdown_service

logger = logging.getLogger(__name__)

_active_ws: WebSocket | None = None
_broadcast_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_service(use_keyboard=False)
    yield
    await shutdown_service()


app = FastAPI(title="SkyMind AI Server", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    svc = get_service()
    return {
        "status": "ok",
        "session_state": svc.state.value,
        "planner_backend": svc.planner_backend,
        "planner_device": svc.planner_device,
    }


@app.post("/session/start")
async def session_start(body: dict[str, Any] | None = None) -> dict[str, str]:
    svc = get_service()
    session_id = await svc.start_session(body or {})
    global _broadcast_task
    if _broadcast_task is None or _broadcast_task.done():
        _broadcast_task = asyncio.create_task(_run_broadcast())
    return {"session_id": session_id}


@app.post("/session/stop")
async def session_stop() -> dict:
    return await shutdown_service()


_listener_registered = False


async def _run_broadcast() -> None:
    global _listener_registered
    svc = get_service()

    if not _listener_registered:
        def on_frame(frame) -> None:
            ws = _active_ws
            if ws is None:
                return
            payload = frame.model_dump()
            asyncio.create_task(_safe_send(ws, payload))

        svc.add_frame_listener(on_frame)
        _listener_registered = True

    try:
        await svc.run_broadcast_loop()
    except asyncio.CancelledError:
        pass


async def _safe_send(ws: WebSocket, payload: dict) -> None:
    try:
        await ws.send_json(payload)
    except Exception:
        pass


@app.websocket("/ws/session")
async def ws_session(websocket: WebSocket) -> None:
    global _active_ws, _broadcast_task
    if _active_ws is not None:
        await websocket.close(code=4008, reason="Only one client allowed")
        return

    await websocket.accept()
    _active_ws = websocket
    svc = get_service()

    if svc.state.value == "idle":
        await svc.start_session({})
        if _broadcast_task is None or _broadcast_task.done():
            _broadcast_task = asyncio.create_task(_run_broadcast())

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            await _handle_upstream(msg)
    except WebSocketDisconnect:
        pass
    finally:
        _active_ws = None


async def _handle_upstream(msg: dict) -> None:
    svc = get_service()
    msg_type = msg.get("type", "")
    if msg_type == "vibe_prompt":
        scenario_id = await svc.handle_vibe_prompt(msg.get("text", ""))
        if _active_ws:
            await _active_ws.send_json({"type": "scenario_loaded", "scenario_id": scenario_id})
    elif msg_type == "manual_failure":
        await svc.handle_manual_failure(msg.get("failure_id", "engine_failure"), msg.get("params"))
    elif msg_type == "pause":
        await svc.pause()
    elif msg_type == "resume":
        await svc.resume()
    elif msg_type == "reset_scenario":
        await svc.reset_scenario()
    elif msg_type == "set_control_mode":
        svc.set_control_mode(msg.get("mode", "autopilot"))
