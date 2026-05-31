"""LeWMEngine — encode, predict, checkpoint I/O."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch

from skymind_core.lewm.model import LeWMModel
from skymind_core.lewm.state_vector import LATENT_DIM


class LeWMEngine:
    """State-vector LeWM for flight dynamics latent prediction."""

    def __init__(self, device: str | None = None) -> None:
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = LeWMModel().to(self.device)
        self.model.eval()

    def encode(self, obs: np.ndarray) -> np.ndarray:
        x = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        if x.ndim == 1:
            x = x.unsqueeze(0)
        with torch.no_grad():
            latent = self.model.encode(x)
        return latent.squeeze(0).cpu().numpy().astype(np.float32)

    def predict(self, latent: np.ndarray, action: np.ndarray, env: np.ndarray) -> np.ndarray:
        z = torch.as_tensor(latent, dtype=torch.float32, device=self.device)
        a = torch.as_tensor(action, dtype=torch.float32, device=self.device)
        e = torch.as_tensor(env, dtype=torch.float32, device=self.device)
        if z.ndim == 1:
            z, a, e = z.unsqueeze(0), a.unsqueeze(0), e.unsqueeze(0)
        with torch.no_grad():
            out = self.model.predict(z, a, e)
        return out.squeeze(0).cpu().numpy().astype(np.float32)

    def load_checkpoint(self, path: str | Path) -> None:
        data = torch.load(path, map_location=self.device, weights_only=False)
        if isinstance(data, dict) and "model_state_dict" in data:
            self.model.load_state_dict(data["model_state_dict"])
        else:
            self.model.load_state_dict(data)
        self.model.eval()

    def save_checkpoint(self, path: str | Path, metadata: dict[str, Any] | None = None) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "model_state_dict": self.model.state_dict(),
            "latent_dim": LATENT_DIM,
        }
        if metadata:
            payload["metadata"] = metadata
        torch.save(payload, path)

    @property
    def torch_model(self) -> LeWMModel:
        return self.model

    def train_mode(self) -> None:
        self.model.train()

    def eval_mode(self) -> None:
        self.model.eval()
