"""Sandboxed shell execution tool (disabled by default, strict command allowlist only)."""

import asyncio
from typing import Any

from app.agent.base_tool import BaseTool, ExecutionContext, RiskLevel, ToolResult
from app.config import get_settings


class ShellRunTool(BaseTool):
    """Tool to execute allow-listed commands. Disabled by default, always high risk."""

    @property
    def name(self) -> str:
        return "shell.run"

    @property
    def description(self) -> str:
        return "Run an allow-listed command in the local environment. Disabled by default. (High Risk, Requires approval)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Base command to execute (must be in shell allowlist)",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of command line arguments",
                },
            },
            "required": ["command"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        settings = get_settings()
        if not settings.shell_enabled:
            return ToolResult(
                success=False,
                output="",
                error="Shell execution is disabled by default. Set ARIA_SHELL_ENABLED=true in settings.",
            )

        cmd = args.get("command", "").strip().lower()
        cmd_args = [str(a) for a in args.get("args", [])]

        allowed = settings.allowed_shell_commands_list
        if cmd not in allowed:
            allowed_str = ", ".join(allowed)
            return ToolResult(
                success=False,
                output="",
                error=f"Command '{cmd}' is not in the allowlist ({allowed_str}).",
            )

        try:
            # Execute subprocess safely without shell=True to avoid injection
            proc = await asyncio.create_subprocess_exec(
                cmd,
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

            out_text = stdout.decode("utf-8", errors="replace").strip()
            err_text = stderr.decode("utf-8", errors="replace").strip()

            combined = out_text
            if err_text:
                combined += f"\n[STDERR]: {err_text}"

            return ToolResult(
                success=proc.returncode == 0,
                output=combined or f"Command exited with return code {proc.returncode}.",
                error=(
                    None if proc.returncode == 0 else f"Process exited with code {proc.returncode}"
                ),
                meta={"returncode": proc.returncode},
            )
        except TimeoutError:
            return ToolResult(success=False, output="", error="Command timed out after 30 seconds.")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Shell execution failed: {e}")
