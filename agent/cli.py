"""CLI entrypoint for the underwriting agent."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from agent.orchestrator import OrchestratorAgent
from agent.output.models import ApplicationInput, UnderwritingDecision
from agent.tools.audit_logger import AuditLoggerTool
from agent.tools.doc_retriever import DocRetrieverTool
from agent.tools.risk_scorer import RiskScorerTool
from agent.tools.rule_checker import RuleCheckerTool
from providers import get_provider


CACHE_DIR = Path("data/cache")
DEMO_FILES = [
    Path("data/synthetic/sample_application.json"),
    Path("data/synthetic/high_risk_application.json"),
    Path("data/synthetic/missing_info_application.json"),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agent.cli",
        description="核保前置检查 Agent 命令行入口。",
    )
    parser.add_argument(
        "--input",
        help="投保申请 JSON 文件路径。",
    )
    parser.add_argument(
        "--provider",
        help="覆盖配置中的 provider，例如 claude 或 glm4。",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="跳过缓存。",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="运行内置仿真示例。",
    )
    return parser


def build_agent(provider_name: str | None = None) -> OrchestratorAgent:
    provider = get_provider(provider_name=provider_name)
    tools = [
        RuleCheckerTool(),
        DocRetrieverTool(),
        RiskScorerTool(),
        AuditLoggerTool(),
    ]
    return OrchestratorAgent(provider=provider, tools=tools)


def load_application(path: Path) -> ApplicationInput:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ApplicationInput.model_validate(payload)


async def run_application(
    agent: OrchestratorAgent,
    application: ApplicationInput,
    *,
    provider_name: str | None,
    use_cache: bool,
) -> UnderwritingDecision:
    cache_key = _cache_key(application, provider_name)
    cache_path = CACHE_DIR / f"{cache_key}.json"

    if use_cache and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return UnderwritingDecision.model_validate(payload)

    result = await agent.process(application)

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            result.model_dump_json(indent=2),
            encoding="utf-8",
        )

    return result


async def run_cli_async(args: argparse.Namespace) -> int:
    if not args.input and not args.demo:
        build_parser().print_help()
        return 0

    agent = build_agent(provider_name=args.provider)
    input_files = [Path(args.input)] if args.input else DEMO_FILES

    for input_file in input_files:
        application = load_application(input_file)
        result = await run_application(
            agent,
            application,
            provider_name=args.provider,
            use_cache=not args.no_cache,
        )
        print(format_decision(application.application_id, result))
        if len(input_files) > 1 and input_file != input_files[-1]:
            print()

    return 0


def format_decision(application_id: str, decision: UnderwritingDecision) -> str:
    lines = [
        "=== 核保结果 ===",
        f"申请ID: {application_id}",
        f"决策: {decision.decision}",
        f"风险等级: {decision.risk_level}（评分: {decision.risk_score}/100）",
        "理由:",
    ]
    if decision.reasons:
        lines.extend(f"  - {reason}" for reason in decision.reasons)
    else:
        lines.append("  - 无")

    if decision.missing_info:
        lines.append("待补充信息:")
        lines.extend(f"  - {item}" for item in decision.missing_info)

    if decision.next_steps:
        lines.append("下一步:")
        lines.extend(f"  - {step}" for step in decision.next_steps)

    tool_calls = ", ".join(decision.tool_calls_made) if decision.tool_calls_made else "无"
    lines.append(f"处理耗时: {decision.processing_time_ms}ms")
    lines.append(f"调用工具: {tool_calls}")
    return "\n".join(lines)


def _cache_key(application: ApplicationInput, provider_name: str | None) -> str:
    raw = json.dumps(application.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(f"{provider_name or 'default'}::{raw}".encode("utf-8")).hexdigest()
    return digest


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_cli_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
