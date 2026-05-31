"""Singleton AICoreService holder for FastAPI."""

from __future__ import annotations

import logging
import os

from skymind_core.service.ai_core import AICoreService

logger = logging.getLogger(__name__)

_service: AICoreService | None = None


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def use_mock_planner() -> bool:
    """Real LeWM by default; set SKYMIND_MOCK_PLANNER=1 to force mock."""
    return _env_flag("SKYMIND_MOCK_PLANNER", default=False)


def init_service(*, mock_planner: bool | None = None, use_keyboard: bool = False) -> AICoreService:
    global _service
    if mock_planner is None:
        mock_planner = use_mock_planner()

    llm = None
    try:
        from skymind_llm.orchestrator import LLMOrchestrator

        llm = LLMOrchestrator()
    except Exception:
        pass

    device = os.environ.get("SKYMIND_PLANNER_DEVICE", "cpu")
    _service = AICoreService(
        mock_planner=mock_planner,
        use_keyboard=use_keyboard,
        llm_orchestrator=llm,
        planner_device=device,
    )
    backend = "mock LeWM" if mock_planner else "real LeWM checkpoint"
    logger.info("Planner backend: %s (device=%s)", backend, device)
    return _service


def get_service() -> AICoreService:
    if _service is None:
        return init_service()
    return _service


async def shutdown_service() -> dict:
    global _service
    if _service is None:
        return {}
    summary = await _service.stop_session()
    _service = None
    return summary
