"""Sandboxed terminal execution tool for Aria and Antigravity."""

import asyncio
import os
import shlex
from pathlib import Path
from typing import Any

from app.agent.safety import SecurityViolationError, verify_path_allowed
from app.config import get_settings
from app.tools.shell import ShellRunTool
from tools.base import BaseTool, ExecutionContext, RiskLevel, ToolResult


class TerminalTool(BaseTool):
    """Executes allow-listed terminal commands within sandboxed project and whitelist directories."""

    name = "terminal.exec"
    description = (
        "Execute an allow-listed terminal command in a sandboxed directory. "
        "Strictly validated against permitted commands (python, git, pytest, npm, node, etc.). "
        "High risk; requires owner approval."
    )
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Full command line string or base command (e.g. 'git status' or 'python --version')",
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of command arguments if command is just executable name",
            },
            "cwd": {
                "type": "string",
                "description": "Optional working directory path (must be within repository or whitelisted folders)",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Execution timeout limit in seconds (default 30, max 120)",
            },
        },
        "required": ["command"],
    }

    # Safe built-in allowlist commands
    DEFAULT_ALLOWED_COMMANDS = {
        "git",
        "python",
        "py",
        "pytest",
        "ruff",
        "black",
        "npm",
        "npx",
        "node",
        "dir",
        "ls",
        "echo",
        "ollama",
    }

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        settings = get_settings()

        raw_cmd = args.get("command", "").strip()
        if not raw_cmd:
            return ToolResult(success=False, error="Command cannot be empty.")

        # Split command line safely into parts
        try:
            parts = shlex.split(raw_cmd, posix=False if os.name == "nt" else True)
        except Exception:
            parts = raw_cmd.split()

        extra_args = args.get("args") or []
        if extra_args:
            parts.extend([str(a) for a in extra_args])

        if not parts:
            return ToolResult(success=False, error="Parsed command is empty.")

        cleaned_first = parts[0].strip("\"'")
        base_cmd = Path(cleaned_first).name.lower()
        if base_cmd.endswith(".exe"):
            base_cmd = base_cmd[:-4]

        # Combine configured allowlist with safe defaults
        allowed = set(settings.allowed_shell_commands_list) | self.DEFAULT_ALLOWED_COMMANDS
        if base_cmd not in allowed:
            return ToolResult(
                success=False,
                error=f"Command '{base_cmd}' is not in the allowed terminal commands: {sorted(list(allowed))}",
            )

        # Validate working directory
        cwd_str = args.get("cwd")
        target_cwd = Path.cwd()
        if cwd_str:
            try:
                candidate = Path(cwd_str).resolve()
                repo_root = Path(__file__).resolve().parent.parent.parent
                whitelist = settings.whitelisted_directories + [repo_root]
                target_cwd = verify_path_allowed(candidate, whitelist)
            except SecurityViolationError as sec_err:
                return ToolResult(success=False, error=str(sec_err))

        timeout = min(max(float(args.get("timeout_seconds") or 30.0), 1.0), 120.0)

        cleaned_args = [
            p.strip("\"'") if p.startswith(('"', "'")) and p.endswith(('"', "'")) else p
            for p in parts[1:]
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                cleaned_first,
                *cleaned_args,
                cwd=str(target_cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            out_text = stdout.decode("utf-8", errors="replace").strip()
            err_text = stderr.decode("utf-8", errors="replace").strip()

            combined = out_text
            if err_text:
                combined = f"{out_text}\n[STDERR]: {err_text}".strip()

            success = proc.returncode == 0
            return ToolResult(
                success=success,
                output=combined or f"Process exited with return code {proc.returncode}.",
                error=None if success else f"Command exited with return code {proc.returncode}",
                metadata={
                    "command": raw_cmd,
                    "returncode": proc.returncode,
                    "cwd": str(target_cwd),
                },
            )
        except TimeoutError:
            return ToolResult(
                success=False,
                error=f"Command execution timed out after {timeout} seconds.",
                metadata={"command": raw_cmd},
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Failed to execute command '{parts[0]}': {exc}",
                metadata={"command": raw_cmd},
            )


__all__ = ["TerminalTool", "ShellRunTool"]
