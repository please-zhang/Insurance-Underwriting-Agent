from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import providers
from providers import get_provider
from providers.claude_provider import ClaudeProvider
from providers.glm4_provider import GLM4Provider


@dataclass
class FakeClaudeBlock:
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict | None = None


class FakeClaudeMessages:
    def __init__(self, response):
        self.response = response

    async def create(self, **kwargs):
        return self.response


class FakeClaudeClient:
    def __init__(self, response):
        self.messages = FakeClaudeMessages(response)


class FakeGLMCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeGLMClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeGLMCompletions(responses))


@pytest.mark.asyncio
async def test_claude_provider_chat():
    response = SimpleNamespace(
        content=[FakeClaudeBlock(type="text", text="plain response")],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )
    provider = ClaudeProvider(
        api_key="test",
        model="claude-test",
        client=FakeClaudeClient(response),
    )

    result = await provider.chat(messages=[{"role": "user", "content": "hello"}])

    assert result == "plain response"


@pytest.mark.asyncio
async def test_claude_provider_tool_use():
    response = SimpleNamespace(
        content=[
            FakeClaudeBlock(type="text", text="checking"),
            FakeClaudeBlock(
                type="tool_use",
                id="tool-1",
                name="rule_checker",
                input={"age": 45},
            ),
        ],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=15, output_tokens=30),
    )
    provider = ClaudeProvider(
        api_key="test",
        model="claude-test",
        client=FakeClaudeClient(response),
    )

    result = await provider.chat_with_tools(
        messages=[{"role": "user", "content": "check"}],
        tools=[
            {
                "name": "rule_checker",
                "description": "check rules",
                "input_schema": {"type": "object"},
            }
        ],
    )

    assert result.stop_reason == "tool_use"
    assert result.content == "checking"
    assert result.tool_calls is not None
    assert result.tool_calls[0].name == "rule_checker"
    assert result.tool_calls[0].arguments == {"age": 45}


@pytest.mark.asyncio
async def test_glm4_provider_fallback():
    fallback_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="fallback answer", tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(model_dump=lambda: {"total_tokens": 42}),
    )
    fake_client = FakeGLMClient([RuntimeError("tool not supported"), fallback_response])
    provider = GLM4Provider(
        base_url="http://glm4.test",
        api_key="none",
        model="glm-4",
        client=fake_client,
    )

    result = await provider.chat_with_tools(
        messages=[{"role": "user", "content": "need review"}],
        tools=[
            {
                "name": "doc_retriever",
                "description": "fetch docs",
                "input_schema": {"type": "object"},
            }
        ],
        system="system prompt",
    )

    assert result.content == "fallback answer"
    assert result.tool_calls is None
    assert len(fake_client.chat.completions.calls) == 2
    assert "可用工具如下" in fake_client.chat.completions.calls[-1]["messages"][0]["content"]


def test_get_provider_from_config(tmp_path, monkeypatch):
    config_path = tmp_path / "providers.yaml"
    config_path.write_text(
        "\n".join(
            [
                "active_provider: claude",
                "claude:",
                "  api_key: ${ANTHROPIC_API_KEY}",
                "  model: claude-test",
                "  max_tokens: 1024",
                "  timeout: 12",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-key")

    provider = get_provider(str(config_path))

    assert isinstance(provider, ClaudeProvider)
    assert provider.api_key == "secret-key"
    assert provider.max_tokens == 1024


def test_get_provider_override_name(tmp_path):
    config_path = tmp_path / "providers.yaml"
    config_path.write_text(
        "\n".join(
            [
                "active_provider: claude",
                "claude:",
                "  api_key: test-1",
                "  model: claude-test",
                "  max_tokens: 1024",
                "  timeout: 12",
                "glm4:",
                "  base_url: http://glm4.test/v1",
                "  api_key: none",
                "  model: glm-4",
                "  max_tokens: 2048",
                "  timeout: 60",
            ]
        ),
        encoding="utf-8",
    )

    provider = providers.get_provider(str(config_path), provider_name="glm4")

    assert isinstance(provider, GLM4Provider)
