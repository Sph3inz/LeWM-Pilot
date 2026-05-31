"""Extract JSON from LLM responses (reasoning blocks, markdown fences)."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_text(text: str) -> str:
    """Strip reasoning tags and markdown fences; return JSON substring."""
    cleaned = text.strip()
    cleaned = re.sub(r"<reasoning>.*?</reasoning>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        return fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def parse_json_object(text: str) -> dict[str, Any]:
    raw = extract_json_text(text)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data
