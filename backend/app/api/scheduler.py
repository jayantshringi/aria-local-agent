"""REST API routes for background scheduler status, manual reminder triggers, and briefings."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.security import get_current_device
from app.scheduler.briefing import generate_morning_briefing
from app.scheduler.engine import scheduler

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])


class TriggerBriefingRequest(BaseModel):
    language: str | None = None
    persist_message: bool = True


@router.get("/status")
async def get_scheduler_status(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Retrieve scheduler running status, job details, and polling interval."""
    return scheduler.get_status()


@router.post("/poll")
async def trigger_reminder_poll(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Manually trigger due reminder poll."""
    fired = await scheduler.poll_due_reminders()
    return {
        "status": "success",
        "reminders_fired_count": len(fired),
        "fired_reminders": fired,
    }


@router.post("/briefing")
async def trigger_morning_briefing(
    req: TriggerBriefingRequest,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Manually generate and broadcast a morning daily briefing."""
    result = await generate_morning_briefing(
        language=req.language,
        persist_message=req.persist_message,
    )
    return {
        "status": "success",
        "briefing": result,
    }
