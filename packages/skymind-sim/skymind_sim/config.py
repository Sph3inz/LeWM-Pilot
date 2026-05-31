"""Load YAML simulation config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_sim_config(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        path = Path(__file__).resolve().parents[3] / "configs" / "sim.yaml"
    path = Path(path)
    if not path.exists():
        return {
            "sim_hz": 10,
            "aircraft_id": "c172",
            "jsbgym_env_id": None,
            "initial_alt_ft": 3000,
            "initial_heading_deg": 270,
            "lance_root": "data/lance/sessions",
        }
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
