"""Modular tool definitions and implementations."""

from app.agent.registry import ToolRegistry, tool_registry
from app.tools.apps import AppsOpenTool
from app.tools.files import (
    FilesDeleteTool,
    FilesMoveTool,
    FilesReadTool,
    FilesSearchTool,
    FilesWriteTool,
)
from app.tools.notes import NotesCreateTool, NotesSearchTool
from app.tools.reminders import RemindersCreateTool, RemindersListTool
from app.tools.shell import ShellRunTool
from app.tools.web import WebSearchTool


def register_all_tools(registry: ToolRegistry = tool_registry) -> None:
    """Register all built-in agent tools into the specified registry."""
    registry.register(NotesCreateTool())
    registry.register(NotesSearchTool())
    registry.register(FilesSearchTool())
    registry.register(FilesReadTool())
    registry.register(FilesWriteTool())
    registry.register(FilesMoveTool())
    registry.register(FilesDeleteTool())
    registry.register(RemindersCreateTool())
    registry.register(RemindersListTool())
    registry.register(AppsOpenTool())
    registry.register(WebSearchTool())
    registry.register(ShellRunTool())


# Auto-register defaults on module import
register_all_tools(tool_registry)
