"""Database repository providing asynchronous CRUD operations."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import aiosqlite


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Session Operations
# ---------------------------------------------------------------------------


async def create_session(
    conn: aiosqlite.Connection,
    title: str = "New Chat",
    device_id: str | None = None,
) -> dict[str, Any]:
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    now = _utc_now_iso()
    await conn.execute(
        """
        INSERT INTO sessions (id, title, created_at, updated_at, summary, device_id)
        VALUES (?, ?, ?, ?, NULL, ?)
        """,
        (session_id, title, now, now, device_id),
    )
    await conn.commit()
    return {
        "id": session_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "summary": None,
        "device_id": device_id,
    }


async def get_session(conn: aiosqlite.Connection, session_id: str) -> dict[str, Any] | None:
    """Fetch a single session by its ID."""
    async with conn.execute(
        "SELECT id, title, created_at, updated_at, summary, device_id FROM sessions WHERE id = ?",
        (session_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def list_sessions(
    conn: aiosqlite.Connection, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """List sessions ordered from newest to oldest update."""
    async with conn.execute(
        """
        SELECT id, title, created_at, updated_at, summary, device_id
        FROM sessions
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_session(
    conn: aiosqlite.Connection,
    session_id: str,
    title: str | None = None,
    summary: str | None = None,
) -> dict[str, Any] | None:
    """Update title or summary for a session."""
    now = _utc_now_iso()
    updates = ["updated_at = ?"]
    params: list[Any] = [now]

    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if summary is not None:
        updates.append("summary = ?")
        params.append(summary)

    params.append(session_id)
    await conn.execute(
        f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    await conn.commit()
    return await get_session(conn, session_id)


async def delete_session(conn: aiosqlite.Connection, session_id: str) -> bool:
    """Delete a session and cascade delete all its messages."""
    cursor = await conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    await conn.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Message Operations
# ---------------------------------------------------------------------------


async def create_message(
    conn: aiosqlite.Connection,
    session_id: str,
    role: str,
    content: str,
    tokens: int = 0,
    meta_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create and persist a message immediately."""
    message_id = str(uuid.uuid4())
    now = _utc_now_iso()
    meta_str = json.dumps(meta_json) if meta_json is not None else None

    # Insert message
    await conn.execute(
        """
        INSERT INTO messages (id, session_id, role, content, created_at, tokens, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, session_id, role, content, now, tokens, meta_str),
    )

    # Touch session updated_at
    await conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    await conn.commit()

    return {
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": now,
        "tokens": tokens,
        "meta_json": meta_str,
    }


async def list_messages(
    conn: aiosqlite.Connection, session_id: str, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    """List messages for a session in chronological order."""
    async with conn.execute(
        """
        SELECT id, session_id, role, content, created_at, tokens, meta_json
        FROM messages
        WHERE session_id = ?
        ORDER BY created_at ASC
        LIMIT ? OFFSET ?
        """,
        (session_id, limit, offset),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def search_messages_fts(
    conn: aiosqlite.Connection, query: str, limit: int = 20
) -> list[dict[str, Any]]:
    """Search message contents using FTS5 match query."""
    async with conn.execute(
        """
        SELECT m.id, m.session_id, m.role, m.content, m.created_at, bm.rank
        FROM (
            SELECT message_id, rank
            FROM messages_fts
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        ) bm
        JOIN messages m ON m.id = bm.message_id
        ORDER BY bm.rank
        """,
        (query, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Device Authentication Operations
# ---------------------------------------------------------------------------


async def register_device(conn: aiosqlite.Connection, name: str, token_hash: str) -> dict[str, Any]:
    """Register a new trusted device."""
    device_id = str(uuid.uuid4())
    now = _utc_now_iso()
    await conn.execute(
        """
        INSERT INTO devices (id, name, token_hash, created_at, last_seen, revoked)
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (device_id, name, token_hash, now, now),
    )
    await conn.commit()
    return {
        "id": device_id,
        "name": name,
        "token_hash": token_hash,
        "created_at": now,
        "last_seen": now,
        "revoked": 0,
    }


async def get_device_by_token_hash(
    conn: aiosqlite.Connection, token_hash: str
) -> dict[str, Any] | None:
    """Lookup an active (non-revoked) device by token hash."""
    async with conn.execute(
        """
        SELECT id, name, token_hash, created_at, last_seen, revoked
        FROM devices
        WHERE token_hash = ? AND revoked = 0
        """,
        (token_hash,),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def update_device_last_seen(conn: aiosqlite.Connection, device_id: str) -> None:
    """Update last_seen timestamp for a device."""
    now = _utc_now_iso()
    await conn.execute("UPDATE devices SET last_seen = ? WHERE id = ?", (now, device_id))
    await conn.commit()


async def list_devices(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    """List all registered devices."""
    async with conn.execute(
        "SELECT id, name, created_at, last_seen, revoked FROM devices ORDER BY created_at DESC"
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def revoke_device(conn: aiosqlite.Connection, device_id: str) -> bool:
    """Revoke access for a specific device."""
    cursor = await conn.execute("UPDATE devices SET revoked = 1 WHERE id = ?", (device_id,))
    await conn.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Settings Operations
# ---------------------------------------------------------------------------


async def get_setting(
    conn: aiosqlite.Connection, key: str, default: str | None = None
) -> str | None:
    """Get system setting by key."""
    async with conn.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return default
        return str(row["value"])


async def set_setting(conn: aiosqlite.Connection, key: str, value: str) -> None:
    """Set or update system setting by key."""
    await conn.execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    await conn.commit()
