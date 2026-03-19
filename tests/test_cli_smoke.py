from __future__ import annotations

import json
from argparse import Namespace

import pytest

from agent.cli import format_decision, main, run_cli_async
from agent.output.models import ApplicationInput, UnderwritingDecision


def test_cli_main_returns_zero(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["agent.cli"])

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "核保前置检查 Agent 命令行入口" in captured.out


def test_format_decision():
    output = format_decision(
        "APP-2026-001",
        UnderwritingDecision(
            decision="APPROVED_WITH_LOADING",
            risk_level="MEDIUM",
            risk_score=62,
            reasons=["高血压已受控。"],
            missing_info=[],
            next_steps=["补充血压记录。"],
            confidence=0.88,
            tool_calls_made=["rule_checker", "risk_scorer"],
            processing_time_ms=1234,
        ),
    )

    assert "申请ID: APP-2026-001" in output
    assert "调用工具: rule_checker, risk_scorer" in output


@pytest.mark.asyncio
async def test_run_cli_async_with_input(tmp_path, capsys, monkeypatch):
    application_path = tmp_path / "application.json"
    application_path.write_text(
        json.dumps(
            {
                "application_id": "APP-TEST-001",
                "applicant": {
                    "age": 45,
                    "gender": "male",
                    "occupation": "office_worker",
                    "smoking": False,
                    "bmi": 24.5,
                },
                "health_conditions": [],
                "coverage": {
                    "product_code": "LIFE-TERM-20",
                    "coverage_amount": 300000,
                    "coverage_period_years": 20,
                    "premium_frequency": "annual",
                },
                "beneficiaries": [{"relationship": "spouse", "percentage": 100}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class FakeAgent:
        async def process(self, application: ApplicationInput) -> UnderwritingDecision:
            assert application.application_id == "APP-TEST-001"
            return UnderwritingDecision(
                decision="APPROVED",
                risk_level="LOW",
                risk_score=30,
                reasons=["标准承保。"],
                missing_info=[],
                next_steps=["进入出单流程。"],
                confidence=0.95,
                tool_calls_made=["rule_checker"],
                processing_time_ms=88,
            )

    monkeypatch.setattr("agent.cli.build_agent", lambda provider_name=None: FakeAgent())

    exit_code = await run_cli_async(
        Namespace(input=str(application_path), provider=None, no_cache=True, demo=False)
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "APP-TEST-001" in captured.out
    assert "决策: APPROVED" in captured.out
