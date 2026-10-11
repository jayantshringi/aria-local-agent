"""Filesystem tools strictly restricted to whitelisted directory paths."""

import os
import shutil
from pathlib import Path
from typing import Any

from app.agent.base_tool import BaseTool, ExecutionContext, RiskLevel, ToolResult
from app.agent.safety import SecurityViolationError, verify_path_allowed
from app.config import get_settings


class FilesSearchTool(BaseTool):
    """Search for files matching pattern in whitelisted folders."""

    @property
    def name(self) -> str:
        return "files.search"

    @property
    def description(self) -> str:
        return "Search for files by glob pattern or keyword inside whitelisted folders."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match (e.g., '*.md', '*budget*')",
                },
                "subfolder": {
                    "type": "string",
                    "description": "Optional relative subfolder path within whitelisted root",
                },
            },
            "required": ["pattern"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        settings = get_settings()
        roots = settings.whitelisted_directories
        pattern = args.get("pattern", "*").strip()
        subfolder = args.get("subfolder", "").strip()

        try:
            matched_files: list[str] = []
            for root in roots:
                search_dir = root
                if subfolder:
                    search_dir = verify_path_allowed(root / subfolder, roots)

                if search_dir.exists() and search_dir.is_dir():
                    for match in search_dir.rglob(pattern):
                        if match.is_file():
                            rel_path = match.relative_to(root)
                            matched_files.append(f"{root.name}/{rel_path}")

            if not matched_files:
                return ToolResult(
                    success=True,
                    output=f"No files found matching '{pattern}'.",
                    meta={"count": 0},
                )

            return ToolResult(
                success=True,
                output="\n".join(matched_files[:50]),
                meta={"count": len(matched_files)},
            )
        except SecurityViolationError as e:
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Search failed: {e}")


class FilesReadTool(BaseTool):
    """Read file content from whitelisted directory."""

    @property
    def name(self) -> str:
        return "files.read"

    @property
    def description(self) -> str:
        return "Read text/markdown contents of a file inside whitelisted folders."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to file"},
            },
            "required": ["path"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        settings = get_settings()
        roots = settings.whitelisted_directories
        raw_path = args.get("path", "").strip()

        if not raw_path:
            return ToolResult(success=False, output="", error="Path cannot be empty")

        try:
            target_path = Path(raw_path)
            if not target_path.is_absolute():
                target_path = roots[0] / target_path

            safe_path = verify_path_allowed(target_path, roots)
            if not safe_path.exists():
                return ToolResult(success=False, output="", error=f"File not found: {raw_path}")

            if safe_path.is_dir():
                return ToolResult(
                    success=False, output="", error=f"Path is a directory, not a file: {raw_path}"
                )

            # Read up to 50KB to prevent memory exhaustion
            content = safe_path.read_text(encoding="utf-8", errors="replace")
            if len(content) > 50_000:
                content = content[:50_000] + "\n... [Truncated at 50,000 characters]"

            return ToolResult(
                success=True,
                output=content,
                meta={"path": str(safe_path), "size": len(content)},
            )
        except SecurityViolationError as e:
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Read error: {e}")


class FilesWriteTool(BaseTool):
    """Write or append text content to a file inside whitelisted directory."""

    @property
    def name(self) -> str:
        return "files.write"

    @property
    def description(self) -> str:
        return "Create, overwrite, or append content to a file in a whitelisted folder. (Requires approval)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the destination file"},
                "content": {"type": "string", "description": "Text content to write"},
                "mode": {
                    "type": "string",
                    "enum": ["overwrite", "append"],
                    "description": "Write mode ('overwrite' or 'append', default 'overwrite')",
                },
            },
            "required": ["path", "content"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        settings = get_settings()
        roots = settings.whitelisted_directories
        raw_path = args.get("path", "").strip()
        content = args.get("content", "")
        mode = args.get("mode", "overwrite")

        if not raw_path:
            return ToolResult(success=False, output="", error="Path cannot be empty")

        try:
            target_path = Path(raw_path)
            if not target_path.is_absolute():
                target_path = roots[0] / target_path

            safe_path = verify_path_allowed(target_path, roots)
            safe_path.parent.mkdir(parents=True, exist_ok=True)

            file_mode = "a" if mode == "append" else "w"
            with safe_path.open(file_mode, encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to '{safe_path.name}'.",
                meta={"path": str(safe_path), "mode": mode},
            )
        except SecurityViolationError as e:
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Write error: {e}")


class FilesMoveTool(BaseTool):
    """Move or rename a file within whitelisted folders."""

    @property
    def name(self) -> str:
        return "files.move"

    @property
    def description(self) -> str:
        return "Move or rename a file inside whitelisted folders. (Requires approval)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source file path"},
                "destination": {"type": "string", "description": "Destination file path"},
            },
            "required": ["source", "destination"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        settings = get_settings()
        roots = settings.whitelisted_directories
        src_raw = args.get("source", "").strip()
        dst_raw = args.get("destination", "").strip()

        try:
            src = Path(src_raw) if Path(src_raw).is_absolute() else roots[0] / src_raw
            dst = Path(dst_raw) if Path(dst_raw).is_absolute() else roots[0] / dst_raw

            safe_src = verify_path_allowed(src, roots)
            safe_dst = verify_path_allowed(dst, roots)

            if not safe_src.exists():
                return ToolResult(
                    success=False, output="", error=f"Source does not exist: {src_raw}"
                )

            safe_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(safe_src), str(safe_dst))

            return ToolResult(
                success=True,
                output=f"Successfully moved '{safe_src.name}' to '{safe_dst}'.",
                meta={"source": str(safe_src), "destination": str(safe_dst)},
            )
        except SecurityViolationError as e:
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Move error: {e}")


class FilesDeleteTool(BaseTool):
    """Safely move a file to trash bin (soft delete, never permanent unrecoverable deletion)."""

    @property
    def name(self) -> str:
        return "files.delete"

    @property
    def description(self) -> str:
        return "Safely move a file to the trash bin inside whitelisted folders. Never permanently deletes. (High Risk, Requires approval)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to move to trash"},
            },
            "required": ["path"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        settings = get_settings()
        roots = settings.whitelisted_directories
        raw_path = args.get("path", "").strip()

        try:
            target = Path(raw_path) if Path(raw_path).is_absolute() else roots[0] / raw_path
            safe_path = verify_path_allowed(target, roots)

            if not safe_path.exists():
                return ToolResult(success=False, output="", error=f"File not found: {raw_path}")

            # Reversible soft-deletion: move to a .trash folder in the root
            trash_dir = roots[0] / ".trash"
            trash_dir.mkdir(parents=True, exist_ok=True)

            trash_target = trash_dir / f"{safe_path.name}_{int(os.path.getmtime(str(safe_path)))}"
            shutil.move(str(safe_path), str(trash_target))

            return ToolResult(
                success=True,
                output=f"Safely moved '{safe_path.name}' to trash ({trash_target.name}). Reversible.",
                meta={"original_path": str(safe_path), "trash_path": str(trash_target)},
            )
        except SecurityViolationError as e:
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Delete error: {e}")
