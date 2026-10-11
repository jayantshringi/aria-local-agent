"""Tests for WebSocket chat streaming and immediate message persistence."""

import pytest
from starlette.testclient import TestClient

from app.auth.security import generate_device_token, hash_token
from app.db import repository
from app.db.connection import Database
from app.main import create_app


@pytest.fixture
def test_client(initialized_db: Database):
    """Synchronous Starlette TestClient with WebSocket support."""
    app = create_app()
    return TestClient(app)


def test_websocket_unauthorized(test_client: TestClient):
    """Verify unauthorized WebSocket connection is rejected."""
    with test_client.websocket_connect("/ws/chat") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "error"
        assert "Unauthorized" in data["error"]


@pytest.mark.asyncio
async def test_websocket_chat_streaming_and_persistence(
    test_client: TestClient, initialized_db: Database, monkeypatch
):
    """Test WebSocket chat: authenticated connect, streaming token output, and DB persistence."""
    # 1. Register a valid device token in DB
    raw_token = generate_device_token()
    t_hash = hash_token(raw_token)
    async with initialized_db.get_connection() as conn:
        device = await repository.register_device(conn, "Test Workstation", t_hash)
        assert device["name"] == "Test Workstation"

    # 2. Mock OllamaClient stream_chat
    async def mock_stream_chat(*args, **kwargs):
        yield {"type": "delta", "content": "I am "}
        yield {"type": "delta", "content": "Aria, "}
        yield {"type": "delta", "content": "your assistant."}
        yield {"type": "done", "tokens": 6, "model": "qwen2.5:7b-instruct"}

    from app.api import chat_ws

    monkeypatch.setattr(chat_ws.OllamaClient, "stream_chat", mock_stream_chat)

    # 3. Connect to WebSocket with token
    with test_client.websocket_connect(f"/ws/chat?token={raw_token}") as ws:
        # Initial connected greeting
        init_event = ws.receive_json()
        assert init_event["type"] == "connected"
        assert init_event["device"]["name"] == "Test Workstation"

        # Send user chat message
        ws.send_json(
            {
                "type": "message",
                "content": "Hello Aria, who are you?",
            }
        )

        # Receive user message saved confirmation
        saved_event = ws.receive_json()
        assert saved_event["type"] == "message_saved"
        session_id = saved_event["session_id"]
        assert saved_event["message"]["role"] == "user"
        assert saved_event["message"]["content"] == "Hello Aria, who are you?"

        # Receive streaming tokens
        t1 = ws.receive_json()
        assert t1["type"] == "token"
        assert t1["delta"] == "I am "

        t2 = ws.receive_json()
        assert t2["type"] == "token"
        assert t2["delta"] == "Aria, "

        t3 = ws.receive_json()
        assert t3["type"] == "token"
        assert t3["delta"] == "your assistant."

        # Receive done event
        done_event = ws.receive_json()
        assert done_event["type"] == "done"
        assert done_event["message"]["role"] == "assistant"
        assert done_event["message"]["content"] == "I am Aria, your assistant."
        assert done_event["message"]["tokens"] == 6

    # 4. Verify messages are persisted in SQLite!
    async with initialized_db.get_connection() as conn:
        db_messages = await repository.list_messages(conn, session_id)
        assert len(db_messages) == 2
        assert db_messages[0]["role"] == "user"
        assert db_messages[0]["content"] == "Hello Aria, who are you?"
        assert db_messages[1]["role"] == "assistant"
        assert db_messages[1]["content"] == "I am Aria, your assistant."


@pytest.mark.asyncio
async def test_websocket_tool_events_and_kill_switch(
    test_client: TestClient, initialized_db: Database, monkeypatch
):
    """Test execute_tool, action approval, and emergency kill over WebSocket."""
    raw_token = generate_device_token()
    t_hash = hash_token(raw_token)
    async with initialized_db.get_connection() as conn:
        await repository.register_device(conn, "Admin Device", t_hash)

    with test_client.websocket_connect(f"/ws/chat?token={raw_token}") as ws:
        init_event = ws.receive_json()
        assert init_event["type"] == "connected"

        # 1. Execute low-risk tool via websocket
        ws.send_json(
            {
                "type": "execute_tool",
                "tool": "notes.create",
                "args": {"title": "WS Note", "content": "Created via WS"},
            }
        )
        resp = ws.receive_json()
        assert resp["type"] == "tool_dispatched"
        assert resp["result"]["status"] == "executed"
        assert resp["result"]["success"] is True

        # 2. Trigger kill switch via websocket
        ws.send_json({"type": "kill"})
        kill_resp = ws.receive_json()
        assert kill_resp["type"] == "agent_killed"
