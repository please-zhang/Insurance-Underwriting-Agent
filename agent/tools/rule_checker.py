"""Rule matching tool for underwriting checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.tools.base import BaseTool


class RuleCheckerTool(BaseTool):
    name = "rule_checker"
    description = "检查投保申请是否符合核保规则库中的规定，返回适用规则和违规情况。"
    input_schema = {
        "type": "object",
        "properties": {
            "age": {"type": "integer", "description": "申请人年龄"},
            "health_conditions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "既往症名称列表",
            },
            "coverage_amount": {"type": "integer", "description": "申请保额（元）"},
            "product_code": {"type": "string", "description": "产品代码"},
        },
        "required": ["age", "coverage_amount", "product_code"],
    }

    def __init__(self, rules_path: str = "data/rules/underwriting_rules.json") -> None:
        self.rules_path = Path(rules_path)
        payload = json.loads(self.rules_path.read_text(encoding="utf-8"))
        self.rules = payload.get("rules", [])

    async def execute(
        self,
        *,
        age: int,
        coverage_amount: int,
        product_code: str,
        health_conditions: list[Any] | None = None,
        smoking: bool | None = None,
        bmi: float | None = None,
    ) -> dict[str, Any]:
        conditions = self._normalize_conditions(health_conditions or [])
        rules_matched: list[dict[str, Any]] = []
        violations: list[dict[str, Any]] = []
        hard_stops: list[dict[str, Any]] = []

        for rule in self.rules:
            matched, violated = self._evaluate_rule(
                rule=rule,
                age=age,
                coverage_amount=coverage_amount,
                product_code=product_code,
                conditions=conditions,
                smoking=smoking,
                bmi=bmi,
            )
            if matched:
                record = self._rule_record(rule)
                rules_matched.append(record)
                if rule.get("hard_stop"):
                    hard_stops.append(record)
            elif violated:
                violations.append(self._rule_record(rule))

        return {
            "rules_matched": rules_matched,
            "violations": violations,
            "hard_stops": hard_stops,
        }

    def _normalize_conditions(self, conditions: list[Any]) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        for item in conditions:
            if isinstance(item, str):
                normalized[item] = {"condition": item}
            elif isinstance(item, dict) and item.get("condition"):
                normalized[item["condition"]] = item
        return normalized

    def _evaluate_rule(
        self,
        *,
        rule: dict[str, Any],
        age: int,
        coverage_amount: int,
        product_code: str,
        conditions: dict[str, dict[str, Any]],
        smoking: bool | None,
        bmi: float | None,
    ) -> tuple[bool, bool]:
        category = rule.get("category")
        criteria = rule.get("criteria", {})

        if category == "age":
            min_age = criteria.get("min_age", 0)
            max_age = criteria.get("max_age", 10_000)
            return (min_age <= age <= max_age, False)

        if category == "condition":
            condition_name = criteria.get("condition")
            condition = conditions.get(condition_name)
            if not condition:
                return (False, False)
            controlled = criteria.get("controlled")
            if controlled is None or condition.get("controlled") == controlled:
                return (True, False)
            return (False, True)

        if category == "smoking":
            expected = criteria.get("smoking")
            return (smoking is expected, False)

        if category == "bmi":
            threshold = criteria.get("bmi_gt")
            return (bmi is not None and threshold is not None and bmi > threshold, False)

        if category == "coverage":
            if criteria.get("product_code") and criteria["product_code"] != product_code:
                return (False, False)
            min_age = criteria.get("min_age")
            max_coverage = criteria.get("max_coverage_amount")
            age_gate = min_age is None or age >= min_age
            if not age_gate:
                return (False, False)
            if max_coverage is None:
                return (False, False)
            if rule.get("hard_stop"):
                return (coverage_amount > max_coverage, False)
            if coverage_amount <= max_coverage:
                return (True, False)
            return (False, True)

        return (False, False)

    def _rule_record(self, rule: dict[str, Any]) -> dict[str, Any]:
        return {
            "rule_id": rule.get("rule_id"),
            "description": rule.get("description"),
            "impact": rule.get("impact"),
        }
