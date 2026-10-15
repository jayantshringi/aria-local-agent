"""Background daemon worker lifecycle manager for Aria."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("aria.daemons.manager")


@dataclass
class DaemonStatus:
    """Current runtime status of a background daemon worker."""

    name: str
    is_running: bool
    iterations: int = 0
    last_run_at: str | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseDaemon(ABC):
    """Abstract base class for all Aria background proactive daemons."""

    name: str
    interval_seconds: float = 30.0

    def __init__(self) -> None:
        self._is_running = False
        self._task: asyncio.Task[None] | None = None
        self._iterations = 0
        self._last_run_at: datetime | None = None
        self._last_error: str | None = None
        self._extra_meta: dict[str, Any] = {}

    @abstractmethod
    async def run_iteration(self) -> None:
        """Execute one autonomous cycle of the daemon."""
        raise NotImplementedError

    async def start(self) -> None:
        """Start the background daemon loop."""
        if self._is_running:
            return

        self._is_running = True
        self._task = asyncio.create_task(self._loop(), name=f"daemon-{self.name}")
        logger.info(f"Started daemon '{self.name}' (interval: {self.interval_seconds}s)")

    async def stop(self) -> None:
        """Stop the background daemon loop."""
        if not self._is_running:
            return

        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info(f"Stopped daemon '{self.name}'")

    async def _loop(self) -> None:
        """Internal continuous worker loop."""
        while self._is_running:
            try:
                self._last_run_at = datetime.now(UTC)
                await self.run_iteration()
                self._iterations += 1
                self._last_error = None
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._last_error = str(exc)
                logger.error(f"Error in daemon '{self.name}': {exc}", exc_info=True)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    def get_status(self) -> DaemonStatus:
        """Retrieve current status snapshot."""
        return DaemonStatus(
            name=self.name,
            is_running=self._is_running,
            iterations=self._iterations,
            last_run_at=self._last_run_at.isoformat() if self._last_run_at else None,
            last_error=self._last_error,
            metadata=self._extra_meta,
        )


class DaemonManager:
    """Coordinates registration and lifecycle of all background daemons."""

    def __init__(self) -> None:
        self._daemons: dict[str, BaseDaemon] = {}

    def register(self, daemon: BaseDaemon) -> None:
        """Register a daemon worker."""
        self._daemons[daemon.name] = daemon
        logger.debug(f"Registered daemon '{daemon.name}'")

    def get(self, name: str) -> BaseDaemon | None:
        return self._daemons.get(name)

    async def start_all(self) -> None:
        """Start all registered daemons."""
        for d in self._daemons.values():
            await d.start()

    async def stop_all(self) -> None:
        """Stop all registered daemons."""
        for d in self._daemons.values():
            await d.stop()

    def get_all_statuses(self) -> list[DaemonStatus]:
        """Return status for all registered daemons."""
        return [d.get_status() for d in self._daemons.values()]


# Global daemon manager singleton
daemon_manager = DaemonManager()

__all__ = ["BaseDaemon", "DaemonStatus", "DaemonManager", "daemon_manager"]
