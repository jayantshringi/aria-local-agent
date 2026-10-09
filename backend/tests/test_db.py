"""Tests for database initialization, schema, WAL mode, CRUD operations, and FTS5 search."""

from pathlib import Path

import pytest

from app.db import repository
from app.db.connection import Database
from app.db.schema import init_db


@pytest.fixture
async def test_db(tmp_path: Path):
    """Fixture providing a temporary SQLite database initialized with schema."""
    db_file = tmp_path / "test_aria.db"
    db = Database(db_file)
    async with db.get_connection() as conn:
        await init_db(conn)
    return db


@pytest.mark.asyncio
async def test_wal_mode_enabled(test_db: Database):
    """Verify that WAL mode and foreign keys are active."""
    async with test_db.get_connection() as conn:
        async with conn.execute("PRAGMA journal_mode;") as cursor:
            row = await cursor.fetchone()
            assert row[0].lower() == "wal"

        async with conn.execute("PRAGMA foreign_keys;") as cursor:
            row = await cursor.fetchone()
            assert row[0] == 1


@pytest.mark.asyncio
async def test_session_lifecycle(test_db: Database):
    """Test session creation, retrieval, update, and listing."""
    async with test_db.get_connection() as conn:
        # Create
        session = await repository.create_session(conn, title="Initial Discussion")
        assert session["id"] is not None
        assert session["title"] == "Initial Discussion"

        # Get
        fetched = await repository.get_session(conn, session["id"])
        assert fetched is not None
        assert fetched["title"] == "Initial Discussion"

        # Update
        updated = await repository.update_session(
            conn, session["id"], title="Updated Discussion", summary="A brief recap."
        )
        assert updated["title"] == "Updated Discussion"
        assert updated["summary"] == "A brief recap."

        # List
        sessions = await repository.list_sessions(conn)
        assert len(sessions) == 1
        assert sessions[0]["id"] == session["id"]

        # Delete
        deleted = await repository.delete_session(conn, session["id"])
        assert deleted is True
        assert await repository.get_session(conn, session["id"]) is None


@pytest.mark.asyncio
async def test_messages_persistence_and_fts5(test_db: Database):
    """Test immediate message persistence and FTS5 synchronization."""
    async with test_db.get_connection() as conn:
        session = await repository.create_session(conn, title="Memory Test")
        session_id = session["id"]

        # Insert user and assistant messages
        msg1 = await repository.create_message(
            conn, session_id, role="user", content="How do quantum computers work?"
        )
        msg2 = await repository.create_message(
            conn,
            session_id,
            role="assistant",
            content="Quantum computers utilize qubits and superposition principles.",
            tokens=12,
        )

        # Retrieve messages list
        messages = await repository.list_messages(conn, session_id)
        assert len(messages) == 2
        assert messages[0]["id"] == msg1["id"]
        assert messages[1]["id"] == msg2["id"]
        assert messages[1]["tokens"] == 12

        # FTS5 keyword search
        search_results = await repository.search_messages_fts(conn, "quantum")
        assert len(search_results) == 2

        superpos_results = await repository.search_messages_fts(conn, "superposition")
        assert len(superpos_results) == 1
        assert superpos_results[0]["id"] == msg2["id"]

        # Cascade deletion: deleting session cleans up messages and FTS
        await repository.delete_session(conn, session_id)
        remaining_messages = await repository.list_messages(conn, session_id)
        assert len(remaining_messages) == 0

        fts_after_del = await repository.search_messages_fts(conn, "quantum")
        assert len(fts_after_del) == 0


@pytest.mark.asyncio
async def test_device_registration_and_revocation(test_db: Database):
    """Test registering devices, token hashing verification, and revoking."""
    async with test_db.get_connection() as conn:
        dummy_hash = "mock_sha256_hash_123456789"
        device = await repository.register_device(
            conn, name="Jayant's Laptop", token_hash=dummy_hash
        )
        assert device["name"] == "Jayant's Laptop"
        assert device["revoked"] == 0

        # Retrieve by hash
        found = await repository.get_device_by_token_hash(conn, dummy_hash)
        assert found is not None
        assert found["id"] == device["id"]

        # Revoke device
        revoked = await repository.revoke_device(conn, device["id"])
        assert revoked is True

        # Now get by hash should return None because it's revoked
        assert await repository.get_device_by_token_hash(conn, dummy_hash) is None


@pytest.mark.asyncio
async def test_settings_store(test_db: Database):
    """Test key-value settings storage."""
    async with test_db.get_connection() as conn:
        assert await repository.get_setting(conn, "theme", default="dark") == "dark"
        await repository.set_setting(conn, "theme", "amoled")
        assert await repository.get_setting(conn, "theme") == "amoled"
