"""GLM4 provider over an OpenAI-compatible API."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openai import AsyncOpenAI

from providers.base import LLMProvider, LLMResponse, ToolCall


class GLM4Provider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_tokens: int = 2048,
        timeout: int = 60,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.client = client or AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str = "",
    ) -> LLMResponse:
        try:
            response = await self._create_completion(
                messages=self._prepend_system(messages, system),
                tools=self._to_openai_tools(tools),
            )
            return self._to_llm_response(response)
        except Exception:
            fallback_messages = self._build_fallback_messages(messages, tools, system)
            response = await self._retry(
                lambda: self._create_completion(messages=fallback_messages)
            )
            parsed = self._to_llm_response(response)
            parsed.tool_calls = None
            return parsed

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
    ) -> str:
        response = await self._retry(
            lambda: self._create_completion(messages=self._prepend_system(messages, system))
        )
        parsed = self._to_llm_response(response)
        return parsed.content or ""

    async def _create_completion(self, **kwargs: Any) -> Any:
        payload = {
            "model": self.model,
            "messages": kwargs["messages"],
            "max_tokens": self.max_tokens,
        }
        if kwargs.get("tools") is not None:
            payload["tools"] = kwargs["tools"]

        async with asyncio.timeout(self.timeout):
            return await self.client.chat.completions.create(**payload)

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

        raise RuntimeError("GLM4 provider request failed after retries") from last_error

    def _prepend_system(
        self,
        messages: list[dict[str, Any]],
        system: str,
    ) -> list[dict[str, Any]]:
        if not system:
            return messages
        return [{"role": "system", "content": system}, *messages]

    def _to_openai_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in tools
        ]

    def _build_fallback_messages(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
    ) -> list[dict[str, Any]]:
        tool_descriptions = "\n".join(
            f"- {tool['name']}: {tool['description']} | schema={json.dumps(tool['input_schema'], ensure_ascii=False)}"
            for tool in tools
        )
        fallback_system = (
            f"{system}\n\n可用工具如下，请在无法原生调用工具时参考其能力进行推理：\n"
            f"{tool_descriptions}\n\n"
            "如果需要工具，请在文本中清晰说明所需工具和参数；否则直接给出结论。"
        ).strip()
        return self._prepend_system(messages, fallback_system)

    def _to_llm_response(self, response: Any) -> LLMResponse:
        choice = response.choices[0]
        message = choice.message
        tool_calls: list[ToolCall] = []

        for tool_call in getattr(message, "tool_calls", []) or []:
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=getattr(tool_call, "id", ""),
                    name=tool_call.function.name,
                    arguments=arguments,
                )
            )

        usage_obj = getattr(response, "usage", None)
        usage = usage_obj.model_dump() if usage_obj is not None else {}

        return LLMResponse(
            content=(getattr(message, "content", None) or "").strip() or None,
            tool_calls=tool_calls or None,
            stop_reason=getattr(choice, "finish_reason", "stop"),
            usage=usage,
        )
