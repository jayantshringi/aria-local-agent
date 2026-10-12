"""Tests for dynamic tool plugin loader."""

from pathlib import Path

import pytest
from scripts.plugins.sample_echo_plugin import EchoPluginTool

from app.agent.plugins import load_plugins_from_directory
from app.agent.registry import tool_registry


def test_sample_plugin_execution():
    """Verify sample plugin tool behaves as expected."""
    tool = EchoPluginTool()
    assert tool.name == "plugin.echo"
    assert tool.risk_level.value == "low"


@pytest.mark.asyncio
async def test_dynamic_plugin_loader(tmp_path: Path):
    """Test loading plugins dynamically from a custom directory."""
    plugins_dir = tmp_path / "custom_plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write a custom plugin file
    plugin_code = """
from app.agent.base_tool import BaseTool, RiskLevel, ToolResult, ExecutionContext
from typing import Any

class DynamicMathPlugin(BaseTool):
    @property
    def name(self) -> str:
        return "plugin.custom_add"

    @property
    def description(self) -> str:
        return "Adds two numbers"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}}

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        res = args.get("a", 0) + args.get("b", 0)
        return ToolResult(success=True, output=res)
"""
    (plugins_dir / "math_plugin.py").write_text(plugin_code, encoding="utf-8")

    # Write an invalid/private file to test resilience
    (plugins_dir / "_ignored.py").write_text("invalid syntax error!!!", encoding="utf-8")

    # 2. Load plugins
    loaded = load_plugins_from_directory(plugins_dir)
    assert "plugin.custom_add" in loaded

    # 3. Verify tool is in registry and can execute
    registered_tool = tool_registry.get("plugin.custom_add")
    assert registered_tool is not None
    assert registered_tool.name == "plugin.custom_add"

    from app.agent.base_tool import ExecutionContext

    result = await registered_tool.execute({"a": 15, "b": 27}, ExecutionContext())
    assert result.success is True
    assert result.output == 42
