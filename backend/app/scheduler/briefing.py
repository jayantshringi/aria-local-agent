"""Daily morning briefing generator for aria-local-agent."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.api.sync_hub import sync_hub
from app.config import get_settings
from app.db import repository
from app.db.connection import get_database
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger("aria.scheduler.briefing")


def _get_utc_now() -> datetime:
    return datetime.now(UTC)


async def generate_morning_briefing(
    ollama_client: OllamaClient | None = None,
    language: str | None = None,
    persist_message: bool = True,
) -> dict[str, Any]:
    """Generate and broadcast proactive morning briefing.

    Aggregates:
      - Today's reminders
      - Pending actions requiring owner attention
      - Recap of yesterday's active sessions and discussions

    Uses local Ollama chat model to craft a friendly, structured briefing.
    """
    settings = get_settings()
    target_language = language or settings.aria_language
    now = _get_utc_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1) - timedelta(microseconds=1)
    yesterday_start = today_start - timedelta(days=1)
    yesterday_end = today_start - timedelta(microseconds=1)

    db = get_database()
    async with db.get_connection() as conn:
        today_reminders = await repository.get_reminders_between(
            conn, today_start.isoformat(), today_end.isoformat()
        )
        pending_actions = await repository.list_pending_actions(conn, status="pending", limit=20)
        yesterday_sessions = await repository.get_sessions_between(
            conn, yesterday_start.isoformat(), yesterday_end.isoformat()
        )
        approved_facts = await repository.list_profile_facts(conn, status="approved")

    # Format aggregated context
    reminders_text = (
        "\n".join(f"- [{r['status']}] {r['text']} (Due: {r['due_at']})" for r in today_reminders)
        if today_reminders
        else "No reminders scheduled for today."
    )

    actions_text = (
        "\n".join(f"- Tool: {a['tool']} (Risk: {a['risk_level']})" for a in pending_actions)
        if pending_actions
        else "No pending actions requiring approval."
    )

    sessions_text = (
        "\n".join(
            f"- Session '{s['title']}': {s.get('summary') or 'Recent conversation'}"
            for s in yesterday_sessions
        )
        if yesterday_sessions
        else "No active sessions yesterday."
    )

    profile_text = (
        "\n".join(f"- {f['key']}: {f['value']}" for f in approved_facts[:5])
        if approved_facts
        else "No profile facts recorded."
    )

    system_prompt = (
        "You are Aria, a private, local-first personal AI assistant. "
        f"Your owner's configured language is '{target_language}'. "
        "Create a clean, encouraging, structured morning briefing. "
        "Use markdown formatting with sections: "
        "1. Today's Reminders & Agenda\n"
        "2. Action Items & Approvals\n"
        "3. Recap of Yesterday\n"
        "Keep it concise, clear, and focused on the day ahead."
    )

    user_content = (
        f"Date: {now.strftime('%A, %B %d, %Y')}\n\n"
        f"Owner Profile:\n{profile_text}\n\n"
        f"Today's Reminders:\n{reminders_text}\n\n"
        f"Pending Actions Needing Review:\n{actions_text}\n\n"
        f"Yesterday's Sessions:\n{sessions_text}\n\n"
        f"Please compose the morning briefing now in {target_language}."
    )

    client = ollama_client or OllamaClient()
    briefing_text = ""
    try:
        briefing_text = await client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.6,
        )
    except Exception as exc:
        logger.warning(
            f"Ollama briefing generation failed or offline: {exc}. Using fallback template."
        )
        briefing_text = (
            f"### ☀️ Good Morning!\n\n"
            f"**Date:** {now.strftime('%A, %B %d, %Y')}\n\n"
            f"#### 📅 Today's Agenda\n{reminders_text}\n\n"
            f"#### ⚡ Action Items\n{actions_text}\n\n"
            f"#### 📝 Yesterday's Activity\n{sessions_text}\n"
        )

    briefing_result = {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        "content": briefing_text,
        "language": target_language,
        "reminders_count": len(today_reminders),
        "pending_actions_count": len(pending_actions),
        "yesterday_sessions_count": len(yesterday_sessions),
    }

    # Optionally persist as message in a 'Morning Briefings' session
    if persist_message:
        async with db.get_connection() as conn:
            # Check for existing session or create one
            sessions = await repository.list_sessions(conn, limit=50)
            briefing_session = next(
                (s for s in sessions if s.get("title") == "Daily Briefings"), None
            )
            if not briefing_session:
                briefing_session = await repository.create_session(
                    conn, title="Daily Briefings", device_id="system"
                )
            await repository.create_message(
                conn,
                session_id=briefing_session["id"],
                role="assistant",
                content=briefing_text,
                meta_json={"type": "daily_briefing", "date": briefing_result["date"]},
            )

    # Broadcast notification to all connected devices in real time
    await sync_hub.broadcast_all(
        {
            "type": "daily_briefing",
            "briefing": briefing_result,
        }
    )

    return briefing_result
