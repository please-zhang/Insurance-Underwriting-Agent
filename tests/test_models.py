from __future__ import annotations

import json
from pathlib import Path

from agent.output.models import ApplicationInput
from agent.output.parser import StructuredParser


def _decision_payload() -> dict:
    return {
        "decision": "APPROVED_WITH_LOADING",
        "risk_level": "MEDIUM",
        "risk_score": 62,
        "reasons": ["高血压已受控，建议加费承保。"],
        "missing_info": [],
        "next_steps": ["补充最近 12 个月血压记录。"],
        "confidence": 0.87,
        "tool_calls_made": ["rule_checker", "doc_retriever", "risk_scorer"],
        "processing_time_ms": 3842,
    }


def test_parse_valid_json():
    parser = StructuredParser()

    result = parser.parse(json.dumps(_decision_payload(), ensure_ascii=False))

    assert result.decision == "APPROVED_WITH_LOADING"
    assert result.risk_score == 62


def test_parse_json_in_codeblock():
    parser = StructuredParser()
    wrapped = f"说明如下：\n```json\n{json.dumps(_decision_payload(), ensure_ascii=False)}\n```"

    result = parser.parse(wrapped)

    assert result.risk_level == "MEDIUM"
    assert result.tool_calls_made == ["rule_checker", "doc_retriever", "risk_scorer"]


def test_parse_json_with_garbage():
    parser = StructuredParser()
    noisy = (
        "模型分析开始\n"
        f"{json.dumps(_decision_payload(), ensure_ascii=False)}\n"
        "以上为最终结论"
    )

    result = parser.parse(noisy)

    assert result.confidence == 0.87
    assert result.processing_time_ms == 3842


def test_parse_fallback_returns_request_info():
    parser = StructuredParser()

    result = parser.parse("this is not valid json")

    assert result.decision == "REQUEST_MORE_INFO"
    assert result.missing_info
    assert result.confidence == 0.0


def test_application_input_accepts_missing_optional_fields():
    payload = json.loads(
        Path("data/synthetic/missing_info_application.json").read_text(encoding="utf-8")
    )

    result = ApplicationInput.model_validate(payload)

    assert result.applicant.occupation is None
    assert result.applicant.bmi is None
