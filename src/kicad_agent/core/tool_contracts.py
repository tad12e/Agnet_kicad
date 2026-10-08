"""Provider-neutral contracts for MCP tool calls and results."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .actions import Action
from .errors import AgentError


class ToolRisk(str, enum.Enum):
    """Operational risk classification used by permission policies."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolArgument:
    """Description of one tool argument."""

    name: str
    value_type: str
    description: str = ""
    required: bool = False
    default: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.value_type,
            "description": self.description,
            "required": self.required,
            "default": self.default,
        }


@dataclass
class ToolDefinition:
    """Stable metadata for a tool exposed to an LLM or MCP client."""

    name: str
    description: str
    arguments: List[ToolArgument] = field(default_factory=list)
    risk: ToolRisk = ToolRisk.LOW
    mutating: bool = False
    recoverable: bool = True
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": [argument.to_dict() for argument in self.arguments],
            "risk": self.risk.value,
            "mutating": self.mutating,
            "recoverable": self.recoverable,
            "version": self.version,
        }


@dataclass
class ToolRequest:
    """Normalized request received from an external model client."""

    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "request_id": self.request_id,
            "created_at": self.created_at,
        }


@dataclass
class ToolError:
    """Structured, model-readable tool failure."""

    code: str
    message: str
    recoverable: bool = True
    suggested_inspection: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "suggested_inspection": self.suggested_inspection,
            "details": self.details,
        }

    @classmethod
    def from_agent_error(cls, error: AgentError) -> "ToolError":
        return cls(
            code=error.category.value,
            message=error.message,
            recoverable=error.recoverable,
            details=error.to_dict(),
        )


@dataclass
class ToolResponse:
    """Uniform success or failure envelope returned by a tool adapter."""

    tool_name: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[ToolError] = None
    action_id: Optional[str] = None
    backend: Optional[str] = None
    verified: bool = False
    request_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_action(
        cls,
        tool_name: str,
        action: Action,
        result: Any,
        verified: bool = False,
        request_id: Optional[str] = None,
    ) -> "ToolResponse":
        error = None
        if result.error:
            error = ToolError.from_agent_error(result.error)
        return cls(
            tool_name=tool_name,
            success=result.success,
            data=dict(result.data or {}),
            error=error,
            action_id=action.action_id,
            backend=result.backend_used or None,
            verified=verified,
            request_id=request_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "success" if self.success else "error",
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
            "action_id": self.action_id,
            "backend": self.backend,
            "verified": self.verified,
            "request_id": self.request_id,
            "created_at": self.created_at,
        }
