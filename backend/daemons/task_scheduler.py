"""Background daemon for scheduled proactive tasks, reminders, and idle housekeeping."""

import logging
from datetime import UTC, datetime

from app.db import repository
from app.db.connection import get_database
from app.scheduler.engine import scheduler
from daemons.manager import BaseDaemon

logger = logging.getLogger("aria.daemons.task_scheduler")


class TaskSchedulerDaemon(BaseDaemon):
    """Monitors scheduled reminders, fires alerts, and performs proactive background housekeeping."""

    name = "task_scheduler"
    interval_seconds = 20.0

    async def run_iteration(self) -> None:
        """Poll for due reminders and execute periodic housekeeping."""
        now_iso = datetime.now(UTC).isoformat()
        fired = await scheduler.poll_due_reminders()

        db = get_database()
        async with db.get_connection() as conn:
            try:
                await repository.delete_expired_pairing_codes(conn, now_iso)
            except Exception as house_err:
                logger.debug(f"Housekeeping pairing cleanup notice: {house_err}")

        self._extra_meta = {
            "last_check_at": now_iso,
            "due_count_processed": len(fired),
        }


__all__ = ["TaskSchedulerDaemon"]
