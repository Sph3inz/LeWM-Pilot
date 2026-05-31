#!/usr/bin/env python3
"""Launch SkyMind Phase 1 demo — AI server + dashboard instructions."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _python_executable() -> str:
    if VENV_PYTHON.is_file():
        return str(VENV_PYTHON)
    return sys.executable


def _build_env() -> dict[str, str]:
    _load_dotenv(ROOT / ".env")
    env = dict(os.environ)
    paths = [str(ROOT), str(APPS)]
    existing = env.get("PYTHONPATH", "")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def main() -> int:
    checkpoint = ROOT / "checkpoints" / "lewm_flight_v1.pt"
    parser = argparse.ArgumentParser(description="SkyMind demo launcher")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0")
    planner = parser.add_mutually_exclusive_group()
    planner.add_argument(
        "--real-planner",
        action="store_true",
        help="Use trained LeWM checkpoint (default when checkpoint exists)",
    )
    planner.add_argument(
        "--mock-planner",
        action="store_true",
        help="Use fake LeWM (faster, no torch checkpoint needed)",
    )
    parser.add_argument(
        "--planner-device",
        default="cpu",
        help="Torch device for real LeWM (cpu or cuda)",
    )
    args = parser.parse_args()

    py = _python_executable()
    if py != sys.executable:
        print(f"Using venv Python: {py}")
    elif not VENV_PYTHON.is_file():
        print("Warning: .venv not found — using current Python. Run setup from README first.")

    print("SkyMind Phase 1 Demo")
    print("=" * 40)
    print(f"Starting AI server on http://localhost:{args.port} ...")
    print()
    print("In another terminal:")
    print("  cd apps/dashboard")
    print("  npm run dev")
    print("  Open http://localhost:5173")
    print()
    env = _build_env()
    if args.mock_planner:
        use_mock = True
    elif args.real_planner:
        use_mock = False
    else:
        use_mock = not checkpoint.is_file()
    env["SKYMIND_MOCK_PLANNER"] = "1" if use_mock else "0"
    env["SKYMIND_PLANNER_DEVICE"] = args.planner_device

    if env.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY: loaded from .env")
    else:
        print("Warning: OPENROUTER_API_KEY not set — LLM will use fallback scenario")

    if use_mock:
        print("Planner: mock LeWM (pass --real-planner to use checkpoint)")
    elif checkpoint.is_file():
        print(f"Planner: real LeWM ({checkpoint.name}, device={args.planner_device})")
    else:
        print("Warning: checkpoint missing — planner will use mock at runtime")
    print("=" * 40)

    cmd = [
        py,
        "-m",
        "uvicorn",
        "ai_server.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
