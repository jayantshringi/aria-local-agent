"""Full user data export generator supporting JSON and human-readable Markdown."""

from __future__ import annotations

import io
import json
import logging
import time
import zipfile
from typing import Any

import aiosqlite

logger = logging.getLogger("aria.system.export")


async def export_full_data_json(conn: aiosqlite.Connection) -> dict[str, Any]:
    """Extract complete database contents into a structured JSON export dictionary."""
    # 1. Sessions & Messages
    sessions_cursor = await conn.execute(
        "SELECT id, title, created_at, updated_at, summary, device_id "
        "FROM sessions ORDER BY created_at ASC;"
    )
    sessions_rows = await sessions_cursor.fetchall()

    sessions: list[dict[str, Any]] = []
    for s in sessions_rows:
        s_id = s[0]
        msg_cursor = await conn.execute(
            "SELECT id, role, content, created_at, tokens, meta_json "
            "FROM messages WHERE session_id = ? ORDER BY created_at ASC;",
            (s_id,),
        )
        msg_rows = await msg_cursor.fetchall()
        messages = [
            {
                "id": m[0],
                "role": m[1],
                "content": m[2],
                "created_at": m[3],
                "tokens": m[4],
                "meta": json.loads(m[5]) if m[5] else {},
            }
            for m in msg_rows
        ]
        sessions.append(
            {
                "id": s[0],
                "title": s[1],
                "created_at": s[2],
                "updated_at": s[3],
                "summary": s[4],
                "device_id": s[5],
                "messages": messages,
            }
        )

    # 2. Profile Facts
    facts_cursor = await conn.execute(
        "SELECT id, key, value, status, confidence, created_at, updated_at "
        "FROM profile_facts ORDER BY key ASC;"
    )
    facts_rows = await facts_cursor.fetchall()
    profile_facts = [
        {
            "id": f[0],
            "key": f[1],
            "value": f[2],
            "status": f[3],
            "confidence": f[4],
            "created_at": f[5],
            "updated_at": f[6],
        }
        for f in facts_rows
    ]

    # 3. Reminders
    rem_cursor = await conn.execute(
        "SELECT id, text, due_at, repeat_rule, status FROM reminders ORDER BY due_at ASC;"
    )
    rem_rows = await rem_cursor.fetchall()
    reminders = [
        {
            "id": r[0],
            "text": r[1],
            "due_at": r[2],
            "repeat_rule": r[3],
            "status": r[4],
        }
        for r in rem_rows
    ]

    # 4. Audit Log
    audit_cursor = await conn.execute(
        "SELECT id, ts, tool, args_json, risk_level, status, approved_by, result_json, error "
        "FROM audit_log ORDER BY ts DESC LIMIT 500;"
    )
    audit_rows = await audit_cursor.fetchall()
    audit_log = [
        {
            "id": a[0],
            "timestamp": a[1],
            "tool": a[2],
            "args": json.loads(a[3]) if a[3] else {},
            "risk_level": a[4],
            "status": a[5],
            "approved_by": a[6],
            "result": json.loads(a[7]) if a[7] else None,
            "error": a[8],
        }
        for a in audit_rows
    ]

    # 5. Settings
    settings_cursor = await conn.execute("SELECT key, value FROM settings;")
    settings_rows = await settings_cursor.fetchall()
    settings = {row[0]: row[1] for row in settings_rows}

    return {
        "version": "1.0",
        "exported_at": time.time(),
        "exported_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sessions": sessions,
        "profile_facts": profile_facts,
        "reminders": reminders,
        "audit_log": audit_log,
        "settings": settings,
    }


def generate_export_zip(export_data: dict[str, Any]) -> bytes:
    """Package JSON and human-readable Markdown files into a ZIP archive."""
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Full JSON dump
        json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")
        zf.writestr("aria_export.json", json_bytes)

        # 2. Markdown sessions
        for s in export_data.get("sessions", []):
            safe_title = "".join(
                c for c in s.get("title", "chat") if c.isalnum() or c in (" ", "_", "-")
            ).strip()
            filename = f"sessions/{safe_title[:40]}_{s['id'][:8]}.md"

            md_lines = [
                f"# Session: {s.get('title', 'Untitled')}",
                f"- **ID:** `{s['id']}`",
                f"- **Created:** {s.get('created_at')}",
                f"- **Summary:** {s.get('summary') or 'None'}",
                "",
                "---",
                "",
            ]
            for m in s.get("messages", []):
                role_label = "**User**" if m["role"] == "user" else "**Aria**"
                md_lines.append(f"{role_label} *({m['created_at']})*:\n\n{m['content']}\n")
                md_lines.append("")

            zf.writestr(filename, "\n".join(md_lines).encode("utf-8"))

        # 3. Profile facts markdown
        facts = export_data.get("profile_facts", [])
        fact_lines = ["# Profile Memory Facts\n"]
        for f in facts:
            fact_lines.append(
                f"- **{f['key']}**: {f['value']} *(Status: {f['status']}, Confidence: {f.get('confidence', 1.0)})*"
            )
        zf.writestr("profile_facts.md", "\n".join(fact_lines).encode("utf-8"))

        # 4. Reminders markdown
        rems = export_data.get("reminders", [])
        rem_lines = ["# Reminders\n"]
        for r in rems:
            rem_lines.append(f"- **{r['text']}** (Due: {r['due_at']}, Status: {r['status']})")
        zf.writestr("reminders.md", "\n".join(rem_lines).encode("utf-8"))

    return zip_buffer.getvalue()
