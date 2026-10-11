"""Agent execution loop, tool dispatch, approval gating, and safety interception."""

import json
import logging
from typing import Any

from app.agent.base_tool import ExecutionContext, RiskLevel
from app.agent.kill_switch import kill_switch
from app.agent.registry import tool_registry
from app.agent.safety import wrap_untrusted_data
from app.api.sync_hub import sync_hub
from app.db import repository
from app.db.connection import get_database

logger = logging.getLogger("aria.agent.loop")


async def dispatch_tool_call(
    tool_name: str,
    args: dict[str, Any],
    session_id: str | None = None,
    device_id: str | None = None,
    auto_approve_low_risk: bool = True,
) -> dict[str, Any]:
    """
    Handle a tool call proposed by the model or requested by the user:
    - If kill switch is active, immediately reject.
    - If LOW risk and auto_approve_low_risk is True: execute immediately and log to audit_log.
    - If MEDIUM or HIGH risk: create a pending_action, log to audit_log, broadcast to devices.
    """
    if kill_switch.is_active:
        return {
            "status": "killed",
            "error": "Operation blocked: emergency kill switch is currently active.",
        }

    tool = tool_registry.get(tool_name)
    if not tool:
        return {
            "status": "error",
            "error": f"Tool '{tool_name}' is not recognized or available.",
        }

    args_json = json.dumps(args, default=str)
    db = get_database()

    # 1. Low risk: Execute immediately
    if tool.risk_level == RiskLevel.LOW and auto_approve_low_risk:
        ctx = ExecutionContext(
            session_id=session_id,
            device_id=device_id,
            is_approved=True,
            approved_by="auto",
        )
        try:
            result = await tool.execute(args, ctx)
            async with db.get_connection() as conn:
                await repository.create_audit_entry(
                    conn,
                    tool=tool.name,
                    args_json=args_json,
                    risk_level=tool.risk_level.value,
                    status="executed" if result.success else "failed",
                    approved_by="auto",
                    result_json=json.dumps(result.to_dict(), default=str),
                    error=result.error,
                )

            safe_output = wrap_untrusted_data(tool.name, str(result.output))
            return {
                "status": "executed",
                "success": result.success,
                "output": safe_output,
                "raw_output": result.output,
                "error": result.error,
                "risk_level": tool.risk_level.value,
            }
        except Exception as exc:
            error_msg = f"Unexpected execution error: {exc}"
            async with db.get_connection() as conn:
                await repository.create_audit_entry(
                    conn,
                    tool=tool.name,
                    args_json=args_json,
                    risk_level=tool.risk_level.value,
                    status="failed",
                    approved_by="auto",
                    error=error_msg,
                )
            return {"status": "failed", "error": error_msg}

    # 2. Medium or High risk: Create pending action requiring approval
    async with db.get_connection() as conn:
        action = await repository.create_pending_action(
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

    # Broadcast notification to all connected devices in real time
    await sync_hub.broadcast_all(
        {
            "type": "pending_action_created",
            "action": {
                "id": action["id"],
                "session_id": session_id,
                "tool": tool.name,
                "args": args,
                "risk_level": tool.risk_level.value,
                "created_at": action["created_at"],
            },
        }
    )

    return {
        "status": "pending_approval",
        "action_id": action["id"],
        "tool": tool.name,
        "args": args,
        "risk_level": tool.risk_level.value,
        "message": f"Action '{tool.name}' requires owner approval ({tool.risk_level.value} risk).",
    }


async def approve_and_execute_action(action_id: str, resolved_by: str = "owner") -> dict[str, Any]:
    """Approve a pending action and execute it."""
    if kill_switch.is_active:
        return {
            "status": "killed",
            "error": "Cannot execute: emergency kill switch is currently active.",
        }

    db = get_database()
    async with db.get_connection() as conn:
        action = await repository.get_pending_action(conn, action_id)
        if not action:
            return {"status": "error", "error": "Pending action not found."}

        if action["status"] != "pending":
            return {
                "status": "error",
                "error": f"Action has already been resolved with status '{action['status']}'.",
            }

        tool = tool_registry.get(action["tool"])
        if not tool:
            await repository.update_pending_action_status(
                conn, action_id, status="failed", resolved_by=resolved_by
            )
            return {"status": "error", "error": f"Tool '{action['tool']}' is no longer available."}

        # Parse stored arguments
        try:
            args = json.loads(action["args_json"])
        except Exception:
            args = {}

        ctx = ExecutionContext(
            session_id=action["session_id"],
            device_id=resolved_by,
            is_approved=True,
            approved_by=resolved_by,
        )

        try:
            result = await tool.execute(args, ctx)
            await repository.update_pending_action_status(
                conn, action_id, status="approved", resolved_by=resolved_by
            )
            await repository.create_audit_entry(
                conn,
                tool=tool.name,
                args_json=action["args_json"],
                risk_level=action["risk_level"],
                status="executed" if result.success else "failed",
                approved_by=resolved_by,
                result_json=json.dumps(result.to_dict(), default=str),
                error=result.error,
            )

            safe_output = wrap_untrusted_data(tool.name, str(result.output))
            response_data = {
                "status": "executed",
                "action_id": action_id,
                "success": result.success,
                "output": safe_output,
                "raw_output": result.output,
                "error": result.error,
            }
        except Exception as exc:
            error_msg = f"Execution error: {exc}"
            await repository.update_pending_action_status(
                conn, action_id, status="failed", resolved_by=resolved_by
            )
            await repository.create_audit_entry(
                conn,
                tool=tool.name,
                args_json=action["args_json"],
                risk_level=action["risk_level"],
                status="failed",
                approved_by=resolved_by,
                error=error_msg,
            )
            response_data = {"status": "failed", "action_id": action_id, "error": error_msg}

    # Broadcast resolution to other devices
    await sync_hub.broadcast_all(
        {
            "type": "pending_action_resolved",
            "action_id": action_id,
            "status": "approved",
            "resolved_by": resolved_by,
            "result": response_data,
        }
    )

    return response_data


async def reject_pending_action(action_id: str, resolved_by: str = "owner") -> dict[str, Any]:
    """Reject a pending action."""
    db = get_database()
    async with db.get_connection() as conn:
        action = await repository.get_pending_action(conn, action_id)
        if not action:
            return {"status": "error", "error": "Pending action not found."}

        if action["status"] != "pending":
            return {
                "status": "error",
                "error": f"Action has already been resolved with status '{action['status']}'.",
            }

        await repository.update_pending_action_status(
            conn, action_id, status="rejected", resolved_by=resolved_by
        )
        await repository.create_audit_entry(
            conn,
            tool=action["tool"],
            args_json=action["args_json"],
            risk_level=action["risk_level"],
            status="denied",
            approved_by=resolved_by,
        )

    await sync_hub.broadcast_all(
        {
            "type": "pending_action_resolved",
            "action_id": action_id,
            "status": "rejected",
            "resolved_by": resolved_by,
        }
    )

    return {"status": "rejected", "action_id": action_id}
