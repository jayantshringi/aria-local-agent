"""Application launcher tool restricted to configured allowlist."""

import shutil
import subprocess
from typing import Any

from app.agent.base_tool import BaseTool, ExecutionContext, RiskLevel, ToolResult
from app.config import get_settings


class AppsOpenTool(BaseTool):
    """Tool to launch an approved desktop application."""

    @property
    def name(self) -> str:
        return "apps.open"

    @property
    def description(self) -> str:
        return "Open a whitelisted application on the host machine (e.g., 'notepad', 'calc'). (Requires approval)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name of the application to open (must be in allowlist)",
                },
            },
            "required": ["app_name"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        settings = get_settings()
        allowed = settings.allowed_apps_list
        app_name = args.get("app_name", "").strip().lower()

        if not app_name:
            return ToolResult(success=False, output="", error="Application name cannot be empty")

        if app_name not in allowed:
            allowed_str = ", ".join(allowed)
            return ToolResult(
                success=False,
                output="",
                error=f"Application '{app_name}' is not in the allowlist ({allowed_str}).",
            )

        # Check if binary or command exists
        executable = shutil.which(app_name) or app_name
        try:
            # Spawn process safely without shell=True
            subprocess.Popen([executable])
            return ToolResult(
                success=True,
                output=f"Application '{app_name}' launched successfully.",
                meta={"app_name": app_name},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to launch '{app_name}': {e}",
            )
