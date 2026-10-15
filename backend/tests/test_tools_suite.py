"""Unit and integration tests for standardized Antigravity tool suite."""

import sys
from pathlib import Path

import pytest

from app.config import get_settings
from tools.base import ExecutionContext, RiskLevel
from tools.browser import BrowserAutomationTool
from tools.filesystem import FilesystemTool
from tools.git_tool import GitTool
from tools.os_actions import OSActionsTool
from tools.registry import ToolRegistry
from tools.terminal import TerminalTool


@pytest.fixture
def test_context() -> ExecutionContext:
    return ExecutionContext(session_id="test-session", is_approved=True)


@pytest.mark.asyncio
async def test_tool_registry():
    registry = ToolRegistry()
    assert len(registry.list_tools()) == 0

    fs_tool = FilesystemTool()
    registry.register(fs_tool)

    assert registry.get("filesystem") is fs_tool
    assert "filesystem" in registry.list_names()
    assert len(registry.get_schemas()) == 1
    assert registry.get_schemas()[0]["name"] == "filesystem"
    assert registry.get_schemas()[0]["risk_level"] == RiskLevel.MEDIUM.value

    # Filter by risk
    assert len(registry.get_tools_by_risk(RiskLevel.MEDIUM)) == 1
    assert len(registry.get_tools_by_risk(RiskLevel.HIGH)) == 0

    assert registry.unregister("filesystem") is True
    assert registry.get("filesystem") is None


@pytest.mark.asyncio
async def test_filesystem_tool_lifecycle(tmp_path: Path, monkeypatch):
    # Configure whitelist to point to tmp_path
    monkeypatch.setattr(get_settings(), "folder_whitelist", str(tmp_path))

    fs_tool = FilesystemTool()
    ctx = ExecutionContext(is_approved=True)

    # 1. Write file
    write_res = await fs_tool.execute(
        {"action": "write", "path": "notes.txt", "content": "Hello Aria OS"}, ctx
    )
    assert write_res.success is True

    # 2. Read file
    read_res = await fs_tool.execute({"action": "read", "path": "notes.txt"}, ctx)
    assert read_res.success is True
    assert "Hello Aria OS" in read_res.output

    # 3. File info
    info_res = await fs_tool.execute({"action": "info", "path": "notes.txt"}, ctx)
    assert info_res.success is True
    assert info_res.metadata["is_file"] is True

    # 4. List directory
    list_res = await fs_tool.execute({"action": "list", "path": ""}, ctx)
    assert list_res.success is True
    assert "notes.txt" in list_res.output

    # 5. Move file
    move_res = await fs_tool.execute(
        {"action": "move", "path": "notes.txt", "destination": "renamed.txt"}, ctx
    )
    assert move_res.success is True

    # 6. Delete file (soft-delete to .trash)
    del_res = await fs_tool.execute({"action": "delete", "path": "renamed.txt"}, ctx)
    assert del_res.success is True

    # 7. Path traversal security check
    traversal_res = await fs_tool.execute(
        {"action": "read", "path": "../../windows/system32/cmd.exe"}, ctx
    )
    assert traversal_res.success is False
    assert "Access denied" in traversal_res.error


@pytest.mark.asyncio
async def test_terminal_tool(test_context: ExecutionContext):
    term = TerminalTool()

    # Allowed command: current python executable
    res = await term.execute(
        {"command": f'"{sys.executable}" --version'},
        test_context,
    )
    assert res.success is True
    assert "Python" in res.output

    # Blocked unallowed command
    blocked_res = await term.execute(
        {"command": "malicious_hack_tool --destroy"},
        test_context,
    )
    assert blocked_res.success is False
    assert "not in the allowed terminal commands" in blocked_res.error


@pytest.mark.asyncio
async def test_git_tool(test_context: ExecutionContext):
    git_tool = GitTool()

    # Git status
    status_res = await git_tool.execute({"action": "status"}, test_context)
    assert status_res.success is True

    # Git branch
    branch_res = await git_tool.execute({"action": "branch"}, test_context)
    assert branch_res.success is True

    # Enforce security rule: git push is strictly forbidden
    push_res = await git_tool.execute({"action": "push"}, test_context)
    assert push_res.success is False
    assert "strictly prohibited" in push_res.error


@pytest.mark.asyncio
async def test_browser_tool_navigation(test_context: ExecutionContext):
    browser_tool = BrowserAutomationTool()

    # Test HTTP fallback navigation on local mock or public domain
    res = await browser_tool._execute_http_fallback("https://example.com", "navigate", 1000)
    assert res.success is True
    assert "<untrusted_tool_data" in res.output
    assert "</untrusted_tool_data>" in res.output
    assert "example.com" in res.metadata["url"]


@pytest.mark.asyncio
async def test_os_actions_tool(test_context: ExecutionContext):
    os_tool = OSActionsTool()

    # System info
    info_res = await os_tool.execute({"action": "system_info"}, test_context)
    assert info_res.success is True
    assert "CPU Usage" in info_res.output
    assert "RAM" in info_res.output
    assert "Disk" in info_res.output

    # List processes
    proc_res = await os_tool.execute({"action": "list_processes", "limit": 5}, test_context)
    assert proc_res.success is True
    assert len(proc_res.metadata["processes"]) <= 5
