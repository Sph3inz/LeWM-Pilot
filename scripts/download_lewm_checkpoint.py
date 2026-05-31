#!/usr/bin/env python3
"""Download optional HuggingFace LeWM base checkpoint (best-effort)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Download LeWM HF checkpoint")
    parser.add_argument(
        "--repo",
        default="quentinll/lewm-reacher",
        help="HuggingFace model repo",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "checkpoints" / "lewm_base.pt",
    )
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("huggingface_hub not installed; skipping HF download.")
        print("LeWM will use random init and fine-tune on flight data.")
        return 0

    try:
        path = hf_hub_download(repo_id=args.repo, filename="weights.pt")
        import shutil

        shutil.copy(path, args.out)
        print(f"Downloaded weights to {args.out}")
        print(
            "Note: flight-state encoder uses random init; "
            "Predictor may not load HF weights (ViT vs MLP mismatch)."
        )
    except Exception as exc:
        print(f"HF download failed ({exc}); using random init for fine-tune.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
