from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.tools.audit_logger import AuditLoggerTool
from agent.tools.doc_retriever import DocRetrieverTool
from agent.tools.risk_scorer import RiskScorerTool
from agent.tools.rule_checker import RuleCheckerTool


@pytest.mark.asyncio
async def test_rule_checker_standard_case():
    tool = RuleCheckerTool()

    result = await tool.execute(
        age=45,
        coverage_amount=500000,
        product_code="LIFE-TERM-20",
        health_conditions=[{"condition": "hypertension", "controlled": True}],
        smoking=False,
        bmi=24.5,
    )

    matched_ids = {item["rule_id"] for item in result["rules_matched"]}
    assert "R001" in matched_ids
    assert "R004" in matched_ids
    assert result["hard_stops"] == []


@pytest.mark.asyncio
async def test_rule_checker_hard_stop():
    tool = RuleCheckerTool()

    result = await tool.execute(
        age=72,
        coverage_amount=400000,
        product_code="LIFE-TERM-20",
        health_conditions=[{"condition": "diabetes", "controlled": False}],
        smoking=True,
        bmi=31.4,
    )

    hard_stop_ids = {item["rule_id"] for item in result["hard_stops"]}
    assert "R006" in hard_stop_ids
    assert "R010" in hard_stop_ids


@pytest.mark.asyncio
async def test_doc_retriever_returns_results(tmp_path):
    docs_path = tmp_path / "manual.md"
    docs_path.write_text(
        "高血压申请人如血压稳定，可考虑加费承保。\n\n糖尿病控制不佳者需严格核查。",
        encoding="utf-8",
    )
    tool = DocRetrieverTool(
        docs_path=str(docs_path),
        persist_dir=str(tmp_path / "chroma"),
        collection_name="docs_returns_results",
    )

    result = await tool.execute(query="高血压承保条件", top_k=1)

    assert len(result["passages"]) == 1
    assert "高血压" in result["passages"][0]["content"]


@pytest.mark.asyncio
async def test_doc_retriever_empty_db(tmp_path):
    tool = DocRetrieverTool(
        docs_path=str(tmp_path / "missing.md"),
        persist_dir=str(tmp_path / "chroma"),
        collection_name="docs_empty_db",
    )

    result = await tool.execute(query="任意查询", top_k=2)

    assert result == {"passages": []}


@pytest.mark.asyncio
async def test_risk_scorer_low_risk():
    tool = RiskScorerTool()

    result = await tool.execute(
        age=35,
        smoking=False,
        bmi=22.1,
        rule_checker_result={
            "rules_matched": [{"rule_id": "R001", "description": "标准承保", "impact": "positive"}],
            "violations": [],
            "hard_stops": [],
        },
    )

    assert result["risk_level"] == "LOW"
    assert result["risk_score"] <= 40


@pytest.mark.asyncio
async def test_risk_scorer_high_risk():
    tool = RiskScorerTool()

    result = await tool.execute(
        age=70,
        smoking=True,
        bmi=31.0,
        rule_checker_result={
            "rules_matched": [
                {"rule_id": "R005", "description": "高血压未受控", "impact": "negative"}
            ],
            "violations": [
                {"rule_id": "R010", "description": "高龄高保额", "impact": "negative"}
            ],
            "hard_stops": [],
        },
    )

    assert result["risk_level"] == "HIGH"
    assert result["risk_score"] >= 71


@pytest.mark.asyncio
async def test_audit_logger_writes_file(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    tool = AuditLoggerTool(log_path=str(log_path))

    result = await tool.execute(
        application_id="APP-2026-001",
        preliminary_decision="APPROVED_WITH_LOADING",
        risk_score=62,
        tools_used=["rule_checker", "risk_scorer"],
        summary="高血压受控，加费承保。",
    )

    assert result["status"] == "recorded"
    line = log_path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["application_id"] == "APP-2026-001"
    assert payload["preliminary_decision"] == "APPROVED_WITH_LOADING"
