"""LLMOrchestrator — generate and validate scenario JSON via OpenRouter."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import jsonschema
import os
import yaml
from pydantic import BaseModel, Field

from skymind_llm.json_extract import parse_json_object
from skymind_llm.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "openrouter",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "api_key_env": "OPENROUTER_API_KEY",
    "temperature": 0.2,
    "max_tokens": 4096,
    "timeout_s": 60,
    "retries": 2,
    "fallback_scenario": "configs/scenarios/demo_engine_out.json",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_llm_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else repo_root() / "configs" / "llm.yaml"
    merged = dict(_DEFAULT_CONFIG)
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            merged.update(yaml.safe_load(fh) or {})
    return merged


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class LLMOrchestrator:
    """Call OpenRouter to compile instructor prompts into scenario JSON."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        client: OpenRouterClient | None = None,
    ) -> None:
        self._cfg = load_llm_config(config_path)
        self._schema_path = repo_root() / "schemas" / "scenario.schema.json"
        with self._schema_path.open(encoding="utf-8") as fh:
            self._schema = json.load(fh)
        prompt_path = Path(__file__).parent / "prompts" / "scenario_compiler.md"
        self._system_prompt = prompt_path.read_text(encoding="utf-8")
        from skymind_llm.env import load_dotenv

        load_dotenv()
        key_env = str(self._cfg.get("api_key_env", "OPENROUTER_API_KEY"))
        api_key = os.environ.get(key_env, "")
        self._client = client or OpenRouterClient(
            api_key=api_key,
            base_url=str(self._cfg["base_url"]),
            model=str(self._cfg["model"]),
            timeout_s=float(self._cfg["timeout_s"]),
        )
        fallback = Path(str(self._cfg["fallback_scenario"]))
        if not fallback.is_absolute():
            fallback = repo_root() / fallback
        self._fallback_path = fallback

    def validate(self, doc: dict) -> ValidationResult:
        errors: list[str] = []
        try:
            jsonschema.validate(doc, self._schema)
        except jsonschema.ValidationError as exc:
            errors.append(str(exc.message))
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def load_fallback(self) -> dict:
        with self._fallback_path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def generate_scenario(self, prompt: str, context: dict | None = None) -> dict:
        context = context or {}
        retries = int(self._cfg.get("retries", 2))
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                doc = self._call_llm(prompt, context)
                result = self.validate(doc)
                if result.valid:
                    return doc
                logger.warning("LLM scenario invalid: %s", result.errors)
                last_error = ValueError("; ".join(result.errors))
            except Exception as exc:
                logger.warning("LLM attempt %s failed: %s", attempt + 1, exc)
                last_error = exc
        logger.info("Using fallback scenario after LLM failure: %s", last_error)
        return self.load_fallback()

    def _call_llm(self, prompt: str, context: dict) -> dict:
        user_parts = [prompt.strip()]
        if context:
            user_parts.append(f"Context: {json.dumps(context)}")
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]
        content = self._client.chat_completion(
            messages,
            temperature=float(self._cfg.get("temperature", 0.2)),
            max_tokens=int(self._cfg.get("max_tokens", 4096)),
        )
        return parse_json_object(content)

    def stream_response(self, prompt: str):
        """Optional generator — yields full response as single chunk for Phase 1."""
        yield self.generate_scenario(prompt)
