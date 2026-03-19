"""Defensive parser for structured LLM outputs."""

from __future__ import annotations

import asyncio
import json
import re
import threading
from collections.abc import Awaitable, Callable

from agent.output.models import UnderwritingDecision


class StructuredParser:
    def __init__(
        self,
        llm_reformatter: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._llm_reformatter = llm_reformatter

    def parse(self, raw_output: str, max_retries: int = 3) -> UnderwritingDecision:
        for candidate in (
            raw_output,
            self._extract_json_block(raw_output),
            self._extract_largest_json(raw_output),
        ):
            decision = self._parse_candidate(candidate)
            if decision is not None:
                return decision

        for _ in range(max_retries):
            reformatted = self._llm_reformat(raw_output)
            decision = self._parse_candidate(reformatted)
            if decision is not None:
                return decision

        return self._fallback_decision()

    def _parse_candidate(self, candidate: str | None) -> UnderwritingDecision | None:
        if not candidate:
            return None

        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        try:
            return UnderwritingDecision.model_validate(payload)
        except Exception:
            return None

    def _extract_json_block(self, text: str) -> str | None:
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_largest_json(self, text: str) -> str | None:
        largest: str | None = None
        stack = 0
        start = -1

        for index, char in enumerate(text):
            if char == "{":
                if stack == 0:
                    start = index
                stack += 1
            elif char == "}":
                if stack == 0:
                    continue
                stack -= 1
                if stack == 0 and start != -1:
                    candidate = text[start : index + 1]
                    if largest is None or len(candidate) > len(largest):
                        largest = candidate
                    start = -1

        return largest

    def _llm_reformat(self, raw: str) -> str | None:
        if self._llm_reformatter is None:
            return None

        return self._run_async(self._llm_reformatter(raw))

    def _run_async(self, awaitable: Awaitable[str]) -> str | None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(awaitable)

        result: dict[str, str | Exception] = {}

        def runner() -> None:
            try:
                result["value"] = asyncio.run(awaitable)
            except Exception as exc:  # pragma: no cover - defensive path
                result["error"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in result:
            return None
        return result.get("value")

    def _fallback_decision(self) -> UnderwritingDecision:
        return UnderwritingDecision(
            decision="REQUEST_MORE_INFO",
            risk_level="HIGH",
            risk_score=100,
            reasons=["模型输出无法解析为合法 JSON。"],
            missing_info=["请人工复核模型输出并补充结构化信息。"],
            next_steps=["重新生成核保结果", "检查模型输出格式约束"],
            confidence=0.0,
            tool_calls_made=[],
            processing_time_ms=0,
        )
