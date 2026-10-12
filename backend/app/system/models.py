"""Ollama model switcher and runtime management."""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite
import httpx

from app.config import get_settings

logger = logging.getLogger("aria.system.models")


async def get_active_chat_model(conn: aiosqlite.Connection) -> str:
    """Retrieve the currently configured chat model from SQLite settings or environment default."""
    cursor = await conn.execute(
        "SELECT value FROM settings WHERE key = 'active_chat_model' LIMIT 1;"
    )
    row = await cursor.fetchone()
    if row and row[0]:
        return row[0]
    return get_settings().ollama_chat_model


async def set_active_chat_model(conn: aiosqlite.Connection, model_name: str) -> str:
    """Persist newly chosen active chat model into SQLite settings."""
    clean_name = model_name.strip()
    await conn.execute(
        "INSERT INTO settings (key, value) VALUES ('active_chat_model', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
        (clean_name,),
    )
    await conn.commit()
    logger.info(f"Switched active chat model to: {clean_name}")
    return clean_name


async def list_installed_ollama_models() -> dict[str, Any]:
    """Query local Ollama instance for installed models."""
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"

    models_list: list[dict[str, Any]] = []
    online = False

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                online = True
                for m in data.get("models", []):
                    details = m.get("details", {})
                    models_list.append(
                        {
                            "name": m.get("name"),
                            "size": m.get("size", 0),
                            "modified_at": m.get("modified_at", ""),
                            "parameter_size": details.get("parameter_size", "unknown"),
                            "quantization_level": details.get("quantization_level", "unknown"),
                            "family": details.get("family", "unknown"),
                        }
                    )
    except Exception as e:
        logger.debug(f"Could not connect to Ollama tags endpoint: {e}")

    return {
        "ollama_online": online,
        "models": models_list,
        "ollama_url": settings.ollama_base_url,
    }
