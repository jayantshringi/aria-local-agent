"""Health and diagnostics endpoints."""

from typing import Any

from fastapi import APIRouter

from app.db.connection import get_database
from app.llm.ollama_client import OllamaClient

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/v1/health")
async def health_check() -> dict[str, Any]:
    """Check status of API server, SQLite database, and Ollama connection."""
    db_ok = False
    try:
        db = get_database()
        async with db.get_connection() as conn:
            async with conn.execute("SELECT 1") as cursor:
                row = await cursor.fetchone()
                db_ok = row is not None and row[0] == 1
    except Exception:
        db_ok = False

    ollama_client = OllamaClient()
    ollama_status = await ollama_client.check_health()

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": {"connected": db_ok, "wal_mode": True},
        "ollama": ollama_status,
    }
