"""Tests for Phase 4 database models: audit_log, pending_actions, notes, and reminders."""

import pytest

from app.db import repository
from app.db.connection import Database


@pytest.mark.asyncio
async def test_audit_log_crud(initialized_db: Database):
    """Verify audit log entry creation, filtering, and retrieval."""
    async with initialized_db.get_connection() as conn:
        entry = await repository.create_audit_entry(
            conn,
            tool="files.read",
            args_json='{"path": "test.txt"}',
            risk_level="low",
            status="executed",
            approved_by="auto",
            result_json='{"content": "hello"}',
            error=None,
        )
        assert entry["id"] is not None
        assert entry["tool"] == "files.read"

        fetched = await repository.get_audit_entry(conn, entry["id"])
        assert fetched is not None
        assert fetched["tool"] == "files.read"
        assert fetched["risk_level"] == "low"

        logs = await repository.list_audit_logs(conn, tool="files.read")
        assert len(logs) == 1
        assert logs[0]["id"] == entry["id"]

        no_logs = await repository.list_audit_logs(conn, tool="shell.run")
        assert len(no_logs) == 0


@pytest.mark.asyncio
async def test_pending_actions_lifecycle(initialized_db: Database):
    """Verify pending actions creation, listing, approval, rejection, and kill cancel."""
    async with initialized_db.get_connection() as conn:
        # Create pending action
        action1 = await repository.create_pending_action(
            conn,
            tool="files.write",
            args_json='{"path": "sample.md", "content": "draft"}',
            risk_level="medium",
            session_id="sess-100",
        )
        action2 = await repository.create_pending_action(
            conn,
            tool="files.delete",
            args_json='{"path": "old.md"}',
            risk_level="high",
            session_id="sess-100",
        )

        pending = await repository.list_pending_actions(conn, status="pending")
        assert len(pending) == 2

        # Approve action 1
        resolved_1 = await repository.update_pending_action_status(
            conn, action1["id"], status="approved", resolved_by="dev-pc"
        )
        assert resolved_1["status"] == "approved"
        assert resolved_1["resolved_by"] == "dev-pc"

        # Check remaining pending
        pending_after = await repository.list_pending_actions(conn, status="pending")
        assert len(pending_after) == 1
        assert pending_after[0]["id"] == action2["id"]

        # Cancel all via kill switch
        killed_count = await repository.cancel_all_pending_actions(conn, resolved_by="kill_switch")
        assert killed_count == 1

        final_pending = await repository.list_pending_actions(conn, status="pending")
        assert len(final_pending) == 0


@pytest.mark.asyncio
async def test_notes_crud(initialized_db: Database):
    """Verify notes creation, retrieval, search, update, and deletion."""
    async with initialized_db.get_connection() as conn:
        note = await repository.create_note(
            conn,
            title="Meeting Notes",
            content="Discussed local AI agent security and offline memory.",
            tags="ai,security",
        )
        assert note["id"] is not None
        assert note["title"] == "Meeting Notes"

        fetched = await repository.get_note(conn, note["id"])
        assert fetched is not None
        assert "local AI agent" in fetched["content"]

        # Search notes
        results = await repository.search_notes(conn, query="security")
        assert len(results) == 1
        assert results[0]["id"] == note["id"]

        # Update note
        updated = await repository.update_note(
            conn, note["id"], title="Updated Meeting Notes", content="New content."
        )
        assert updated["title"] == "Updated Meeting Notes"
        assert updated["content"] == "New content."

        # Delete note
        deleted = await repository.delete_note(conn, note["id"])
        assert deleted is True
        assert await repository.get_note(conn, note["id"]) is None


@pytest.mark.asyncio
async def test_reminders_crud(initialized_db: Database):
    """Verify reminders creation, listing by status, status update, and deletion."""
    async with initialized_db.get_connection() as conn:
        r1 = await repository.create_reminder(
            conn, text="Review PR for Phase 4", due_at="2026-10-12T10:00:00Z"
        )
        r2 = await repository.create_reminder(
            conn, text="Daily Standup", due_at="2026-10-12T09:00:00Z", repeat_rule="daily"
        )
        assert r1["id"] is not None
        assert r2["repeat_rule"] == "daily"

        pending_reminders = await repository.list_reminders(conn, status="pending")
        assert len(pending_reminders) == 2

        # Mark completed
        comp = await repository.update_reminder_status(conn, r1["id"], status="completed")
        assert comp["status"] == "completed"

        # List completed
        completed_reminders = await repository.list_reminders(conn, status="completed")
        assert len(completed_reminders) == 1
        assert completed_reminders[0]["id"] == r1["id"]

        # Delete
        assert await repository.delete_reminder(conn, r2["id"]) is True
