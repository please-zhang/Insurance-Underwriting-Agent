"""Abstract interfaces shared by LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] | None
    stop_reason: str
    usage: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str = "",
    ) -> LLMResponse:
        """Send a message with available tools."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
    ) -> str:
        """Send a plain chat message."""
