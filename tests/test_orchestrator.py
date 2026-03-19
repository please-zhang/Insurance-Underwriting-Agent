from __future__ import annotations

import asyncio
import json

import pytest

from agent.orchestrator import OrchestratorAgent
from agent.output.models import ApplicationInput
from agent.tools.base import BaseTool
from providers.base import LLMResponse, ToolCall


class MockProvider:
    def __init__(self, planning_response: LLMResponse, final_response: str = "") -> None:
        self.planning_response = planning_response
        self.final_response = final_response
        self.chat_with_tools_calls = 0
        self.chat_calls = 0

    async def chat_with_tools(self, messages, tools, system=""):
        self.chat_with_tools_calls += 1
        return self.planning_response

    async def chat(self, messages, system=""):
        self.chat_calls += 1
        return self.final_response


class RecordingTool(BaseTool):
    def __init__(self, name: str, result: dict, calls: list[str], delay: float = 0.0) -> None:
        self.name = name
        self.result = result
        self.calls = calls
        self.delay = delay
        self.description = f"{name} description"
        self.input_schema = {"type": "object"}

    async def execute(self, **kwargs):
        self.calls.append(self.name)
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.result


def _application_payload() -> dict:
    return {
        "application_id": "APP-2026-001",
        "applicant": {
            "age": 45,
            "gender": "male",
            "occupation": "office_worker",
            "smoking": False,
            "bmi": 24.5,
        },
        "health_conditions": [
            {
                "condition": "hypertension",
                "diagnosed_year": 2020,
                "controlled": True,
                "medication": "amlodipine",
            }
        ],
        "coverage": {
            "product_code": "LIFE-TERM-20",
            "coverage_amount": 500000,
            "coverage_period_years": 20,
            "premium_frequency": "annual",
        },
        "beneficiaries": [{"relationship": "spouse", "percentage": 100}],
    }


@pytest.mark.asyncio
async def test_process_standard_application():
    provider = MockProvider(
        planning_response=LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(id="1", name="rule_checker", arguments={}),
                ToolCall(id="2", name="doc_retriever", arguments={"query": "高血压承保条件"}),
                ToolCall(id="3", name="risk_scorer", arguments={}),
            ],
            stop_reason="tool_use",
            usage={},
        ),
        final_response=json.dumps(
            {
                "decision": "APPROVED_WITH_LOADING",
                "risk_level": "MEDIUM",
                "risk_score": 62,
                "reasons": ["高血压已受控，建议加费承保。"],
                "missing_info": [],
                "next_steps": ["补充最近 12 个月血压记录。"],
                "confidence": 0.88,
                "tool_calls_made": [],
                "processing_time_ms": 0,
            },
            ensure_ascii=False,
        ),
    )
    calls: list[str] = []
    tools = [
        RecordingTool(
            "rule_checker",
            {"rules_matched": [{"description": "高血压已受控", "impact": "negative"}], "violations": [], "hard_stops": []},
            calls,
        ),
        RecordingTool("doc_retriever", {"passages": [{"content": "高血压可加费承保"}]}, calls),
        RecordingTool(
            "risk_scorer",
            {"risk_score": 62, "risk_level": "MEDIUM", "factors": [], "score_breakdown": {}},
            calls,
        ),
    ]
    agent = OrchestratorAgent(provider=provider, tools=tools)

    result = await agent.process(_application_payload())

    assert result.decision == "APPROVED_WITH_LOADING"
    assert result.risk_level == "MEDIUM"
    assert result.tool_calls_made == ["rule_checker", "doc_retriever", "risk_scorer"]
    assert provider.chat_with_tools_calls == 1
    assert provider.chat_calls == 1


@pytest.mark.asyncio
async def test_process_hard_stop():
    provider = MockProvider(
        planning_response=LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(id="1", name="rule_checker", arguments={}),
                ToolCall(id="2", name="doc_retriever", arguments={"query": "糖尿病拒保"}),
                ToolCall(id="3", name="risk_scorer", arguments={}),
            ],
            stop_reason="tool_use",
            usage={},
        ),
    )
    calls: list[str] = []
    tools = [
        RecordingTool(
            "rule_checker",
            {
                "rules_matched": [],
                "violations": [],
                "hard_stops": [{"description": "糖尿病未受控时拒保。"}],
            },
            calls,
        ),
        RecordingTool("doc_retriever", {"passages": []}, calls),
        RecordingTool("risk_scorer", {"risk_score": 90, "risk_level": "HIGH"}, calls),
    ]
    agent = OrchestratorAgent(provider=provider, tools=tools)

    result = await agent.process(_application_payload())

    assert result.decision == "DECLINED"
    assert result.risk_score == 100
    assert provider.chat_calls == 0
    assert "risk_scorer" not in calls


@pytest.mark.asyncio
async def test_tools_executed_in_correct_order():
    provider = MockProvider(
        planning_response=LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(id="4", name="audit_logger", arguments={}),
                ToolCall(id="3", name="risk_scorer", arguments={}),
                ToolCall(id="2", name="doc_retriever", arguments={"query": "标准承保"}),
                ToolCall(id="1", name="rule_checker", arguments={}),
            ],
            stop_reason="tool_use",
            usage={},
        ),
        final_response=json.dumps(
            {
                "decision": "APPROVED",
                "risk_level": "LOW",
                "risk_score": 32,
                "reasons": ["标准承保。"],
                "missing_info": [],
                "next_steps": ["进入出单流程。"],
                "confidence": 0.93,
                "tool_calls_made": [],
                "processing_time_ms": 0,
            },
            ensure_ascii=False,
        ),
    )
    calls: list[str] = []
    tools = [
        RecordingTool("rule_checker", {"rules_matched": [], "violations": [], "hard_stops": []}, calls, delay=0.05),
        RecordingTool("doc_retriever", {"passages": []}, calls, delay=0.01),
        RecordingTool("risk_scorer", {"risk_score": 32, "risk_level": "LOW"}, calls),
        RecordingTool("audit_logger", {"status": "recorded"}, calls),
    ]
    agent = OrchestratorAgent(provider=provider, tools=tools)

    await agent.process(_application_payload())

    assert set(calls[:2]) == {"rule_checker", "doc_retriever"}
    assert calls[2] == "risk_scorer"
    assert calls[3] == "audit_logger"


@pytest.mark.asyncio
async def test_parse_failure_returns_request_info():
    provider = MockProvider(
        planning_response=LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="1", name="rule_checker", arguments={})],
            stop_reason="tool_use",
            usage={},
        ),
        final_response="not valid json",
    )
    tools = [
        RecordingTool("rule_checker", {"rules_matched": [], "violations": [], "hard_stops": []}, []),
    ]
    agent = OrchestratorAgent(provider=provider, tools=tools)

    result = await agent.process(ApplicationInput.model_validate(_application_payload()))

    assert result.decision == "REQUEST_MORE_INFO"
    assert result.missing_info
