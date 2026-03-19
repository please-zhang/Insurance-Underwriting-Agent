"""Audit logging tool."""

from __future__ import annotations

import json
from asyncio import to_thread
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.tools.base import BaseTool


class AuditLoggerTool(BaseTool):
    name = "audit_logger"
    description = "将核保处理过程记录到审核日志，用于合规追溯。"
    input_schema = {
        "type": "object",
        "properties": {
            "application_id": {"type": "string"},
            "preliminary_decision": {
                "type": "string",
                "enum": ["APPROVED", "APPROVED_WITH_LOADING", "DECLINED", "REQUEST_MORE_INFO"],
            },
            "risk_score": {"type": "integer"},
            "tools_used": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
        },
        "required": ["application_id", "preliminary_decision", "risk_score"],
    }

    def __init__(self, log_path: str = "data/audit/audit.jsonl") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    async def execute(
        self,
        *,
        application_id: str,
        preliminary_decision: str,
        risk_score: int,
        tools_used: list[str] | None = None,
        summary: str | None = None,
        reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        log_id = f"LOG-{application_id}"
        entry = {
            "log_id": log_id,
            "timestamp": timestamp,
            "application_id": application_id,
            "preliminary_decision": preliminary_decision,
            "risk_score": risk_score,
            "tools_used": tools_used or [],
            "summary": summary or "",
            "reasons": reasons or [],
        }

        await to_thread(self._append_jsonl, entry)

        return {"log_id": log_id, "timestamp": timestamp, "status": "recorded"}

    def _append_jsonl(self, entry: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
