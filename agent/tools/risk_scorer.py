"""Pure Python risk scoring tool."""

from __future__ import annotations

from typing import Any

from agent.tools.base import BaseTool


class RiskScorerTool(BaseTool):
    name = "risk_scorer"
    description = "根据规则匹配结果和申请信息计算综合风险评分（0-100 分）。"
    input_schema = {
        "type": "object",
        "properties": {
            "rule_checker_result": {"type": "object", "description": "rule_checker 的输出"},
            "age": {"type": "integer"},
            "smoking": {"type": "boolean"},
            "bmi": {"type": "number"},
        },
        "required": ["rule_checker_result", "age"],
    }

    async def execute(
        self,
        *,
        rule_checker_result: dict[str, Any],
        age: int,
        smoking: bool = False,
        bmi: float | None = None,
    ) -> dict[str, Any]:
        hard_stops = rule_checker_result.get("hard_stops", [])
        violations = rule_checker_result.get("violations", [])
        matched = rule_checker_result.get("rules_matched", [])

        if hard_stops:
            return {
                "risk_score": 100,
                "risk_level": "HIGH",
                "factors": ["触发一票否决规则"],
                "score_breakdown": {
                    "base_score": 100,
                    "age_factor": 0,
                    "health_factor": 0,
                    "lifestyle_factor": 0,
                    "product_factor": 0,
                },
            }

        age_factor = 5 if age < 40 else 10 if age <= 55 else 20 if age <= 65 else 30
        health_factor = len(violations) * 20
        health_factor += sum(10 for item in matched if item.get("impact") == "negative")
        health_factor -= sum(3 for item in matched if item.get("impact") == "positive")
        lifestyle_factor = (15 if smoking else 0) + (10 if bmi is not None and bmi > 30 else 0)
        product_factor = 5 if any(item.get("impact") == "neutral" for item in matched) else 0
        base_score = 10

        total = max(0, min(100, base_score + age_factor + health_factor + lifestyle_factor + product_factor))
        risk_level = "LOW" if total <= 40 else "MEDIUM" if total <= 70 else "HIGH"

        factors = [item.get("description", "") for item in matched if item.get("description")]
        factors.extend(item.get("description", "") for item in violations if item.get("description"))

        return {
            "risk_score": total,
            "risk_level": risk_level,
            "factors": factors,
            "score_breakdown": {
                "base_score": base_score,
                "age_factor": age_factor,
                "health_factor": health_factor,
                "lifestyle_factor": lifestyle_factor,
                "product_factor": product_factor,
            },
        }
