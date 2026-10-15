"""OPEC Agent Loop: Executor Component for safe, sandboxed step execution."""

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.agent.kill_switch import kill_switch
from app.agent.safety import wrap_untrusted_data
from app.api.sync_hub import sync_hub
from app.db import repository
from app.db.connection import get_database
from core.observer import Observation
from core.planner import PlanStep
from tools.base import ExecutionContext, RiskLevel
from tools.registry import tool_registry

logger = logging.getLogger("aria.core.executor")


@dataclass
class StepExecutionResult:
    """Outcome of executing an individual plan step."""

    step_id: int
    action: str
    success: bool
    output: Any = None
    error: str | None = None
    risk_level: str = "low"
    requires_approval: bool = False
    action_id: str | None = None


class Executor:
    """Executes individual plan steps against the standardized tool registry with safety controls."""

    def __init__(self) -> None:
        pass

    async def execute_step(
        self,
        step: PlanStep,
        observation: Observation,
        session_id: str | None = None,
        device_id: str | None = None,
        auto_approve_low_risk: bool = True,
    ) -> StepExecutionResult:
        """Execute a plan step with kill-switch verification and approval gating."""
        # 1. Kill Switch verification
        if kill_switch.is_active:
            return StepExecutionResult(
                step_id=step.step_id,
                action=step.action,
                success=False,
                error="Execution blocked: emergency kill switch is currently active.",
            )

        # Special internal action: synthesize response
        if step.action == "synthesize_response":
            return StepExecutionResult(
                step_id=step.step_id,
                action=step.action,
                success=True,
                output=step.args.get("query") or observation.user_input,
            )

        # 2. Lookup tool
        tool = tool_registry.get(step.action)
        if not tool:
            return StepExecutionResult(
                step_id=step.step_id,
                action=step.action,
                success=False,
                error=f"Tool '{step.action}' is not registered or available in tool registry.",
            )

        db = get_database()
        args_json = json.dumps(step.args, default=str)

        # 3. Low Risk: Execute immediately
        if tool.risk_level == RiskLevel.LOW and auto_approve_low_risk:
            ctx = ExecutionContext(
                session_id=session_id,
                device_id=device_id or "auto",
                is_approved=True,
                approved_by="auto",
            )
            try:
                res = await tool.execute(step.args, ctx)
                # Record in audit trail
                async with db.get_connection() as conn:
                    await repository.create_audit_entry(
                        conn,
                        tool=tool.name,
                        args_json=args_json,
                        risk_level=tool.risk_level.value,
                        status="executed" if res.success else "failed",
                        approved_by="auto",
                        result_json=json.dumps(res.to_dict(), default=str),
                        error=res.error,
                    )

                safe_out = wrap_untrusted_data(tool.name, str(res.output))
                return StepExecutionResult(
                    step_id=step.step_id,
                    action=step.action,
                    success=res.success,
                    output=safe_out,
                    error=res.error,
                    risk_level=tool.risk_level.value,
                    requires_approval=False,
                )
            except Exception as exc:
                err_msg = f"Unexpected execution error in {step.action}: {exc}"
                async with db.get_connection() as conn:
                    await repository.create_audit_entry(
                        conn,
                        tool=tool.name,
                        args_json=args_json,
                        risk_level=tool.risk_level.value,
                        status="failed",
                        approved_by="auto",
                        error=err_msg,
                    )
                return StepExecutionResult(
                    step_id=step.step_id,
                    action=step.action,
                    success=False,
                    error=err_msg,
                    risk_level=tool.risk_level.value,
                )

        # 4. Medium / High Risk: Require owner approval
        async with db.get_connection() as conn:
            pending = await repository.create_pending_action(
                conn,
                tool=tool.name,
                args_json=args_json,
                risk_level=tool.risk_level.value,
                session_id=session_id,
            )
            await repository.create_audit_entry(
                conn,
                tool=tool.name,
                args_json=args_json,
                risk_level=tool.risk_level.value,
                status="pending_approval",
                approved_by=None,
            )

        # Broadcast live approval request to all connected devices
        await sync_hub.broadcast_all(
            {
                "type": "pending_action_created",
                "action": {
                    "id": pending["id"],
                    "session_id": session_id,
                    "tool": tool.name,
                    "args": step.args,
                    "risk_level": tool.risk_level.value,
                    "created_at": pending["created_at"],
                },
            }
        )

        return StepExecutionResult(
            step_id=step.step_id,
            action=step.action,
            success=True,
            output=f"Action '{tool.name}' requires owner approval ({tool.risk_level.value} risk).",
            risk_level=tool.risk_level.value,
            requires_approval=True,
            action_id=pending["id"],
        )


__all__ = ["Executor", "StepExecutionResult"]
