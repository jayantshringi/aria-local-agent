"""Sandboxed Filesystem tool suite for Aria and Antigravity."""

from typing import Any

from app.agent.safety import SecurityViolationError, verify_path_allowed
from app.config import get_settings
from app.tools.files import (
    FilesDeleteTool,
    FilesMoveTool,
    FilesReadTool,
    FilesSearchTool,
    FilesWriteTool,
)
from tools.base import BaseTool, ExecutionContext, RiskLevel, ToolResult


class FilesystemTool(BaseTool):
    """Unified sandboxed filesystem manager for reading, writing, searching, moving, and soft-deleting files."""

    name = "filesystem"
    description = (
        "Perform safe filesystem operations within whitelisted directories. "
        "Supported actions: 'read', 'write', 'search', 'list', 'move', 'delete', 'info'."
    )
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "search", "list", "move", "delete", "info"],
                "description": "Filesystem operation to perform",
            },
            "path": {
                "type": "string",
                "description": "Target file or directory path relative to whitelisted folder",
            },
            "content": {
                "type": "string",
                "description": "Content to write (when action is 'write')",
            },
            "destination": {
                "type": "string",
                "description": "Destination path (when action is 'move')",
            },
            "pattern": {
                "type": "string",
                "description": "Search glob pattern (when action is 'search' or 'list')",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._read_tool = FilesReadTool()
        self._write_tool = FilesWriteTool()
        self._search_tool = FilesSearchTool()
        self._move_tool = FilesMoveTool()
        self._delete_tool = FilesDeleteTool()

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        action = args.get("action", "").lower().strip()
        path_str = args.get("path", "").strip()

        if action == "read":
            return await self._read_tool.execute({"path": path_str}, context)
        elif action == "write":
            content = args.get("content", "")
            return await self._write_tool.execute({"path": path_str, "content": content}, context)
        elif action == "search":
            pattern = args.get("pattern") or path_str or "*"
            return await self._search_tool.execute({"pattern": pattern}, context)
        elif action == "move":
            destination = args.get("destination") or args.get("dest_path", "")
            source = path_str or args.get("source", "")
            return await self._move_tool.execute(
                {
                    "source": source,
                    "destination": destination,
                    "source_path": source,
                    "dest_path": destination,
                },
                context,
            )

        elif action == "delete":
            return await self._delete_tool.execute({"path": path_str}, context)
        elif action == "list":
            return await self._list_dir(path_str, args.get("pattern", "*"))
        elif action == "info":
            return await self._file_info(path_str)
        else:
            return ToolResult(
                success=False,
                error=f"Unsupported filesystem action: '{action}'. Choose from: read, write, search, list, move, delete, info",
            )

    async def _list_dir(self, subpath: str, pattern: str) -> ToolResult:
        settings = get_settings()
        roots = settings.whitelisted_directories
        try:
            entries = []
            for root in roots:
                target_dir = root
                if subpath:
                    target_dir = verify_path_allowed(root / subpath, roots)
                if target_dir.exists() and target_dir.is_dir():
                    for item in sorted(target_dir.glob(pattern)):
                        kind = "dir" if item.is_dir() else "file"
                        size = item.stat().st_size if item.is_file() else 0
                        entries.append(f"[{kind}] {item.name} ({size} bytes)")
            return ToolResult(
                success=True,
                output="\n".join(entries) if entries else "Directory is empty.",
                metadata={"count": len(entries)},
            )
        except SecurityViolationError as err:
            return ToolResult(success=False, error=str(err))
        except Exception as exc:
            return ToolResult(success=False, error=f"List failed: {exc}")

    async def _file_info(self, subpath: str) -> ToolResult:
        settings = get_settings()
        roots = settings.whitelisted_directories
        try:
            for root in roots:
                candidate = root / subpath
                if candidate.exists():
                    target = verify_path_allowed(candidate, roots)
                    stat = target.stat()
                    info = {
                        "path": str(target),
                        "name": target.name,
                        "is_file": target.is_file(),
                        "is_dir": target.is_dir(),
                        "size_bytes": stat.st_size,
                        "created_at": stat.st_ctime,
                        "modified_at": stat.st_mtime,
                    }
                    return ToolResult(success=True, output=info, metadata=info)
            return ToolResult(success=False, error=f"File not found: {subpath}")
        except SecurityViolationError as err:
            return ToolResult(success=False, error=str(err))
        except Exception as exc:
            return ToolResult(success=False, error=f"Info failed: {exc}")


__all__ = [
    "FilesystemTool",
    "FilesSearchTool",
    "FilesReadTool",
    "FilesWriteTool",
    "FilesMoveTool",
    "FilesDeleteTool",
]
