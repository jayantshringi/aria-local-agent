"""Host Operating System actions and telemetry tool for Aria and Antigravity."""

import platform
from typing import Any

import psutil

from app.tools.apps import AppsOpenTool
from tools.base import BaseTool, ExecutionContext, RiskLevel, ToolResult


class OSActionsTool(BaseTool):
    """Executes safe host OS actions, queries system status, and launches allow-listed applications."""

    name = "os.action"
    description = (
        "Inspect host OS state or launch allow-listed desktop applications. "
        "Actions: 'system_info', 'list_processes', 'launch_app'."
    )
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["system_info", "list_processes", "launch_app"],
                "description": "Operating system action to execute",
            },
            "app_name": {
                "type": "string",
                "description": "Application name to launch (when action is 'launch_app')",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum items to return for list_processes (default 10)",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._apps_tool = AppsOpenTool()

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        action = args.get("action", "system_info").lower().strip()

        if action == "system_info":
            return self._get_system_info()
        elif action == "list_processes":
            limit = min(int(args.get("limit") or 10), 50)
            return self._list_processes(limit)
        elif action == "launch_app":
            app_name = args.get("app_name", "")
            return await self._apps_tool.execute({"app_name": app_name}, context)
        else:
            return ToolResult(
                success=False,
                error=f"Unsupported OS action: '{action}'. Choose from: system_info, list_processes, launch_app",
            )

    def _get_system_info(self) -> ToolResult:
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        info = {
            "os": platform.system(),
            "os_release": platform.release(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_total_gb": round(vm.total / (1024**3), 2),
            "ram_used_gb": round(vm.used / (1024**3), 2),
            "ram_percent": vm.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_percent": disk.percent,
        }
        output_lines = [
            f"OS: {info['os']} {info['os_release']}",
            f"CPU Usage: {info['cpu_percent']}%",
            f"RAM: {info['ram_used_gb']}GB / {info['ram_total_gb']}GB ({info['ram_percent']}%)",
            f"Disk: {info['disk_free_gb']}GB free / {info['disk_total_gb']}GB ({info['disk_percent']}%)",
        ]
        return ToolResult(
            success=True,
            output="\n".join(output_lines),
            metadata=info,
        )

    def _list_processes(self, limit: int) -> ToolResult:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = p.info
                if info["name"]:
                    procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: (x.get("cpu_percent") or 0.0), reverse=True)
        top = procs[:limit]
        lines = [
            f"PID {p['pid']}: {p['name']} (CPU: {p.get('cpu_percent', 0)}%, RAM: {round(p.get('memory_percent', 0) or 0, 1)}%)"
            for p in top
        ]
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "No processes found.",
            metadata={"count": len(top), "processes": top},
        )


__all__ = ["OSActionsTool", "AppsOpenTool"]
