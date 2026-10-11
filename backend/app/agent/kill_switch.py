"""Global emergency kill switch to immediately halt running tasks and clear pending queues."""

import asyncio
import logging
from typing import Any

from app.api.sync_hub import sync_hub
from app.db import repository
from app.db.connection import get_database

logger = logging.getLogger("aria.agent.kill_switch")


class KillSwitch:
    """Singleton kill switch manager coordinating task cancellation and queue clearing."""

    def __init__(self) -> None:
        self._killed_event = asyncio.Event()
        self._active_tasks: set[asyncio.Task[Any]] = set()
        self._lock = asyncio.Lock()

    @property
    def is_active(self) -> bool:
        """True if the agent has been halted by the kill switch."""
        return self._killed_event.is_set()

    def register_task(self, task: asyncio.Task[Any]) -> None:
        """Register an active task to be cancelled if kill switch is triggered."""
        self._active_tasks.add(task)
        task.add_done_callback(lambda t: self._active_tasks.discard(t))

    async def trigger(self, reason: str = "Emergency kill switch activated") -> dict[str, Any]:
        """
        Immediately halt all running agent operations:
        1. Set killed flag.
        2. Cancel in-flight asyncio tasks.
        3. Clear pending actions in database to 'killed'.
        4. Broadcast kill event to all connected devices.
        """
        self._killed_event.set()
        logger.warning(f"KILL SWITCH TRIGGERED: {reason}")

        # Cancel active background tasks
        cancelled_tasks = 0
        async with self._lock:
            for task in list(self._active_tasks):
                if not task.done():
                    task.cancel()
                    cancelled_tasks += 1
            self._active_tasks.clear()

        # Update pending actions in DB
        db = get_database()
        cancelled_actions = 0
        try:
            async with db.get_connection() as conn:
                cancelled_actions = await repository.cancel_all_pending_actions(
                    conn, resolved_by="kill_switch"
                )
        except Exception as e:
            logger.error(f"Failed to cancel pending actions in DB during kill: {e}")

        # Broadcast across WebSocket to all client devices
        try:
            await sync_hub.broadcast_all(
                {
                    "type": "agent_killed",
                    "reason": reason,
                    "cancelled_tasks": cancelled_tasks,
                    "cancelled_actions": cancelled_actions,
                }
            )
        except Exception as e:
            logger.debug(f"Failed to broadcast kill event: {e}")

        return {
            "killed": True,
            "reason": reason,
            "cancelled_tasks": cancelled_tasks,
            "cancelled_actions": cancelled_actions,
        }

    def reset(self) -> None:
        """Reset the kill switch to normal operation."""
        self._killed_event.clear()
        logger.info("Kill switch reset. Agent operations resumed.")


# Global singleton
kill_switch = KillSwitch()
