"""Integration tests for Phase 4 Agent REST API, approvals, and kill switch."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.agent.kill_switch import kill_switch
from app.config import get_settings


@pytest.fixture
async def auth_headers(async_client: AsyncClient) -> dict[str, str]:
    """Helper to login and obtain valid auth headers."""
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"password": "TestPassword123", "device_name": "TestDevice"},
    )
    assert resp.status_code == 200
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_tools_api(async_client: AsyncClient, auth_headers: dict[str, str]):
    """Verify GET /api/v1/agent/tools returns registered catalog."""
    resp = await async_client.get("/api/v1/agent/tools", headers=auth_headers)
    assert resp.status_code == 200
    tools = resp.json()
    assert len(tools) >= 12
    tool_names = [t["name"] for t in tools]
    assert "notes.create" in tool_names
    assert "files.read" in tool_names
    assert "files.delete" in tool_names


@pytest.mark.asyncio
async def test_execute_low_risk_auto_executes(
    async_client: AsyncClient, auth_headers: dict[str, str]
):
    """Verify executing low-risk tool runs immediately without pending action."""
    resp = await async_client.post(
        "/api/v1/agent/execute",
        json={"tool": "notes.create", "args": {"title": "Quick Note", "content": "Sample content"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "executed"
    assert data["success"] is True
    assert "Quick Note" in data["output"]

    # Verify audit log was created
    audit_resp = await async_client.get(
        "/api/v1/agent/audit?tool=notes.create", headers=auth_headers
    )
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    assert logs[0]["tool"] == "notes.create"
    assert logs[0]["status"] == "executed"


@pytest.mark.asyncio
async def test_execute_medium_risk_generates_pending_action(
    async_client: AsyncClient, auth_headers: dict[str, str], tmp_path: Path, monkeypatch
):
    """Verify medium/high risk tool generates a pending action that must be approved."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ARIA_FOLDER_WHITELIST", str(sandbox))
    get_settings.cache_clear()

    # 1. Propose files.write (Medium risk)
    prop_resp = await async_client.post(
        "/api/v1/agent/execute",
        json={
            "tool": "files.write",
            "args": {"path": "approved_file.txt", "content": "Approved content!"},
        },
        headers=auth_headers,
    )
    assert prop_resp.status_code == 200
    prop_data = prop_resp.json()
    assert prop_data["status"] == "pending_approval"
    action_id = prop_data["action_id"]

    # File should NOT exist yet
    assert not (sandbox / "approved_file.txt").exists()

    # 2. Check pending actions endpoint
    pending_resp = await async_client.get("/api/v1/agent/actions/pending", headers=auth_headers)
    assert pending_resp.status_code == 200
    pending_list = pending_resp.json()
    assert any(a["id"] == action_id for a in pending_list)

    # 3. Approve action
    appr_resp = await async_client.post(
        f"/api/v1/agent/actions/{action_id}/approve",
        headers=auth_headers,
    )
    assert appr_resp.status_code == 200
    appr_data = appr_resp.json()
    assert appr_data["status"] == "executed"
    assert appr_data["success"] is True

    # File should NOW exist
    assert (sandbox / "approved_file.txt").exists()
    assert (sandbox / "approved_file.txt").read_text(encoding="utf-8") == "Approved content!"

    # 4. Action should no longer be pending
    pending_after = await async_client.get("/api/v1/agent/actions/pending", headers=auth_headers)
    assert not any(a["id"] == action_id for a in pending_after.json())


@pytest.mark.asyncio
async def test_reject_pending_action(
    async_client: AsyncClient, auth_headers: dict[str, str], tmp_path: Path, monkeypatch
):
    """Verify rejecting a pending action prevents execution and records denial in audit log."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ARIA_FOLDER_WHITELIST", str(sandbox))
    get_settings.cache_clear()

    prop_resp = await async_client.post(
        "/api/v1/agent/execute",
        json={
            "tool": "files.write",
            "args": {"path": "rejected_file.txt", "content": "Should not write"},
        },
        headers=auth_headers,
    )
    action_id = prop_resp.json()["action_id"]

    # Reject
    rej_resp = await async_client.post(
        f"/api/v1/agent/actions/{action_id}/reject",
        headers=auth_headers,
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["status"] == "rejected"

    # File never created
    assert not (sandbox / "rejected_file.txt").exists()

    # Audit log check
    audit_resp = await async_client.get("/api/v1/agent/audit", headers=auth_headers)
    denied_entries = [e for e in audit_resp.json() if e["status"] == "denied"]
    assert len(denied_entries) >= 1


@pytest.mark.asyncio
async def test_emergency_kill_switch(async_client: AsyncClient, auth_headers: dict[str, str]):
    """Verify kill switch stops executions, clears pending actions, and blocks new requests."""
    # Reset kill switch at start
    kill_switch.reset()

    # Create pending action
    prop_resp = await async_client.post(
        "/api/v1/agent/execute",
        json={"tool": "apps.open", "args": {"app_name": "notepad"}},
        headers=auth_headers,
    )
    assert "action_id" in prop_resp.json()

    # Check pending
    pending_before = await async_client.get("/api/v1/agent/actions/pending", headers=auth_headers)
    assert len(pending_before.json()) >= 1

    # Trigger emergency kill switch
    kill_resp = await async_client.post(
        "/api/v1/agent/kill",
        json={"reason": "User clicked red stop button"},
        headers=auth_headers,
    )
    assert kill_resp.status_code == 200
    assert kill_resp.json()["killed"] is True
    assert kill_resp.json()["cancelled_actions"] >= 1

    # Pending actions should now be flushed to empty
    pending_after = await async_client.get("/api/v1/agent/actions/pending", headers=auth_headers)
    assert len(pending_after.json()) == 0

    # Attempts to execute tools while killed must be blocked
    try_exec = await async_client.post(
        "/api/v1/agent/execute",
        json={"tool": "notes.create", "args": {"title": "X", "content": "Y"}},
        headers=auth_headers,
    )
    assert try_exec.json()["status"] == "killed"

    # Reset kill switch
    reset_resp = await async_client.post("/api/v1/agent/kill/reset", headers=auth_headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["is_killed"] is False

    # Now operations succeed again
    resumed_exec = await async_client.post(
        "/api/v1/agent/execute",
        json={"tool": "notes.create", "args": {"title": "Resumed", "content": "Back to work"}},
        headers=auth_headers,
    )
    assert resumed_exec.json()["status"] == "executed"
