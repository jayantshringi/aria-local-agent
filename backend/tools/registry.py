"""Standardized Antigravity tool registry."""

import logging
from typing import Any

from tools.base import BaseTool, RiskLevel

logger = logging.getLogger("aria.tools.registry")


class ToolRegistry:
    """Registry maintaining available tools with metadata and validation."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            logger.debug(f"Overwriting previously registered tool: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name} [{tool.risk_level}]")

    def unregister(self, tool_name: str) -> bool:
        """Remove a tool from the registry."""
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False

    def get(self, tool_name: str) -> BaseTool | None:
        """Retrieve a tool by name."""
        return self._tools.get(tool_name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def get_schemas(self) -> list[dict[str, Any]]:
        """Return standardized schemas for all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def get_tools_by_risk(self, risk_level: RiskLevel) -> list[BaseTool]:
        """Filter tools by risk level."""
        return [t for t in self._tools.values() if t.risk_level == risk_level]

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()


# Global tool registry singleton
tool_registry = ToolRegistry()
