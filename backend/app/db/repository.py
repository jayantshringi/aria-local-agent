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
# Pairing Operations (Phase 3)
# ---------------------------------------------------------------------------


async def create_pairing_code(
    conn: aiosqlite.Connection,
    code: str,
    created_by_device_id: str,
    expires_at: str,
) -> dict[str, Any]:
    """Create a new temporary pairing code."""
    pairing_id = str(uuid.uuid4())
    now = _utc_now_iso()
    await conn.execute(
        """
        INSERT INTO pairing_codes (
            id, code, created_by_device_id, created_at,
            expires_at, claimed_at, claimed_by_device_id
        )
        VALUES (?, ?, ?, ?, ?, NULL, NULL)
        """,
        (pairing_id, code, created_by_device_id, now, expires_at),
    )
    await conn.commit()
    return {
        "id": pairing_id,
        "code": code,
        "created_by_device_id": created_by_device_id,
        "created_at": now,
        "expires_at": expires_at,
        "claimed_at": None,
        "claimed_by_device_id": None,
    }


async def get_pairing_code(conn: aiosqlite.Connection, code: str) -> dict[str, Any] | None:
    """Fetch a pairing code record by its code string."""
    async with conn.execute(
        """
        SELECT id, code, created_by_device_id, created_at,
               expires_at, claimed_at, claimed_by_device_id
        FROM pairing_codes
        WHERE code = ?
        """,
        (code,),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def claim_pairing_code(
    conn: aiosqlite.Connection, code: str, claimed_by_device_id: str
) -> bool:
    """Mark an active, unclaimed pairing code as claimed by a new device."""
    now = _utc_now_iso()
    cursor = await conn.execute(
        """
        UPDATE pairing_codes
        SET claimed_at = ?, claimed_by_device_id = ?
        WHERE code = ? AND claimed_at IS NULL AND expires_at > ?
        """,
        (now, claimed_by_device_id, code, now),
    )
    await conn.commit()
    return cursor.rowcount > 0


async def list_active_pairing_codes(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    """List unexpired, unclaimed pairing codes."""
    now = _utc_now_iso()
    async with conn.execute(
        """
        SELECT id, code, created_by_device_id, created_at, expires_at
        FROM pairing_codes
        WHERE claimed_at IS NULL AND expires_at > ?
        ORDER BY created_at DESC
        """,
        (now,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


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


# ---------------------------------------------------------------------------
# Memory Chunks & Vector Operations (Phase 2)
# ---------------------------------------------------------------------------


async def create_memory_chunk(
    conn: aiosqlite.Connection,
    source_type: str,
    source_id: str,
    text: str,
    embedding: list[float] | None = None,
) -> dict[str, Any]:
    """Create a memory chunk and index its embedding in sqlite-vec if provided."""
    chunk_id = str(uuid.uuid4())
    now = _utc_now_iso()

    await conn.execute(
        """
        INSERT INTO memory_chunks (id, source_type, source_id, text, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (chunk_id, source_type, source_id, text, now),
    )

    if embedding is not None and len(embedding) > 0:
        try:
            import sqlite_vec

            serialized = sqlite_vec.serialize_float32(embedding)
            await conn.execute(
                "INSERT INTO memory_vectors (chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, serialized),
            )
        except Exception as e:
            import logging

            logging.getLogger("aria.repository").warning(f"Vector insert error: {e}")

    await conn.commit()
    return {
        "id": chunk_id,
        "source_type": source_type,
        "source_id": source_id,
        "text": text,
        "created_at": now,
    }


async def search_memory_vectors(
    conn: aiosqlite.Connection,
    query_embedding: list[float],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search nearest memory chunks by dense vector distance in sqlite-vec."""
    try:
        import sqlite_vec

        serialized = sqlite_vec.serialize_float32(query_embedding)
        async with conn.execute(
            """
            SELECT v.chunk_id, v.distance, c.source_type, c.source_id, c.text, c.created_at
            FROM memory_vectors v
            JOIN memory_chunks c ON c.id = v.chunk_id
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance ASC
            """,
            (serialized, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        import logging

        logging.getLogger("aria.repository").warning(f"Vector search error: {e}")
        return []


# ---------------------------------------------------------------------------
# Profile Facts Operations (Phase 2)
# ---------------------------------------------------------------------------


async def create_profile_fact(
    conn: aiosqlite.Connection,
    key: str,
    value: str,
    status: str = "pending",
    confidence: float = 1.0,
) -> dict[str, Any]:
    """Create or update a candidate profile fact."""
    fact_id = str(uuid.uuid4())
    now = _utc_now_iso()

    # Check if a fact with the same key already exists
    async with conn.execute("SELECT id, status FROM profile_facts WHERE key = ?", (key,)) as cur:
        existing = await cur.fetchone()
        if existing:
            fact_id = existing["id"]
            await conn.execute(
                """
                UPDATE profile_facts
                SET value = ?, status = ?, confidence = ?, updated_at = ?
                WHERE id = ?
                """,
                (value, status, confidence, now, fact_id),
            )
            await conn.commit()
            return {
                "id": fact_id,
                "key": key,
                "value": value,
                "status": status,
                "confidence": confidence,
                "created_at": now,
                "updated_at": now,
            }

    await conn.execute(
        """
        INSERT INTO profile_facts (id, key, value, status, confidence, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (fact_id, key, value, status, confidence, now, now),
    )
    await conn.commit()
    return {
        "id": fact_id,
        "key": key,
        "value": value,
        "status": status,
        "confidence": confidence,
        "created_at": now,
        "updated_at": now,
    }


async def list_profile_facts(
    conn: aiosqlite.Connection, status: str | None = None
) -> list[dict[str, Any]]:
    """List profile facts, optionally filtered by status ('pending', 'approved', 'rejected')."""
    if status is not None:
        async with conn.execute(
            """
            SELECT id, key, value, status, confidence, created_at, updated_at
            FROM profile_facts
            WHERE status = ?
            ORDER BY updated_at DESC
            """,
            (status,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async with conn.execute("""
        SELECT id, key, value, status, confidence, created_at, updated_at
        FROM profile_facts
        ORDER BY updated_at DESC
        """) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_profile_fact(conn: aiosqlite.Connection, fact_id: str) -> dict[str, Any] | None:
    """Fetch single profile fact by ID."""
    async with conn.execute(
        """
        SELECT id, key, value, status, confidence, created_at, updated_at
        FROM profile_facts WHERE id = ?
        """,
        (fact_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def update_profile_fact(
    conn: aiosqlite.Connection,
    fact_id: str,
    status: str | None = None,
    value: str | None = None,
) -> dict[str, Any] | None:
    """Update fact status ('approved', 'rejected') or value."""
    now = _utc_now_iso()
    updates = ["updated_at = ?"]
    params: list[Any] = [now]

    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if value is not None:
        updates.append("value = ?")
        params.append(value)

    params.append(fact_id)
    await conn.execute(
        f"UPDATE profile_facts SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    await conn.commit()
    return await get_profile_fact(conn, fact_id)


async def delete_profile_fact(conn: aiosqlite.Connection, fact_id: str) -> bool:
    """Delete profile fact permanently."""
    cursor = await conn.execute("DELETE FROM profile_facts WHERE id = ?", (fact_id,))
    await conn.commit()
    return cursor.rowcount > 0
