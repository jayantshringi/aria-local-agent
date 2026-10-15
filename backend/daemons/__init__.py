"""Aria Daemons: Background workers for continuous monitoring, notifications, and proactive task handling."""

from daemons.file_watcher import FileWatcherDaemon
from daemons.manager import BaseDaemon, DaemonManager, DaemonStatus, daemon_manager
from daemons.system_monitor import SystemMonitorDaemon
from daemons.task_scheduler import TaskSchedulerDaemon


def register_default_daemons(manager: DaemonManager = daemon_manager) -> None:
    """Register all standard background proactive workers."""
    manager.register(SystemMonitorDaemon())
    manager.register(FileWatcherDaemon())
    manager.register(TaskSchedulerDaemon())


# Register defaults on import
register_default_daemons(daemon_manager)

__all__ = [
    "BaseDaemon",
    "DaemonStatus",
    "DaemonManager",
    "daemon_manager",
    "SystemMonitorDaemon",
    "FileWatcherDaemon",
    "TaskSchedulerDaemon",
    "register_default_daemons",
]
