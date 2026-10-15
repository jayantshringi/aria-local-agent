"""Sandboxed Git version control tool for Aria and Antigravity."""

import asyncio
from pathlib import Path
from typing import Any

from tools.base import BaseTool, ExecutionContext, RiskLevel, ToolResult


class GitTool(BaseTool):
    """Executes safe local Git commands inside the repository. Never performs git push."""

    name = "git.action"
    description = (
        "Inspect and manage local git repository state. "
        "Allowed actions: 'status', 'diff', 'log', 'branch', 'add', 'commit'. "
        "Never pushes to remote or destroys uncommitted work."
    )
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "diff", "log", "branch", "add", "commit"],
                "description": "Git operation to perform",
            },
            "path": {
                "type": "string",
                "description": "File or path argument (for 'add' or 'diff')",
            },
            "message": {
                "type": "string",
                "description": "Commit message (required for 'commit')",
            },
            "max_count": {
                "type": "integer",
                "description": "Maximum number of commit logs to return (default 10)",
            },
        },
        "required": ["action"],
    }

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent.parent

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        action = args.get("action", "").lower().strip()

        # Enforce AGENTS.md rule: Never push to remote without explicit owner permission
        if action in ("push", "remote"):
            return ToolResult(
                success=False,
                error="Git push / remote modification is strictly prohibited by security rules.",
            )

        cmd_map: dict[str, list[str]] = {
            "status": ["git", "status", "--short", "--branch"],
            "branch": ["git", "branch", "-v"],
        }

        if action == "status":
            cmd = cmd_map["status"]
        elif action == "branch":
            cmd = cmd_map["branch"]
        elif action == "diff":
            target_file = args.get("path")
            cmd = ["git", "diff"]
            if target_file:
                cmd.append(str(target_file))
        elif action == "log":
            count = min(int(args.get("max_count") or 10), 50)
            cmd = ["git", "log", f"-n{count}", "--oneline", "--decorate"]
        elif action == "add":
            target_path = args.get("path", ".").strip()
            cmd = ["git", "add", target_path]
        elif action == "commit":
            message = args.get("message", "").strip()
            if not message:
                return ToolResult(
                    success=False, error="Commit message is required for action 'commit'."
                )
            cmd = ["git", "commit", "-m", message]
        else:
            return ToolResult(
                success=False,
                error=f"Unsupported git action '{action}'. Permitted: status, diff, log, branch, add, commit",
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                cmd[0],
                *cmd[1:],
                cwd=str(self.repo_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
            out_str = stdout.decode("utf-8", errors="replace").strip()
            err_str = stderr.decode("utf-8", errors="replace").strip()

            combined = out_str
            if err_str:
                combined = f"{out_str}\n{err_str}".strip()

            success = proc.returncode == 0
            return ToolResult(
                success=success,
                output=combined or f"Git {action} completed successfully.",
                error=None if success else f"Git exited with code {proc.returncode}: {err_str}",
                metadata={"action": action, "returncode": proc.returncode},
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"Git command failed: {exc}")


__all__ = ["GitTool"]
