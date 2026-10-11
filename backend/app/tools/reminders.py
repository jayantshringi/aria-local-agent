"""Reminders tools for creating and viewing scheduled reminders."""

from typing import Any

from app.agent.base_tool import BaseTool, ExecutionContext, RiskLevel, ToolResult
from app.db import repository
from app.db.connection import get_database


class RemindersCreateTool(BaseTool):
    """Tool to create a scheduled reminder."""

    @property
    def name(self) -> str:
        return "reminders.create"

    @property
    def description(self) -> str:
        return (
            "Create a new reminder with text, due date/time (ISO 8601), and optional repeat rule."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The reminder content or task"},
                "due_at": {
                    "type": "string",
                    "description": "Due date/time in ISO 8601 format (e.g., '2026-10-12T18:00:00')",
                },
                "repeat_rule": {
                    "type": "string",
                    "description": "Optional repeat schedule ('daily', 'weekly', etc.)",
                },
            },
            "required": ["text", "due_at"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        text = args.get("text", "").strip()
        due_at = args.get("due_at", "").strip()
        repeat_rule = args.get("repeat_rule")

        if not text:
            return ToolResult(success=False, output="", error="Reminder text cannot be empty")
        if not due_at:
            return ToolResult(
                success=False, output="", error="Reminder due date/time cannot be empty"
            )

        db = get_database()
        async with db.get_connection() as conn:
            reminder = await repository.create_reminder(
                conn, text=text, due_at=due_at, repeat_rule=repeat_rule
            )
            repeat_str = f" (repeats: {repeat_rule})" if repeat_rule else ""
            return ToolResult(
                success=True,
                output=f"Reminder created: '{text}' due at {due_at}{repeat_str} (ID: {reminder['id'][:8]})",
                meta={"reminder_id": reminder["id"]},
            )


class RemindersListTool(BaseTool):
    """Tool to list scheduled reminders."""

    @property
    def name(self) -> str:
        return "reminders.list"

    @property
    def description(self) -> str:
        return "List upcoming or past reminders, optionally filtered by status ('pending', 'completed', 'all')."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "completed", "all"],
                    "description": "Status filter (default 'pending')",
                },
                "limit": {"type": "integer", "description": "Max reminders to return (default 20)"},
            },
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        status_filter = args.get("status", "pending")
        limit = int(args.get("limit", 20))
        status = None if status_filter == "all" else status_filter

        db = get_database()
        async with db.get_connection() as conn:
            reminders = await repository.list_reminders(conn, status=status, limit=limit)
            if not reminders:
                return ToolResult(success=True, output=f"No {status_filter} reminders found.")

            lines = []
            for r in reminders:
                repeat_str = f" [{r['repeat_rule']}]" if r["repeat_rule"] else ""
                lines.append(
                    f"- [{r['status'].upper()}] **{r['text']}** — Due: {r['due_at']}{repeat_str}"
                )

            return ToolResult(
                success=True,
                output="\n".join(lines),
                meta={"count": len(reminders)},
            )
