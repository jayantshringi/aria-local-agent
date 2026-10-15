"""Standardized Base Tool abstractions, risk levels, and execution context."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    """Safety and permission tiers for agent tools."""

    LOW = "low"  # Read-only or safe local operations (auto-approved by default)
    MEDIUM = "medium"  # Reversible writes or network queries (requires approval)
    HIGH = "high"  # Destructive writes, deletions, or shell executions (strict approval)


@dataclass
class ExecutionContext:
    """Runtime context passed into a tool execution."""

    session_id: str | None = None
    device_id: str | None = None
    is_approved: bool = False
    approved_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def meta(self) -> dict[str, Any]:
        return self.metadata


@dataclass
class ToolResult:
    """Standardized output returned by a tool execution."""

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def meta(self) -> dict[str, Any]:
        return self.metadata

    def to_dict(self) -> dict[str, Any]:
        """Convert result to serializable dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "meta": self.metadata,
        }


class BaseTool(ABC):
    """Abstract base class for all Aria and Antigravity standardized tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique dot-separated tool identifier (e.g. 'files.read')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Clear description of the tool for the model."""
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
        """Execute the tool logic asynchronously with safety context."""
        raise NotImplementedError

    def get_schema(self) -> dict[str, Any]:
        """Return standardized JSON schema representation of the tool."""
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "parameters": self.parameters,
        }

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
