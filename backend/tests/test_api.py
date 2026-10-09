"""Tests for REST API endpoints: health, auth, and sessions."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    """Test health check route."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "database" in data
    assert data["database"]["connected"] is True


@pytest.mark.asyncio
async def test_auth_and_sessions_flow(async_client: AsyncClient):
    """Test full flow: login, token retrieval, creating session, and listing messages."""
    # 1. Login (first time setup)
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"password": "LocalAgentPassword", "device_name": "Test PC"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["token"]
    assert token is not None
    assert login_data["first_time_setup"] is True

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify me endpoint
    me_resp = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["name"] == "Test PC"

    # 3. Unauthorized access without token
    unauth_resp = await async_client.get("/sessions")
    assert unauth_resp.status_code == 401

    # 4. Create session
    create_resp = await async_client.post(
        "/sessions",
        headers=headers,
        json={"title": "Test REST Chat"},
    )
    assert create_resp.status_code == 201
    session_data = create_resp.json()
    session_id = session_data["id"]
    assert session_data["title"] == "Test REST Chat"

    # 5. List sessions
    list_resp = await async_client.get("/sessions", headers=headers)
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id

    # 6. Add message to session
    msg_resp = await async_client.post(
        f"/sessions/{session_id}/messages",
        headers=headers,
        json={"role": "user", "content": "What is the speed of light?", "tokens": 7},
    )
    assert msg_resp.status_code == 201
    assert msg_resp.json()["content"] == "What is the speed of light?"

    # 7. List session messages
    get_msgs_resp = await async_client.get(
        f"/sessions/{session_id}/messages",
        headers=headers,
    )
    assert get_msgs_resp.status_code == 200
    messages = get_msgs_resp.json()
    assert len(messages) == 1
    assert messages[0]["role"] == "user"

    # 8. Delete session
    del_resp = await async_client.delete(f"/sessions/{session_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True
