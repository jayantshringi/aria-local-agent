"""Session management and message history endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.sync_hub import sync_hub
from app.auth.security import get_current_device
from app.db import repository
from app.db.connection import get_database

router = APIRouter(tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default="New Chat", description="Session title")


class UpdateSessionRequest(BaseModel):
    title: str | None = Field(default=None, description="Updated session title")
    summary: str | None = Field(default=None, description="Updated session summary")


class CreateMessageRequest(BaseModel):
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., min_length=1, description="Message textual content")
    tokens: int = Field(default=0, description="Token count")


# ---------------------------------------------------------------------------
# Session Endpoints
# ---------------------------------------------------------------------------


@router.get("/sessions")
@router.get("/api/v1/sessions")
async def list_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: dict[str, Any] = Depends(get_current_device),
) -> list[dict[str, Any]]:
    """List sessions ordered by update time descending."""
    db = get_database()
    async with db.get_connection() as conn:
        return await repository.list_sessions(conn, limit=limit, offset=offset)


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
@router.post("/api/v1/sessions", status_code=status.HTTP_201_CREATED)
async def create_new_session(
    req: CreateSessionRequest,
    current_device: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Create a new session."""
    db = get_database()
    async with db.get_connection() as conn:
        session = await repository.create_session(
            conn,
            title=req.title or "New Chat",
            device_id=current_device.get("id"),
        )
        await sync_hub.broadcast_all({"type": "session_created", "session": session})
        return session


@router.get("/sessions/{session_id}")
@router.get("/api/v1/sessions/{session_id}")
async def get_session_details(
    session_id: str,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Fetch session metadata by ID."""
    db = get_database()
    async with db.get_connection() as conn:
        session = await repository.get_session(conn, session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return session


@router.patch("/sessions/{session_id}")
@router.patch("/api/v1/sessions/{session_id}")
async def update_session_details(
    session_id: str,
    req: UpdateSessionRequest,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Update title or summary for an existing session."""
    db = get_database()
    async with db.get_connection() as conn:
        updated = await repository.update_session(
            conn, session_id, title=req.title, summary=req.summary
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        await sync_hub.broadcast_all({"type": "session_updated", "session": updated})
        return updated


@router.delete("/sessions/{session_id}")
@router.delete("/api/v1/sessions/{session_id}")
async def delete_session_and_messages(
    session_id: str,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Delete a session and all its messages."""
    db = get_database()
    async with db.get_connection() as conn:
        deleted = await repository.delete_session(conn, session_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        await sync_hub.broadcast_all({"type": "session_deleted", "session_id": session_id})
        return {"deleted": True, "session_id": session_id}


# ---------------------------------------------------------------------------
# Message Endpoints
# ---------------------------------------------------------------------------


@router.get("/sessions/{session_id}/messages")
@router.get("/api/v1/sessions/{session_id}/messages")
async def list_session_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: dict[str, Any] = Depends(get_current_device),
) -> list[dict[str, Any]]:
    """List messages for a session in chronological order."""
    db = get_database()
    async with db.get_connection() as conn:
        session = await repository.get_session(conn, session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return await repository.list_messages(conn, session_id, limit=limit, offset=offset)


@router.post("/sessions/{session_id}/messages", status_code=status.HTTP_201_CREATED)
@router.post("/api/v1/sessions/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def create_session_message(
    session_id: str,
    req: CreateMessageRequest,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Create and immediately persist a message."""
    db = get_database()
    async with db.get_connection() as conn:
        session = await repository.get_session(conn, session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return await repository.create_message(
            conn,
            session_id=session_id,
            role=req.role,
            content=req.content,
            tokens=req.tokens,
        )
