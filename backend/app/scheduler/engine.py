"""Background scheduler engine powered by APScheduler for reminders and proactive tasks."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.api.sync_hub import sync_hub
from app.config import get_settings
from app.db import repository
from app.db.connection import get_database
from app.scheduler.briefing import generate_morning_briefing

logger = logging.getLogger("aria.scheduler.engine")


def _calc_next_due(current_due_str: str, repeat_rule: str) -> str | None:
    """Compute the next due ISO timestamp based on repeat rule."""
    try:
        dt = datetime.fromisoformat(current_due_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    rule = repeat_rule.lower().strip()
    if rule == "daily":
        next_dt = dt + timedelta(days=1)
    elif rule == "weekly":
        next_dt = dt + timedelta(weeks=1)
    elif rule == "monthly":
        next_dt = dt + timedelta(days=30)
    else:
        return None

    return next_dt.isoformat()


class AriaScheduler:
    """Async background task scheduler for reminders, proactive briefings, and maintenance."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._running = False
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    async def poll_due_reminders(self) -> list[dict[str, Any]]:
        """Check database for any due reminders and broadcast them to all clients."""
        now_iso = datetime.now(UTC).isoformat()
        db = get_database()
        fired_reminders: list[dict[str, Any]] = []

        try:
            async with db.get_connection() as conn:
                due = await repository.get_due_reminders(conn, now_iso)
                for reminder in due:
                    r_id = reminder["id"]
                    repeat = reminder.get("repeat_rule")

                    if repeat:
                        next_due = _calc_next_due(reminder["due_at"], repeat)
                        if next_due:
                            await conn.execute(
                                "UPDATE reminders SET due_at = ? WHERE id = ?",
                                (next_due, r_id),
                            )
                            await conn.commit()
                        else:
                            await repository.update_reminder_status(conn, r_id, "completed")
                    else:
                        await repository.update_reminder_status(conn, r_id, "completed")

                    fired_reminders.append(reminder)

                    logger.info(f"Reminder fired: '{reminder['text']}' (ID: {r_id[:8]})")
                    await sync_hub.broadcast_all(
                        {
                            "type": "reminder_fired",
                            "reminder": reminder,
                        }
                    )

        except Exception as exc:
            logger.error(f"Error checking due reminders: {exc}", exc_info=True)

        return fired_reminders

    async def run_daily_briefing_job(self) -> None:
        """Trigger scheduled daily morning briefing."""
        logger.info("Executing scheduled morning daily briefing job...")
        try:
            await generate_morning_briefing()
        except Exception as exc:
            logger.error(f"Error running scheduled morning briefing: {exc}", exc_info=True)

    def start(self) -> None:
        """Start the background scheduler."""
        if self._running:
            return

        settings = get_settings()

        # Job 1: Reminder polling
        self._scheduler.add_job(
            self.poll_due_reminders,
            "interval",
            seconds=settings.reminder_poll_interval,
            id="poll_due_reminders",
            replace_existing=True,
        )

        # Job 2: Morning daily briefing
        self._scheduler.add_job(
            self.run_daily_briefing_job,
            "cron",
            hour=settings.briefing_hour,
            minute=settings.briefing_minute,
            id="daily_morning_briefing",
            replace_existing=True,
        )

        self._scheduler.start()
        self._running = True
        logger.info(
            f"AriaScheduler started (reminder poll: {settings.reminder_poll_interval}s, "
            f"morning briefing: {settings.briefing_hour:02d}:{settings.briefing_minute:02d})"
        )

    def shutdown(self) -> None:
        """Stop background scheduler."""
        if not self._running:
            return
        try:
            self._scheduler.shutdown(wait=False)
        except Exception as exc:
            logger.warning(f"Error during scheduler shutdown: {exc}")
        self._running = False
        logger.info("AriaScheduler stopped.")

    def get_status(self) -> dict[str, Any]:
        """Return operational status and registered jobs."""
        jobs_info = []
        if self._running:
            for job in self._scheduler.get_jobs():
                jobs_info.append(
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run_time": (
                            job.next_run_time.isoformat() if job.next_run_time else None
                        ),
                    }
                )

        settings = get_settings()
        return {
            "running": self._running,
            "poll_interval_seconds": settings.reminder_poll_interval,
            "briefing_schedule": f"{settings.briefing_hour:02d}:{settings.briefing_minute:02d}",
            "jobs": jobs_info,
        }


# Global singleton instance
scheduler = AriaScheduler()
