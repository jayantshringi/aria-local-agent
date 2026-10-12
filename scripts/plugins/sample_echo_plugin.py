"""Sample plugin tool demonstrating Aria's dynamic plugin engine.

To install this plugin, copy this file into ~/.aria/plugins/ (or ARIA_PLUGINS_DIR).
"""

from typing import Any

from app.agent.base_tool import BaseTool, ExecutionContext, RiskLevel, ToolResult


class EchoPluginTool(BaseTool):
    """Simple plugin tool that returns an echoed string for demonstration."""

    @property
    def name(self) -> str:
        return "plugin.echo"

    @property
    def description(self) -> str:
        return "Sample custom plugin tool that echoes message text."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Message to echo back",
                }
            },
            "required": ["message"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        msg = args.get("message", "")
        return ToolResult(
            success=True,
            output=f"Plugin Echo: {msg}",
            meta={"custom_plugin": True},
        )
