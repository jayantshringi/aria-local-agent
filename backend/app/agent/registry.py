"""Tool registry for registering, finding, and inspecting agent tools."""

import logging
from typing import Any

from app.agent.base_tool import BaseTool

logger = logging.getLogger("aria.agent.registry")


class ToolRegistry:
    """Manages active tools and serializes definitions for LLM invocation."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting already registered tool '{tool.name}'")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool '{tool.name}' ({tool.risk_level.value})")

    def unregister(self, tool_name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(tool_name, None)

    def get(self, tool_name: str) -> BaseTool | None:
        """Lookup tool by name."""
        return self._tools.get(tool_name)

    def list_tools(self) -> list[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_ollama_tools(self) -> list[dict[str, Any]]:
        """Return all tool definitions formatted for Ollama tool calling."""
        return [tool.to_ollama_tool() for tool in self._tools.values()]

    def get_catalog_summary(self) -> list[dict[str, Any]]:
        """Return human-readable tool catalog."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk_level": t.risk_level.value,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]


# Global singleton
tool_registry = ToolRegistry()
