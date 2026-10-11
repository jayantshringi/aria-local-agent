"""Unit tests for SyncHub multi-device WebSocket manager and real-time broadcasting."""

import json
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.api.sync_hub import SyncHub, sync_hub


class DummyWebSocket:
    """Mock WebSocket for unit testing SyncHub broadcasting."""

    def __init__(self) -> None:
        self.sent_messages: list[str] = []
        self.closed_code: int | None = None
        self.send_text = AsyncMock(side_effect=self._record_send)
        self.close = AsyncMock(side_effect=self._record_close)

    async def _record_send(self, text: str) -> None:
        self.sent_messages.append(text)

    async def _record_close(self, code: int = 1000) -> None:
        self.closed_code = code


@pytest.mark.asyncio
async def test_synchub_registration_and_broadcast():
    """Test registering clients, broadcasting to all, and excluding the sender."""
    hub = SyncHub()
    ws1 = DummyWebSocket()
    ws2 = DummyWebSocket()

    c1 = await hub.register(ws1, device_id="dev-1", device_name="Laptop")
    c2 = await hub.register(ws2, device_id="dev-2", device_name="Phone")
    assert hub.active_connections_count == 2

    # Broadcast to all, excluding c1
    event = {"type": "session_created", "session": {"id": "s-123", "title": "Test"}}
    await hub.broadcast_all(event, exclude=c1)

    assert len(ws1.sent_messages) == 0
    assert len(ws2.sent_messages) == 1
    assert json.loads(ws2.sent_messages[0])["type"] == "session_created"

    # Unregister c2
    await hub.unregister(c2)
    assert hub.active_connections_count == 1


@pytest.mark.asyncio
async def test_synchub_session_targeting():
    """Test broadcasting only to clients subscribed to a specific session."""
    hub = SyncHub()
    ws1 = DummyWebSocket()
    ws2 = DummyWebSocket()
    ws3 = DummyWebSocket()

    c1 = await hub.register(ws1, device_id="dev-1", device_name="Laptop")
    c2 = await hub.register(ws2, device_id="dev-2", device_name="Phone")
    c3 = await hub.register(ws3, device_id="dev-3", device_name="Tablet")

    hub.set_client_session(c1, "sess-A")
    hub.set_client_session(c2, "sess-B")
    hub.set_client_session(c3, "sess-A")

    # Broadcast event specifically for sess-A, excluding c1
    token_event = {"type": "token", "session_id": "sess-A", "delta": "Hello"}
    await hub.broadcast_session("sess-A", token_event, exclude=c1)

    assert len(ws1.sent_messages) == 0
    assert len(ws2.sent_messages) == 0  # c2 is in sess-B
    assert len(ws3.sent_messages) == 1  # c3 is in sess-A
    assert json.loads(ws3.sent_messages[0])["delta"] == "Hello"


@pytest.mark.asyncio
async def test_synchub_disconnect_device():
    """Test forceful disconnection and socket termination when a device is revoked."""
    hub = SyncHub()
    ws_target = DummyWebSocket()
    ws_other = DummyWebSocket()

    await hub.register(ws_target, device_id="bad-device", device_name="Compromised Device")
    await hub.register(ws_other, device_id="safe-device", device_name="Safe PC")

    disconnected_count = await hub.disconnect_device("bad-device")
    assert disconnected_count == 1
    assert ws_target.closed_code == 4003
    assert ws_other.closed_code is None
    assert hub.active_connections_count == 1


@pytest.mark.asyncio
async def test_device_revocation_kicks_synchub_connection(async_client: AsyncClient):
    """Test that calling the device revocation REST endpoint actively terminates active sockets."""
    client = async_client
    # Register host
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"password": "primary-password", "device_name": "Host"},
    )
    host_token = login_resp.json()["token"]

    # Register secondary phone via pairing
    create_resp = await client.post(
        "/api/v1/auth/pair/create",
        headers={"Authorization": f"Bearer {host_token}"},
    )
    code = create_resp.json()["code"]

    claim_resp = await client.post(
        "/api/v1/auth/pair/claim",
        json={"code": code, "device_name": "Stolen Phone"},
    )
    phone_id = claim_resp.json()["device"]["id"]

    # Simulate phone being registered in global sync_hub
    phone_ws = DummyWebSocket()
    await sync_hub.register(phone_ws, device_id=phone_id, device_name="Stolen Phone")

    # Host revokes phone
    revoke_resp = await client.post(
        f"/api/v1/auth/devices/{phone_id}/revoke",
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["revoked"] is True

    # Verify phone websocket was terminated with code 4003
    assert phone_ws.closed_code == 4003
    assert any("auth_revoked" in msg for msg in phone_ws.sent_messages)
