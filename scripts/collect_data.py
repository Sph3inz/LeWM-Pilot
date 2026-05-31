#!/usr/bin/env python3
"""Collect flight telemetry via autopilot maneuver catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skymind_data.collection import AutopilotCollector
from skymind_sim.adapter import SimulatorAdapter
from skymind_sim.config import load_sim_config


def main() -> int:
    parser = argparse.ArgumentParser(description="SkyMind autopilot data collection")
    parser.add_argument("--aircraft", choices=["c172", "t6"], default="c172")
    parser.add_argument("--hours", type=float, default=10.0)
    parser.add_argument("--catalog", choices=["full", "basic"], default="full")
    parser.add_argument("--sim-hz", type=float, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--catalog-path", type=Path, default=None)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--manifest-name", type=str, default=None)
    parser.add_argument("--no-real-time", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.config is None:
        args.config = ROOT / "configs" / ("sim_t6.yaml" if args.aircraft == "t6" else "sim.yaml")
    if args.catalog_path is None:
        args.catalog_path = ROOT / "configs" / (
            "maneuver_catalog_t6.yaml" if args.aircraft == "t6" else "maneuver_catalog.yaml"
        )
    if args.manifest_name is None:
        args.manifest_name = (
            "collection_manifest_t6.json" if args.aircraft == "t6" else "collection_manifest.json"
        )

    cfg = load_sim_config(args.config)
    hz = args.sim_hz or float(cfg.get("sim_hz", 10))
    lance_root = args.data_root or Path(cfg.get("lance_root", "data/lance/sessions"))
    env_id = cfg.get("jsbgym_env_id")

    adapter = SimulatorAdapter(
        env_id=env_id,
        sim_hz=hz,
        aircraft_id=args.aircraft,
    )
    collector = AutopilotCollector(
        adapter=adapter,
        lance_root=lance_root,
        sim_hz=hz,
        real_time=not args.no_real_time,
    )

    print(
        f"Collecting {args.hours} hr ({args.catalog} catalog, {args.aircraft}) "
        f"@ {hz} Hz -> {lance_root}"
    )
    try:
        manifest = collector.run(
            hours=args.hours,
            catalog=args.catalog,
            aircraft_id=args.aircraft,
            catalog_path=args.catalog_path,
            resume=args.resume,
            manifest_name=args.manifest_name,
        )
    finally:
        adapter.close()

    manifest_path = lance_root.parent / args.manifest_name
    print(
        f"Collection complete: {manifest['total_hours']} hr, "
        f"{len(manifest['session_ids'])} sessions, "
        f"{manifest['failure_injections']} failures"
    )
    print(f"Manifest: {manifest_path}")
    return 0 if manifest["total_hours"] >= args.hours * 0.99 else 1


if __name__ == "__main__":
    raise SystemExit(main())
