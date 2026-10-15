"""Unit and integration tests for background proactive daemons."""

import asyncio
from pathlib import Path

import pytest

from daemons.file_watcher import FileWatcherDaemon
from daemons.manager import BaseDaemon, DaemonManager
from daemons.system_monitor import SystemMonitorDaemon
from daemons.task_scheduler import TaskSchedulerDaemon


class DummyTestDaemon(BaseDaemon):
    name = "dummy_daemon"
    interval_seconds = 0.05

    def __init__(self):
        super().__init__()
        self.count = 0

    async def run_iteration(self):
        self.count += 1
        self._extra_meta = {"count": self.count}


@pytest.mark.asyncio
async def test_daemon_manager_lifecycle():
    manager = DaemonManager()
    dummy = DummyTestDaemon()
    manager.register(dummy)

    assert manager.get("dummy_daemon") is dummy

    await manager.start_all()
    await asyncio.sleep(0.15)
    statuses = manager.get_all_statuses()
    assert len(statuses) == 1
    assert statuses[0].is_running is True
    assert statuses[0].iterations >= 1
    assert statuses[0].metadata.get("count", 0) >= 1

    await manager.stop_all()
    stopped_statuses = manager.get_all_statuses()
    assert stopped_statuses[0].is_running is False


@pytest.mark.asyncio
async def test_system_monitor_daemon():
    daemon = SystemMonitorDaemon(cpu_threshold=99.0, ram_threshold=99.0)
    await daemon.run_iteration()

    status = daemon.get_status()
    assert "cpu_percent" in status.metadata
    assert "ram_percent" in status.metadata
    assert "disk_percent" in status.metadata


@pytest.mark.asyncio
async def test_file_watcher_daemon(tmp_path: Path):
    watch_dir = tmp_path / "custom_watch_folder"
    watch_dir.mkdir()
    watcher = FileWatcherDaemon(watch_roots=[watch_dir])

    # Initial snapshot
    await watcher.run_iteration()
    assert watcher.get_status().metadata["total_files_watched"] == 0

    # Add file
    test_file = watch_dir / "sample.txt"
    test_file.write_text("initial content", encoding="utf-8")

    await watcher.run_iteration()
    meta = watcher.get_status().metadata
    assert meta["total_files_watched"] == 1
    assert meta["last_changes"]["added"] == 1

    # Modify file
    test_file.write_text("updated content with more text", encoding="utf-8")
    await watcher.run_iteration()
    meta2 = watcher.get_status().metadata
    assert meta2["last_changes"]["modified"] == 1


@pytest.mark.asyncio
async def test_task_scheduler_daemon():
    scheduler_daemon = TaskSchedulerDaemon()
    await scheduler_daemon.run_iteration()
    status = scheduler_daemon.get_status()
    assert "last_check_at" in status.metadata
