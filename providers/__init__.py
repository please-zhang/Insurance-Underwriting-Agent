"""LLM provider factory."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from providers.base import LLMProvider
from providers.claude_provider import ClaudeProvider
from providers.glm4_provider import GLM4Provider


def get_provider(
    config_path: str = "config/providers.yaml",
    provider_name: str | None = None,
) -> LLMProvider:
    path = Path(config_path)
    config = _load_config(path)
    active_provider = provider_name or config["active_provider"]
    provider_config = config[active_provider]

    if active_provider == "claude":
        return ClaudeProvider(**provider_config)
    if active_provider == "glm4":
        return GLM4Provider(**provider_config)
    if active_provider == "openai":
        raise NotImplementedError("OpenAIProvider 尚未实现。")

    raise ValueError(f"Unsupported provider: {active_provider}")


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Provider config not found: {path}")

    raw = path.read_text(encoding="utf-8")
    expanded = _expand_env_vars(raw)
    data = yaml.safe_load(expanded)
    if not isinstance(data, dict):
        raise ValueError("Provider config must be a mapping")
    return data


def _expand_env_vars(raw: str) -> str:
    pattern = re.compile(r"\$\{([A-Z0-9_]+)\}")

    def replacer(match: re.Match[str]) -> str:
        return os.getenv(match.group(1), "")

    return pattern.sub(replacer, raw)
