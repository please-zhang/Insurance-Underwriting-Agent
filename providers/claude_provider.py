"""Anthropic Claude provider."""

from __future__ import annotations

import asyncio
from typing import Any

from anthropic import AsyncAnthropic

from providers.base import LLMProvider, LLMResponse, ToolCall


class ClaudeProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 4096,
        timeout: int = 30,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.client = client or AsyncAnthropic(api_key=api_key, timeout=timeout)

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str = "",
    ) -> LLMResponse:
        response = await self._retry(
            lambda: self._create_message(messages=messages, system=system, tools=tools)
        )
        return self._to_llm_response(response)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
    ) -> str:
        response = await self._retry(
            lambda: self._create_message(messages=messages, system=system)
        )
        content = [
            block.text
            for block in getattr(response, "content", [])
            if getattr(block, "type", None) == "text"
        ]
        return "".join(content).strip()

    async def _create_message(self, **kwargs: Any) -> Any:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": kwargs["messages"],
        }
        if kwargs.get("system"):
            payload["system"] = kwargs["system"]
        if kwargs.get("tools") is not None:
            payload["tools"] = kwargs["tools"]

        async with asyncio.timeout(self.timeout):
            return await self.client.messages.create(**payload)

    async def _retry(self, operation: Any) -> Any:
        delays = (1, 2, 4)
        last_error: Exception | None = None

        for attempt, delay in enumerate(delays, start=1):
            try:
                return await operation()
            except Exception as exc:
                last_error = exc
                if attempt == len(delays):
                    break
                await asyncio.sleep(delay)

        raise RuntimeError("Claude provider request failed after retries") from last_error

    def _to_llm_response(self, response: Any) -> LLMResponse:
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in getattr(response, "content", []):
            block_type = getattr(block, "type", None)
            if block_type == "text":
                content_parts.append(getattr(block, "text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=getattr(block, "id", ""),
                        name=getattr(block, "name", ""),
                        arguments=getattr(block, "input", {}) or {},
                    )
                )

        usage = {}
        usage_obj = getattr(response, "usage", None)
        if usage_obj is not None:
            usage = {
                "input_tokens": getattr(usage_obj, "input_tokens", None),
                "output_tokens": getattr(usage_obj, "output_tokens", None),
            }

        return LLMResponse(
            content="".join(content_parts).strip() or None,
            tool_calls=tool_calls or None,
            stop_reason=getattr(response, "stop_reason", "end_turn"),
            usage=usage,
        )
