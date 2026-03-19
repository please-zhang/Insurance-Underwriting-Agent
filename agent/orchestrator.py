"""Main agent orchestration logic."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from agent.output.models import ApplicationInput, UnderwritingDecision
from agent.output.parser import StructuredParser
from agent.tools.base import BaseTool
from providers.base import LLMProvider, ToolCall


TOOL_DEPENDENCIES: dict[str, list[str]] = {
    "rule_checker": [],
    "doc_retriever": [],
    "risk_scorer": ["rule_checker"],
    "audit_logger": ["risk_scorer"],
}


class OrchestratorAgent:
    def __init__(
        self,
        provider: LLMProvider,
        tools: list[BaseTool],
        parser: StructuredParser | None = None,
    ) -> None:
        self.provider = provider
        self.tools = {tool.name: tool for tool in tools}
        self.parser = parser or StructuredParser()

    async def process(self, application: ApplicationInput | dict[str, Any]) -> UnderwritingDecision:
        started_at = time.perf_counter()
        app = (
            application
            if isinstance(application, ApplicationInput)
            else ApplicationInput.model_validate(application)
        )
        system_prompt = self._build_system_prompt()
        planning_messages = [
            {
                "role": "user",
                "content": json.dumps(app.model_dump(mode="json"), ensure_ascii=False),
            }
        ]

        planning_response = await self.provider.chat_with_tools(
            messages=planning_messages,
            tools=[tool.to_claude_tool_spec() for tool in self.tools.values()],
            system=system_prompt,
        )
        tool_calls = planning_response.tool_calls or []

        executed_results: list[dict[str, Any]] = []
        previous_results: dict[str, dict[str, Any]] = {}
        tool_names_used: list[str] = []

        for round_calls in self._get_tool_execution_order(tool_calls):
            round_results = await self._execute_tools_parallel(
                round_calls,
                app=app,
                previous_results=previous_results,
            )
            executed_results.extend(round_results)
            for item in round_results:
                previous_results[item["tool_name"]] = item["result"]
                tool_names_used.append(item["tool_name"])

            if self._has_hard_stop(previous_results):
                return self._build_hard_stop_decision(
                    previous_results=previous_results,
                    processing_time_ms=self._elapsed_ms(started_at),
                    tool_calls_made=tool_names_used,
                )

        final_messages = [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "application": app.model_dump(mode="json"),
                        "tool_results": executed_results,
                    },
                    ensure_ascii=False,
                ),
            }
        ]
        raw_output = await self.provider.chat(messages=final_messages, system=system_prompt)
        decision = self.parser.parse(raw_output)
        return decision.model_copy(
            update={
                "tool_calls_made": tool_names_used,
                "processing_time_ms": self._elapsed_ms(started_at),
            }
        )

    async def _execute_tools_parallel(
        self,
        tool_calls: list[ToolCall],
        *,
        app: ApplicationInput,
        previous_results: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        tasks = [
            self._execute_single_tool(tool_call, app=app, previous_results=previous_results)
            for tool_call in tool_calls
        ]
        return await asyncio.gather(*tasks)

    async def _execute_tools_sequential(
        self,
        tool_calls: list[ToolCall],
        *,
        app: ApplicationInput,
        previous_results: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        results = []
        for tool_call in tool_calls:
            result = await self._execute_single_tool(
                tool_call,
                app=app,
                previous_results=previous_results,
            )
            results.append(result)
            previous_results[result["tool_name"]] = result["result"]
        return results

    def _build_system_prompt(self) -> str:
        schema = {
            "decision": "APPROVED | APPROVED_WITH_LOADING | DECLINED | REQUEST_MORE_INFO",
            "risk_level": "LOW | MEDIUM | HIGH",
            "risk_score": "0-100",
            "reasons": ["string"],
            "missing_info": ["string"],
            "next_steps": ["string"],
            "confidence": "0.0-1.0",
            "tool_calls_made": ["string"],
            "processing_time_ms": "integer",
        }
        return (
            "你是保险核保专家。先根据申请决定需要调用哪些工具，再结合工具结果输出严格 JSON。"
            f"最终 JSON Schema: {json.dumps(schema, ensure_ascii=False)}"
        )

    def _get_tool_execution_order(self, tool_calls: list[ToolCall]) -> list[list[ToolCall]]:
        requested = {tool_call.name: tool_call for tool_call in tool_calls if tool_call.name in self.tools}
        if not requested:
            return []

        remaining = dict(requested)
        completed: set[str] = set()
        rounds: list[list[ToolCall]] = []

        while remaining:
            ready = [
                tool_call
                for tool_name, tool_call in requested.items()
                if tool_name in remaining
                and all(dep not in requested or dep in completed for dep in TOOL_DEPENDENCIES.get(tool_name, []))
            ]
            if not ready:
                raise ValueError("Circular or unsatisfied tool dependencies detected")
            rounds.append(ready)
            for tool_call in ready:
                completed.add(tool_call.name)
                remaining.pop(tool_call.name, None)

        return rounds

    async def _execute_single_tool(
        self,
        tool_call: ToolCall,
        *,
        app: ApplicationInput,
        previous_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        tool = self.tools[tool_call.name]
        prepared_input = self._prepare_tool_input(
            tool_call=tool_call,
            app=app,
            previous_results=previous_results,
        )

        try:
            result = await tool.execute(**prepared_input)
        except Exception as exc:
            result = {
                "error": str(exc),
                "tool_name": tool_call.name,
                "tool_input": prepared_input,
            }

        return {
            "tool_name": tool_call.name,
            "tool_input": prepared_input,
            "result": result,
        }

    def _prepare_tool_input(
        self,
        *,
        tool_call: ToolCall,
        app: ApplicationInput,
        previous_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        arguments = dict(tool_call.arguments)

        if tool_call.name == "rule_checker":
            arguments.setdefault("age", app.applicant.age)
            arguments.setdefault("coverage_amount", app.coverage.coverage_amount)
            arguments.setdefault("product_code", app.coverage.product_code)
            arguments.setdefault(
                "health_conditions",
                [condition.model_dump(mode="json") for condition in app.health_conditions],
            )
            arguments.setdefault("smoking", app.applicant.smoking)
            arguments.setdefault("bmi", app.applicant.bmi)
            return arguments

        if tool_call.name == "doc_retriever":
            arguments.setdefault("product_code", app.coverage.product_code)
            return arguments

        if tool_call.name == "risk_scorer":
            arguments.setdefault("rule_checker_result", previous_results.get("rule_checker", {}))
            arguments.setdefault("age", app.applicant.age)
            arguments.setdefault("smoking", app.applicant.smoking)
            arguments.setdefault("bmi", app.applicant.bmi)
            return arguments

        if tool_call.name == "audit_logger":
            risk_result = previous_results.get("risk_scorer", {})
            arguments.setdefault("application_id", app.application_id)
            arguments.setdefault(
                "preliminary_decision",
                self._derive_preliminary_decision(
                    risk_result=risk_result,
                    rule_result=previous_results.get("rule_checker", {}),
                ),
            )
            arguments.setdefault("risk_score", risk_result.get("risk_score", 0))
            arguments.setdefault("tools_used", list(previous_results.keys()))
            arguments.setdefault("summary", "Preliminary underwriting assessment recorded.")
            return arguments

        return arguments

    def _derive_preliminary_decision(
        self,
        *,
        risk_result: dict[str, Any],
        rule_result: dict[str, Any],
    ) -> str:
        if rule_result.get("hard_stops"):
            return "DECLINED"

        risk_score = risk_result.get("risk_score", 0)
        if risk_score >= 80:
            return "DECLINED"
        if risk_score >= 60:
            return "APPROVED_WITH_LOADING"
        return "APPROVED"

    def _has_hard_stop(self, previous_results: dict[str, dict[str, Any]]) -> bool:
        rule_result = previous_results.get("rule_checker", {})
        return bool(rule_result.get("hard_stops"))

    def _build_hard_stop_decision(
        self,
        *,
        previous_results: dict[str, dict[str, Any]],
        processing_time_ms: int,
        tool_calls_made: list[str],
    ) -> UnderwritingDecision:
        hard_stops = previous_results.get("rule_checker", {}).get("hard_stops", [])
        reasons = [item.get("description", "触发一票否决规则") for item in hard_stops]

        return UnderwritingDecision(
            decision="DECLINED",
            risk_level="HIGH",
            risk_score=100,
            reasons=reasons or ["触发一票否决规则"],
            missing_info=[],
            next_steps=["人工复核拒保原因", "通知申请人拒保结论"],
            confidence=1.0,
            tool_calls_made=tool_calls_made,
            processing_time_ms=processing_time_ms,
        )

    def _elapsed_ms(self, started_at: float) -> int:
        return int((time.perf_counter() - started_at) * 1000)
