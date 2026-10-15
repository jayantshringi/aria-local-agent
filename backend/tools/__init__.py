"""Standardized Antigravity tool registry and implementations for Aria."""

from tools.base import BaseTool, ExecutionContext, RiskLevel, ToolResult
from tools.browser import BrowserAutomationTool
from tools.filesystem import (
    FilesDeleteTool,
    FilesMoveTool,
    FilesReadTool,
    FilesSearchTool,
    FilesWriteTool,
    FilesystemTool,
)
from tools.git_tool import GitTool
from tools.notes import NotesCreateTool, NotesSearchTool
from tools.os_actions import AppsOpenTool, OSActionsTool
from tools.registry import ToolRegistry, tool_registry
from tools.reminders import RemindersCreateTool, RemindersListTool
from tools.terminal import ShellRunTool, TerminalTool


def register_standard_tools(registry: ToolRegistry = tool_registry) -> None:
    """Register all standard Antigravity tools into the registry."""
    # Unified tools
    registry.register(FilesystemTool())
    registry.register(TerminalTool())
    registry.register(GitTool())
    registry.register(BrowserAutomationTool())
    registry.register(OSActionsTool())

    # Individual action tools
    registry.register(FilesSearchTool())
    registry.register(FilesReadTool())
    registry.register(FilesWriteTool())
    registry.register(FilesMoveTool())
    registry.register(FilesDeleteTool())
    registry.register(NotesCreateTool())
    registry.register(NotesSearchTool())
    registry.register(RemindersCreateTool())
    registry.register(RemindersListTool())
    registry.register(AppsOpenTool())
    registry.register(ShellRunTool())


# Automatically register on module import
register_standard_tools(tool_registry)

# Also synchronize with app.agent.registry.tool_registry
try:
    from app.agent.registry import tool_registry as app_tool_registry

    for t in tool_registry.list_tools():
        app_tool_registry.register(t)
except Exception:
    pass

__all__ = [
    "BaseTool",
    "ExecutionContext",
    "RiskLevel",
    "ToolResult",
    "ToolRegistry",
    "tool_registry",
    "register_standard_tools",
    "FilesystemTool",
    "TerminalTool",
    "GitTool",
    "BrowserAutomationTool",
    "OSActionsTool",
    "FilesSearchTool",
    "FilesReadTool",
    "FilesWriteTool",
    "FilesMoveTool",
    "FilesDeleteTool",
    "NotesCreateTool",
    "NotesSearchTool",
    "RemindersCreateTool",
    "RemindersListTool",
    "AppsOpenTool",
    "ShellRunTool",
]
