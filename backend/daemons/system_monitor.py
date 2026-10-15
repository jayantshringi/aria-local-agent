"""Background daemon for continuous host health, CPU/RAM telemetry, and threshold alerting."""

import logging

import psutil

from app.api.sync_hub import sync_hub
from daemons.manager import BaseDaemon

logger = logging.getLogger("aria.daemons.system_monitor")


class SystemMonitorDaemon(BaseDaemon):
    """Monitors host resource usage and broadcasts alerts if thresholds are breached."""

    name = "system_monitor"
    interval_seconds = 30.0

    def __init__(
        self,
        cpu_threshold: float = 90.0,
        ram_threshold: float = 90.0,
        disk_threshold: float = 95.0,
    ) -> None:
        super().__init__()
        self.cpu_threshold = cpu_threshold
        self.ram_threshold = ram_threshold
        self.disk_threshold = disk_threshold

    async def run_iteration(self) -> None:
        """Inspect system metrics and dispatch notifications if critical thresholds are exceeded."""
        cpu = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        self._extra_meta = {
            "cpu_percent": cpu,
            "ram_percent": vm.percent,
            "disk_percent": disk.percent,
        }

        alerts = []
        if cpu >= self.cpu_threshold:
            alerts.append(f"High CPU utilization: {cpu}%")
        if vm.percent >= self.ram_threshold:
            alerts.append(f"High Memory utilization: {vm.percent}%")
        if disk.percent >= self.disk_threshold:
            alerts.append(f"Low Disk Space: {disk.percent}% used")

        if alerts:
            alert_msg = "; ".join(alerts)
            logger.warning(f"System Monitor Alert: {alert_msg}")
            try:
                await sync_hub.broadcast_all(
                    {
                        "type": "system_alert",
                        "alerts": alerts,
                        "metrics": self._extra_meta,
                    }
                )
            except Exception as exc:
                logger.debug(f"Broadcast system alert notice: {exc}")


__all__ = ["SystemMonitorDaemon"]
