"""Profile memory module managing user facts and preferences."""

from typing import Any

import aiosqlite

from app.db import repository


async def get_approved_facts(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    """Retrieve all facts with status 'approved'."""
    return await repository.list_profile_facts(conn, status="approved")


async def get_all_facts(
    conn: aiosqlite.Connection, status: str | None = None
) -> list[dict[str, Any]]:
    """Retrieve profile facts, optionally filtered by status ('pending', 'approved', 'rejected')."""
    return await repository.list_profile_facts(conn, status=status)


async def approve_fact(conn: aiosqlite.Connection, fact_id: str) -> dict[str, Any] | None:
    """Approve a pending fact so it enters the prompt."""
    return await repository.update_profile_fact(conn, fact_id=fact_id, status="approved")


async def reject_fact(conn: aiosqlite.Connection, fact_id: str) -> dict[str, Any] | None:
    """Reject a fact so it never enters the prompt."""
    return await repository.update_profile_fact(conn, fact_id=fact_id, status="rejected")


async def set_fact(
    conn: aiosqlite.Connection,
    key: str,
    value: str,
    status: str = "approved",
    confidence: float = 1.0,
) -> dict[str, Any]:
    """Manually add or update a profile fact."""
    return await repository.create_profile_fact(
        conn, key=key.strip(), value=value.strip(), status=status, confidence=confidence
    )


async def remove_fact(conn: aiosqlite.Connection, fact_id: str) -> bool:
    """Permanently delete a profile fact."""
    return await repository.delete_profile_fact(conn, fact_id=fact_id)


def format_facts_for_prompt(facts: list[dict[str, Any]]) -> str:
    """
    Format approved facts into prompt context block.
    Hard rule: only approved facts should be supplied to this function.
    """
    approved = [f for f in facts if f.get("status") == "approved"]
    if not approved:
        return ""

    lines = ["## User Profile & Approved Facts"]
    for fact in approved:
        key = fact.get("key", "").strip()
        val = fact.get("value", "").strip()
        if key and val:
            lines.append(f"- **{key}**: {val}")

    return "\n".join(lines)
