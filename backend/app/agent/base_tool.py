"""Base tool abstractions and interfaces for agent tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    """Safety risk levels for tools."""

    LOW = "low"  # Read-only, safe, runs automatically
    MEDIUM = "medium"  # Modifies state, opens apps, needs owner confirmation
    HIGH = "high"  # Deletions, shell execution, always needs explicit confirmation


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: Any
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "meta": self.meta,
        }


@dataclass
class ExecutionContext:
    """Context passed to tool execution."""

    session_id: str | None = None
    device_id: str | None = None
    is_approved: bool = False
    approved_by: str | None = None


class BaseTool(ABC):
    """Abstract base class for all agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique dot-separated tool name (e.g., 'files.read')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Clear description of the tool for the LLM."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema dictionary for tool parameters."""
        pass

    @property
    @abstractmethod
    def risk_level(self) -> RiskLevel:
        """Safety tier of this tool."""
        pass

    @abstractmethod
    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        """Asynchronously execute the tool logic."""
        pass

    def to_ollama_tool(self) -> dict[str, Any]:
        """Format tool definition for Ollama function calling API."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
