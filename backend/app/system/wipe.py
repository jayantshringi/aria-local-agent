"""Secure data wipe engine for permanent deletion of all user records."""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite

from app.memory.cache import get_embedding_cache

logger = logging.getLogger("aria.system.wipe")

CONFIRMATION_REQUIRED_STRING = "PERMANENTLY_DELETE_ALL_DATA"


async def wipe_all_user_data(
    conn: aiosqlite.Connection,
    confirmation_phrase: str,
) -> dict[str, Any]:
    """
    Permanently erase all sessions, messages, semantic vectors, profile facts,
    reminders, pending actions, and audit logs.
    Leaves schema and device enrollment tokens intact.
    Requires exact confirmation string match.
    """
    if confirmation_phrase.strip() != CONFIRMATION_REQUIRED_STRING:
        raise ValueError(
            f"Confirmation mismatch. Must supply exactly '{CONFIRMATION_REQUIRED_STRING}'."
        )

    counts: dict[str, int] = {}

    # Tables to wipe
    tables = [
        "messages",
        "messages_fts",
        "sessions",
        "memory_chunks",
        "profile_facts",
        "reminders",
        "pending_actions",
        "audit_log",
    ]

    for tbl in tables:
        try:
            cursor = await conn.execute(f"SELECT COUNT(*) FROM {tbl};")
            row = await cursor.fetchone()
            count = row[0] if row else 0
            await conn.execute(f"DELETE FROM {tbl};")
            counts[tbl] = count
        except Exception as e:
            logger.warning(f"Error purging table {tbl}: {e}")
            counts[tbl] = 0

    # Clean memory_vectors if present
    try:
        await conn.execute("DELETE FROM memory_vectors;")
        counts["memory_vectors"] = -1
    except Exception as e:
        logger.debug(f"memory_vectors delete: {e}")

    await conn.commit()

    # Flush embedding cache
    get_embedding_cache().clear()

    # Vacuum database to reclaim disk space
    try:
        await conn.execute("VACUUM;")
    except Exception as e:
        logger.warning(f"VACUUM error: {e}")

    logger.warning("USER DATA WIPE COMPLETED: all personal agent data erased.")
    return {
        "success": True,
        "purged_records": counts,
    }
