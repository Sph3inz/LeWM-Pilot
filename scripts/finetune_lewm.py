#!/usr/bin/env python3
"""Fine-tune LeWM on Parquet flight sessions (Weeks 11–12)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
import yaml
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skymind_core.lewm.dataset import LeWMDataset
from skymind_core.lewm.engine import LeWMEngine


def _collate(batch: list[dict]) -> dict[str, torch.Tensor]:
    return {
        "obs": torch.stack([torch.as_tensor(b["obs"]) for b in batch]),
        "action": torch.stack([torch.as_tensor(b["action"]) for b in batch]),
        "env": torch.stack([torch.as_tensor(b["env"]) for b in batch]),
        "next_obs": torch.stack([torch.as_tensor(b["next_obs"]) for b in batch]),
    }


def _eval_mse(engine: LeWMEngine, loader: DataLoader) -> float:
    engine.eval_mode()
    total = 0.0
    count = 0
    with torch.no_grad():
        for batch in loader:
            obs = batch["obs"].to(engine.device)
            action = batch["action"].to(engine.device)
            env = batch["env"].to(engine.device)
            next_obs = batch["next_obs"].to(engine.device)
            latent = engine.model.encode(obs)
            pred = engine.model.predict(latent, action, env)
            target = engine.model.encode(next_obs)
            total += torch.nn.functional.mse_loss(pred, target, reduction="sum").item()
            count += obs.size(0)
    return total / max(count, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune LeWM on flight data")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "lewm_finetune.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--epochs", type=int, default=None)
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if args.device:
        device = args.device
    elif cfg.get("device"):
        device = cfg["device"]
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    epochs = args.epochs or int(cfg.get("epochs", 20))
    batch_size = int(cfg.get("batch_size", 64))
    lr = float(cfg.get("lr", 1e-4))
    freeze_epochs = int(cfg.get("freeze_encoder_epochs", 1))
    patience = int(cfg.get("early_stop_patience", 3))
    lance_root = ROOT / cfg.get("lance_root", "data/lance/sessions")
    manifest_paths = [ROOT / p for p in cfg.get("train_manifests", [])]

    engine = LeWMEngine(device=device)
    train_ds, val_ds = LeWMDataset.from_manifests(
        manifest_paths,
        lance_root,
        val_fraction=float(cfg.get("val_fraction", 0.15)),
        max_train_samples=cfg.get("max_train_samples"),
        max_val_samples=cfg.get("max_val_samples"),
    )
    print(f"Train samples: {len(train_ds)}, Val samples: {len(val_ds)}")

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=_collate,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=_collate,
    )

    optimizer = torch.optim.AdamW(engine.model.parameters(), lr=lr)
    best_mse = float("inf")
    stale = 0
    out_path = ROOT / cfg.get("output_checkpoint", "checkpoints/lewm_flight_v1.pt")

    for epoch in range(epochs):
        if epoch < freeze_epochs:
            for p in engine.model.encoder.parameters():
                p.requires_grad = False
        else:
            for p in engine.model.encoder.parameters():
                p.requires_grad = True

        engine.train_mode()
        epoch_loss = 0.0
        n_batches = 0
        for batch in train_loader:
            obs = batch["obs"].to(engine.device)
            action = batch["action"].to(engine.device)
            env = batch["env"].to(engine.device)
            next_obs = batch["next_obs"].to(engine.device)

            optimizer.zero_grad()
            latent = engine.model.encode(obs)
            pred = engine.model.predict(latent, action, env)
            target = engine.model.encode(next_obs).detach()
            loss = torch.nn.functional.mse_loss(pred, target)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            n_batches += 1

        val_mse = _eval_mse(engine, val_loader)
        avg_loss = epoch_loss / max(n_batches, 1)
        print(f"Epoch {epoch + 1}/{epochs} train_loss={avg_loss:.6f} val_mse={val_mse:.6f}")

        if val_mse < best_mse:
            best_mse = val_mse
            stale = 0
            engine.save_checkpoint(out_path, metadata={"val_mse": val_mse, "epoch": epoch + 1})
            print(f"  Saved checkpoint -> {out_path}")
        else:
            stale += 1
            if stale >= patience:
                print(f"Early stop at epoch {epoch + 1}")
                break

    print(f"Fine-tune complete. Best val MSE: {best_mse:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
