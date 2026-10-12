"""Hardware resource telemetry and local system diagnostics."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import time
from typing import Any

from app.config import get_settings
from app.memory.cache import get_embedding_cache

logger = logging.getLogger("aria.system.resources")
_PROCESS_START_TIME = time.time()


def get_system_telemetry() -> dict[str, Any]:
    """
    Collect real-time host resource statistics (CPU, RAM, Disk, Uptime)
    without making any external network requests.
    """
    settings = get_settings()
    data_dir = settings.data_dir_path

    # Disk usage for the Aria data directory
    disk_total, disk_used, disk_free = 0, 0, 0
    disk_percent = 0.0
    try:
        du = shutil.disk_usage(str(data_dir))
        disk_total = du.total
        disk_used = du.used
        disk_free = du.free
        if disk_total > 0:
            disk_percent = round((disk_used / disk_total) * 100, 1)
    except Exception as e:
        logger.warning(f"Failed to read disk usage: {e}")

    # Memory and CPU using psutil if available, fallback gracefully
    cpu_percent = 0.0
    cpu_count = os.cpu_count() or 1
    mem_total, mem_used, mem_free, mem_percent = 0, 0, 0, 0.0

    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        mem_total = vm.total
        mem_used = vm.used
        mem_free = vm.available
        mem_percent = vm.percent
    except Exception as e:
        logger.debug(f"psutil query fallback: {e}")

    # Process and system metadata
    uptime = int(time.time() - _PROCESS_START_TIME)
    cache_stats = get_embedding_cache().stats()

    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": cpu_count,
        },
        "memory": {
            "total_bytes": mem_total,
            "used_bytes": mem_used,
            "available_bytes": mem_free,
            "percent": mem_percent,
        },
        "disk": {
            "total_bytes": disk_total,
            "used_bytes": disk_used,
            "free_bytes": disk_free,
            "percent": disk_percent,
            "path": str(data_dir),
        },
        "platform": {
            "os": platform.system(),
            "release": platform.release(),
            "arch": platform.machine(),
            "python": platform.python_version(),
        },
        "uptime_seconds": uptime,
        "embedding_cache": cache_stats,
    }
