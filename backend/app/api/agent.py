"""REST API routes for agent tools, approval actions, audit logging, and kill switch."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.agent.kill_switch import kill_switch
from app.agent.loop import approve_and_execute_action, dispatch_tool_call, reject_pending_action
from app.agent.registry import tool_registry
from app.auth.security import get_current_device
from app.db import repository
from app.db.connection import get_database

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


class ExecuteToolRequest(BaseModel):
    tool: str = Field(..., description="Tool name to execute (e.g., 'notes.create')")
    args: dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool")
    session_id: str | None = Field(default=None, description="Associated chat session ID")


class KillSwitchRequest(BaseModel):
    reason: str = Field(
        default="Owner triggered emergency kill switch", description="Reason for kill"
    )


@router.get("/tools")
async def list_available_tools(
    _: dict[str, Any] = Depends(get_current_device),
) -> list[dict[str, Any]]:
    """Return all registered agent tools with their parameters and risk tiers."""
    return tool_registry.get_catalog_summary()


@router.post("/execute")
async def execute_tool_endpoint(
    req: ExecuteToolRequest,
    current_device: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """
    Directly request execution of a tool.
    Low risk executes immediately; medium/high risk generates a pending action.
    """
    return await dispatch_tool_call(
        tool_name=req.tool,
        args=req.args,
        session_id=req.session_id,
        device_id=current_device["id"],
    )


@router.get("/actions/pending")
async def list_pending_actions_endpoint(
    _: dict[str, Any] = Depends(get_current_device),
) -> list[dict[str, Any]]:
    """List all actions currently waiting for owner approval."""
    db = get_database()
    async with db.get_connection() as conn:
        return await repository.list_pending_actions(conn, status="pending")


@router.post("/actions/{action_id}/approve")
async def approve_action_endpoint(
    action_id: str,
    current_device: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Approve and execute a pending medium or high risk action."""
    result = await approve_and_execute_action(action_id, resolved_by=current_device["id"])
    if result.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error"))
    return result


@router.post("/actions/{action_id}/reject")
async def reject_action_endpoint(
    action_id: str,
    current_device: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Reject a pending action, preventing execution."""
    result = await reject_pending_action(action_id, resolved_by=current_device["id"])
    if result.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error"))
    return result


@router.post("/kill")
async def activate_kill_switch_endpoint(
    req: KillSwitchRequest | None = None,
    current_device: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """
    Emergency kill switch: halts running agent tasks, flushes pending actions,
    and broadcasts kill notification to all connected devices.
    """
    reason = (
        req.reason
        if req
        else f"Kill switch triggered by device {current_device.get('name', 'owner')}"
    )
    return await kill_switch.trigger(reason=reason)


@router.post("/kill/reset")
async def reset_kill_switch_endpoint(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Reset the emergency kill switch back to normal status."""
    kill_switch.reset()
    return {"status": "resumed", "is_killed": False}


@router.get("/kill/status")
async def get_kill_switch_status(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Check whether the kill switch is currently active."""
    return {"is_killed": kill_switch.is_active}


@router.get("/audit")
async def list_audit_logs_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tool: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    _: dict[str, Any] = Depends(get_current_device),
) -> list[dict[str, Any]]:
    """Fetch paginated audit log records."""
    db = get_database()
    async with db.get_connection() as conn:
        return await repository.list_audit_logs(
            conn, limit=limit, offset=offset, tool=tool, risk_level=risk_level
        )
