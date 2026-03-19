from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.orchestrator import OrchestratorAgent
from agent.output.models import ApplicationInput
from agent.tools.audit_logger import AuditLoggerTool
from agent.tools.doc_retriever import DocRetrieverTool
from agent.tools.risk_scorer import RiskScorerTool
from agent.tools.rule_checker import RuleCheckerTool
from providers import get_provider


def load_json(path: str) -> ApplicationInput:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ApplicationInput.model_validate(payload)


async def run_with_provider(provider_name: str, application: ApplicationInput):
    provider = get_provider(provider_name=provider_name)
    tools = [
        RuleCheckerTool(),
        DocRetrieverTool(),
        RiskScorerTool(),
        AuditLoggerTool(),
    ]
    agent = OrchestratorAgent(provider=provider, tools=tools)
    return await agent.process(application)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "application_file",
    [
        "data/synthetic/sample_application.json",
        "data/synthetic/high_risk_application.json",
    ],
)
async def test_model_parity(application_file):
    """验证 Claude 和 GLM4.7 在相同申请上给出一致的核保结论。"""

    application = load_json(application_file)

    claude_result = await run_with_provider("claude", application)
    glm4_result = await run_with_provider("glm4", application)

    assert claude_result.decision == glm4_result.decision, (
        f"决策不一致: Claude={claude_result.decision}, GLM4={glm4_result.decision}"
    )
    assert claude_result.risk_level == glm4_result.risk_level
    assert abs(claude_result.risk_score - glm4_result.risk_score) <= 20
