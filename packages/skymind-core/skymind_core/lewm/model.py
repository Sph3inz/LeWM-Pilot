"""LeWM StateEncoder and Predictor models."""

from __future__ import annotations

import torch
import torch.nn as nn

from skymind_core.lewm.state_vector import ACTION_DIM, ENV_DIM, LATENT_DIM, STATE_DIM


class StateEncoder(nn.Module):
    def __init__(self, input_dim: int = STATE_DIM, latent_dim: int = LATENT_DIM) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.GELU(),
            nn.Linear(256, latent_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class Predictor(nn.Module):
    def __init__(
        self,
        latent_dim: int = LATENT_DIM,
        action_dim: int = ACTION_DIM,
        env_dim: int = ENV_DIM,
        n_layers: int = 4,
    ) -> None:
        super().__init__()
        input_dim = latent_dim + action_dim + env_dim
        self.input_proj = nn.Linear(input_dim, latent_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=latent_dim,
            nhead=4,
            dim_feedforward=512,
            batch_first=True,
            activation="gelu",
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.output_proj = nn.Linear(latent_dim, latent_dim)

    def forward(self, latent: torch.Tensor, action: torch.Tensor, env: torch.Tensor) -> torch.Tensor:
        x = torch.cat([latent, action, env], dim=-1)
        x = self.input_proj(x).unsqueeze(1)
        x = self.transformer(x).squeeze(1)
        return self.output_proj(x)


class LeWMModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = StateEncoder()
        self.predictor = Predictor()

    def encode(self, obs: torch.Tensor) -> torch.Tensor:
        return self.encoder(obs)

    def predict(self, latent: torch.Tensor, action: torch.Tensor, env: torch.Tensor) -> torch.Tensor:
        return self.predictor(latent, action, env)

    def forward(
        self,
        obs: torch.Tensor,
        action: torch.Tensor,
        env: torch.Tensor,
        next_obs: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        latent = self.encode(obs)
        pred = self.predict(latent, action, env)
        target = self.encode(next_obs) if next_obs is not None else None
        return pred, target
