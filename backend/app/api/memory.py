"""Memory and profile facts API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.security import get_current_device
from app.db.connection import get_database
from app.memory.profile import (
    get_all_facts,
    remove_fact,
    set_fact,
)
from app.memory.retrieval import hybrid_search
from app.memory.summarizer import summarize_session

router = APIRouter(tags=["memory"])


class CreateFactRequest(BaseModel):
    key: str = Field(..., min_length=1, description="Fact key / identifier")
    value: str = Field(..., min_length=1, description="Fact value")
    status: str = Field(default="approved", description="Status ('approved' or 'pending')")


class UpdateFactRequest(BaseModel):
    status: str | None = Field(
        default=None, description="Status ('approved', 'rejected', or 'pending')"
    )
    value: str | None = Field(default=None, description="Updated fact value")


# ---------------------------------------------------------------------------
# Hybrid Memory Search
# ---------------------------------------------------------------------------


@router.get("/api/v1/memory/search")
async def search_memory(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(5, ge=1, le=20, description="Max results"),
    token_budget: int = Query(1000, ge=100, le=4000, description="Token budget"),
    _: dict[str, Any] = Depends(get_current_device),
) -> list[dict[str, Any]]:
    """Hybrid search over past sessions and memory chunks combining FTS5 and sqlite-vec."""
    db = get_database()
    async with db.get_connection() as conn:
        return await hybrid_search(conn, query=q, limit=limit, token_budget=token_budget)


# ---------------------------------------------------------------------------
# Profile Facts (About Me)
# ---------------------------------------------------------------------------


@router.get("/api/v1/memory/facts")
async def list_facts(
    status: str | None = Query(None, description="Filter by status (pending, approved, rejected)"),
    _: dict[str, Any] = Depends(get_current_device),
) -> list[dict[str, Any]]:
    """List profile memory facts."""
    db = get_database()
    async with db.get_connection() as conn:
        return await get_all_facts(conn, status=status)


@router.post("/api/v1/memory/facts", status_code=status.HTTP_201_CREATED)
async def create_fact(
    req: CreateFactRequest,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Create a new profile fact."""
    db = get_database()
    async with db.get_connection() as conn:
        return await set_fact(conn, key=req.key, value=req.value, status=req.status)


@router.patch("/api/v1/memory/facts/{fact_id}")
async def update_fact(
    fact_id: str,
    req: UpdateFactRequest,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Approve, reject, or update value of a profile fact."""
    db = get_database()
    async with db.get_connection() as conn:
        from app.db import repository

        updated = await repository.update_profile_fact(
            conn, fact_id=fact_id, status=req.status, value=req.value
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Profile fact not found"
            )
        return updated


@router.delete("/api/v1/memory/facts/{fact_id}")
async def delete_fact(
    fact_id: str,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, bool]:
    """Permanently delete a profile fact."""
    db = get_database()
    async with db.get_connection() as conn:
        deleted = await remove_fact(conn, fact_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Profile fact not found"
            )
        return {"deleted": True}


# ---------------------------------------------------------------------------
# Session Summarization
# ---------------------------------------------------------------------------


@router.post("/api/v1/memory/sessions/{session_id}/summarize")
async def trigger_session_summarize(
    session_id: str,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Generate and store summary for a specific session."""
    db = get_database()
    async with db.get_connection() as conn:
        summary = await summarize_session(conn, session_id)
        if summary is None:
            return {
                "session_id": session_id,
                "summary": None,
                "message": "Not enough messages to summarize",
            }
        return {"session_id": session_id, "summary": summary}
