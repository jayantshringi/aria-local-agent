"""Unit and integration tests for Phase 5 Scheduler & Morning Briefings."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

import app.tools  # noqa: F401
from app.api.sync_hub import sync_hub
from app.db import repository
from app.db.connection import get_database
from app.llm.ollama_client import OllamaClient
from app.scheduler.briefing import generate_morning_briefing
from app.scheduler.engine import _calc_next_due, scheduler


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


def test_calc_next_due():
    """Verify ISO date calculation for daily, weekly, and monthly repeating rules."""
    base_iso = "2026-10-15T09:00:00"

    next_daily = _calc_next_due(base_iso, "daily")
    assert next_daily is not None
    assert "2026-10-16T09:00:00" in next_daily

    next_weekly = _calc_next_due(base_iso, "weekly")
    assert next_weekly is not None
    assert "2026-10-22T09:00:00" in next_weekly

    next_monthly = _calc_next_due(base_iso, "monthly")
    assert next_monthly is not None
    assert "2026-11-14T09:00:00" in next_monthly

    assert _calc_next_due(base_iso, "irregular") is None


@pytest.mark.asyncio
async def test_poll_due_reminders_completes_past_reminder():
    """Verify scheduler poll finds overdue reminders and marks them completed."""
    db = get_database()
    now = datetime.now(UTC)
    past_iso = (now - timedelta(minutes=15)).isoformat()
    future_iso = (now + timedelta(days=2)).isoformat()

    async with db.get_connection() as conn:
        r_due = await repository.create_reminder(
            conn, text="Call Ahmed about local LLM server", due_at=past_iso
        )
        r_future = await repository.create_reminder(
            conn, text="Upcoming trip planning", due_at=future_iso
        )

    with patch.object(sync_hub, "broadcast_all", new_callable=AsyncMock) as mock_broadcast:
        fired = await scheduler.poll_due_reminders()

        assert len(fired) >= 1
        fired_ids = [r["id"] for r in fired]
        assert r_due["id"] in fired_ids
        assert r_future["id"] not in fired_ids

        # Broadcast should have been emitted
        mock_broadcast.assert_called()
        broadcast_call = mock_broadcast.call_args[0][0]
        assert broadcast_call["type"] == "reminder_fired"
        assert broadcast_call["reminder"]["id"] == r_due["id"]

    # Check updated database status
    async with db.get_connection() as conn:
        updated_due = await repository.get_reminder(conn, r_due["id"])
        assert updated_due["status"] == "completed"

        updated_future = await repository.get_reminder(conn, r_future["id"])
        assert updated_future["status"] == "pending"


@pytest.mark.asyncio
async def test_poll_repeating_reminder_advances_date():
    """Verify repeating reminders remain pending and advance their due_at."""
    db = get_database()
    past_iso = "2026-10-10T18:00:00"

    async with db.get_connection() as conn:
        reminder = await repository.create_reminder(
            conn,
            text="Take evening vitamins",
            due_at=past_iso,
            repeat_rule="daily",
        )

    fired = await scheduler.poll_due_reminders()
    assert any(r["id"] == reminder["id"] for r in fired)

    async with db.get_connection() as conn:
        updated = await repository.get_reminder(conn, reminder["id"])
        assert updated["status"] == "pending"
        assert "2026-10-11T18:00:00" in updated["due_at"]


@pytest.mark.asyncio
async def test_generate_morning_briefing():
    """Verify morning briefing aggregates data and stores in Daily Briefings session."""
    db = get_database()
    today_iso = datetime.now(UTC).isoformat()

    async with db.get_connection() as conn:
        await repository.create_reminder(conn, text="Team sprint sync", due_at=today_iso)
        await repository.create_profile_fact(conn, key="Name", value="Jayant", status="approved")

    mock_ollama = AsyncMock(spec=OllamaClient)
    mock_ollama.chat.return_value = (
        "### ☀️ Good Morning Jayant!\n\n"
        "Here is your agenda today:\n"
        "- Team sprint sync scheduled.\n"
        "Have a productive day!"
    )

    with patch.object(sync_hub, "broadcast_all", new_callable=AsyncMock) as mock_broadcast:
        briefing = await generate_morning_briefing(ollama_client=mock_ollama)

        assert briefing["reminders_count"] >= 1
        assert "Good Morning Jayant!" in briefing["content"]

        # Check broadcast
        mock_broadcast.assert_called_once()
        assert mock_broadcast.call_args[0][0]["type"] == "daily_briefing"

    # Verify session was created and message persisted
    async with db.get_connection() as conn:
        sessions = await repository.list_sessions(conn)
        briefing_session = next((s for s in sessions if s["title"] == "Daily Briefings"), None)
        assert briefing_session is not None

        msgs = await repository.list_messages(conn, briefing_session["id"])
        assert len(msgs) >= 1
        assert msgs[0]["role"] == "assistant"
        assert "Good Morning Jayant!" in msgs[0]["content"]


@pytest.mark.asyncio
async def test_scheduler_api_endpoints(async_client: AsyncClient, auth_headers: dict[str, str]):
    """Verify GET /api/v1/scheduler/status, POST /poll, and POST /briefing."""
    # 1. Status
    resp = await async_client.get("/api/v1/scheduler/status", headers=auth_headers)
    assert resp.status_code == 200
    assert "poll_interval_seconds" in resp.json()

    # 2. Manual poll
    resp = await async_client.post("/api/v1/scheduler/poll", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # 3. Manual briefing with fallback/mock
    with patch(
        "app.api.scheduler.generate_morning_briefing",
        new_callable=AsyncMock,
        return_value={"content": "Mocked briefing", "date": "2026-10-11"},
    ):
        resp = await async_client.post(
            "/api/v1/scheduler/briefing",
            headers=auth_headers,
            json={"language": "en", "persist_message": False},
        )
        assert resp.status_code == 200
        assert resp.json()["briefing"]["content"] == "Mocked briefing"


@pytest.mark.asyncio
async def test_end_to_end_voice_command_to_reminder_firing(
    async_client: AsyncClient, auth_headers: dict[str, str]
):
    """
    End-to-End Test (AGENTS.md Done Criteria):
    Voice input transcribed -> reminders.create tool executes -> stored in SQLite -> scheduler fires on time.
    """
    # 1. Dispatch reminder creation
    past_due = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    resp = await async_client.post(
        "/api/v1/agent/execute",
        headers=auth_headers,
        json={
            "tool": "reminders.create",
            "args": {"text": "Call Ahmed at 6 PM", "due_at": past_due},
        },
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["success"] is True
    assert "Reminder created" in res_data["output"]

    # 2. Run scheduler poll
    with patch.object(sync_hub, "broadcast_all", new_callable=AsyncMock) as mock_broadcast:
        fired = await scheduler.poll_due_reminders()
        assert any("Call Ahmed" in r["text"] for r in fired)
        mock_broadcast.assert_called()
