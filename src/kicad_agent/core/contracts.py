"""Shared contracts between an LLM client, the agent runtime, and KiCad.

These dataclasses define the JSON boundary used by MCP and future adapters.
They intentionally describe runtime state and decisions without performing
backend work or embedding provider-specific behavior.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .actions import Action
from .plans import Plan
from .results import ActionResult, VerificationResult
from .tool_contracts import ToolRequest, ToolResponse
from ..tasks.task import Task


class AgentMode(str, enum.Enum):
    """Runtime capability mode for an agent session."""

    PLAN = "plan"
    BUILD = "build"
    VERIFY = "verify"
    REPAIR = "repair"


class SessionStatus(str, enum.Enum):
    """Lifecycle status for a resumable agent session."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PermissionDecision(str, enum.Enum):
    """Decision returned by the runtime permission boundary."""

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class MessageRole(str, enum.Enum):
    """Conversation participant that produced a session message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MessageType(str, enum.Enum):
    """Normalized message kinds persisted in an agent session."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


@dataclass
class SessionMessage:
    """Provider-neutral conversation message stored in an agent session."""

    role: MessageRole
    message_type: MessageType
    content: str = ""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(self.__dict__)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMessage":
        message_type = MessageType(data["message_type"])
        if message_type is MessageType.USER:
            return UserMessage.from_dict(data)
        if message_type is MessageType.SYSTEM:
            return SystemMessage.from_dict(data)
        if message_type is MessageType.ASSISTANT:
            return AssistantMessage.from_dict(data)
        if message_type is MessageType.TOOL_CALL:
            return ToolCallMessage.from_dict(data)
        if message_type is MessageType.TOOL_RESULT:
            return ToolResultMessage.from_dict(data)
        raise ValueError(f"Unsupported session message type: {message_type}")


@dataclass
class UserMessage(SessionMessage):
    """User request or follow-up supplied to the agent."""

    role: MessageRole = field(default=MessageRole.USER, init=False)
    message_type: MessageType = field(default=MessageType.USER, init=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserMessage":
        return cls(
            content=str(data.get("content", "")),
            message_id=str(data.get("message_id", str(uuid.uuid4()))),
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class SystemMessage(SessionMessage):
    """Runtime instruction or system context supplied to the model."""

    role: MessageRole = field(default=MessageRole.SYSTEM, init=False)
    message_type: MessageType = field(default=MessageType.SYSTEM, init=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemMessage":
        return cls(
            content=str(data.get("content", "")),
            message_id=str(data.get("message_id", str(uuid.uuid4()))),
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class AssistantMessage(SessionMessage):
    """Assistant text response, before or alongside tool calls."""

    role: MessageRole = field(default=MessageRole.ASSISTANT, init=False)
    message_type: MessageType = field(default=MessageType.ASSISTANT, init=False)
    tool_calls: List[ToolRequest] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssistantMessage":
        return cls(
            content=str(data.get("content", "")),
            tool_calls=[
                ToolRequest(
                    tool_name=str(item["tool_name"]),
                    arguments=dict(item.get("arguments", {})),
                    request_id=str(item.get("request_id", str(uuid.uuid4()))),
                    created_at=float(item.get("created_at", time.time())),
                )
                for item in data.get("tool_calls", [])
            ],
            message_id=str(data.get("message_id", str(uuid.uuid4()))),
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "tool_calls": [call.to_dict() for call in self.tool_calls],
        }


@dataclass
class ToolCallMessage(SessionMessage):
    """Normalized assistant request to execute one tool."""

    role: MessageRole = field(default=MessageRole.ASSISTANT, init=False)
    message_type: MessageType = field(default=MessageType.TOOL_CALL, init=False)
    request: ToolRequest = field(
        default_factory=lambda: ToolRequest(tool_name="")
    )

    def __post_init__(self) -> None:
        if not self.content:
            self.content = f"Call tool '{self.request.tool_name}'."

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCallMessage":
        return cls(
            request=ToolRequest(
                tool_name=str(data["request"]["tool_name"]),
                arguments=dict(data["request"].get("arguments", {})),
                request_id=str(data["request"].get("request_id", str(uuid.uuid4()))),
                created_at=float(data["request"].get("created_at", time.time())),
            ),
            content=str(data.get("content", "")),
            message_id=str(data.get("message_id", str(uuid.uuid4()))),
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {**super().to_dict(), "request": self.request.to_dict()}


@dataclass
class ToolResultMessage(SessionMessage):
    """Structured result returned after a tool call."""

    role: MessageRole = field(default=MessageRole.TOOL, init=False)
    message_type: MessageType = field(default=MessageType.TOOL_RESULT, init=False)
    response: ToolResponse = field(
        default_factory=lambda: ToolResponse(tool_name="", success=False)
    )

    def __post_init__(self) -> None:
        if not self.content:
            self.content = (
                f"Tool '{self.response.tool_name}' "
                f"{'succeeded' if self.response.success else 'failed'}."
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolResultMessage":
        response_data = data["response"]
        error_data = response_data.get("error")
        from .tool_contracts import ToolError

        error = (
            ToolError(
                code=str(error_data["code"]),
                message=str(error_data["message"]),
                recoverable=bool(error_data.get("recoverable", True)),
                suggested_inspection=error_data.get("suggested_inspection"),
                details=dict(error_data.get("details", {})),
            )
            if error_data
            else None
        )
        response = ToolResponse(
            tool_name=str(response_data["tool_name"]),
            success=bool(response_data.get("success", False)),
            data=dict(response_data.get("data", {})),
            error=error,
            action_id=response_data.get("action_id"),
            backend=response_data.get("backend"),
            verified=bool(response_data.get("verified", False)),
            request_id=response_data.get("request_id"),
            created_at=float(response_data.get("created_at", time.time())),
        )
        return cls(
            response=response,
            content=str(data.get("content", "")),
            message_id=str(data.get("message_id", str(uuid.uuid4()))),
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {**super().to_dict(), "response": self.response.to_dict()}


def _serialize(value: Any) -> Any:
    """Serialize nested contract values while preserving JSON primitives."""
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


@dataclass
class Observation:
    """Ground-truth state or event reported after an action."""

    kind: str
    message: str
    state: Dict[str, Any] = field(default_factory=dict)
    action_id: Optional[str] = None
    backend: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(self.__dict__)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Observation":
        return cls(
            kind=data["kind"],
            message=data["message"],
            state=dict(data.get("state", {})),
            action_id=data.get("action_id"),
            backend=data.get("backend"),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class RepairAttempt:
    """Record of one deterministic or model-guided recovery attempt."""

    action_id: str
    attempt: int
    reason: str
    replacement_action: Optional[Action] = None
    result: Optional[ActionResult] = None
    verification: Optional[VerificationResult] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(self.__dict__)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RepairAttempt":
        return cls(
            action_id=data["action_id"],
            attempt=int(data.get("attempt", 0)),
            reason=data.get("reason", ""),
            replacement_action=(
                Action.from_dict(data["replacement_action"])
                if data.get("replacement_action") else None
            ),
            result=(
                ActionResult.from_dict(data["result"])
                if data.get("result") else None
            ),
            verification=(
                VerificationResult.from_dict(data["verification"])
                if data.get("verification") else None
            ),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class PermissionRequest:
    """Approval request emitted before a policy-sensitive operation."""

    action: Action
    reason: str
    risk: str = "medium"
    decision: PermissionDecision = PermissionDecision.ASK
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(self.__dict__)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PermissionRequest":
        return cls(
            request_id=data.get("request_id", str(uuid.uuid4())),
            action=Action.from_dict(data["action"]),
            reason=data.get("reason", ""),
            risk=data.get("risk", "medium"),
            decision=PermissionDecision(data.get("decision", PermissionDecision.ASK.value)),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class AgentSession:
    """Serializable session envelope shared with an MCP client."""

    SCHEMA_VERSION = 1
    task: Optional[Task] = None
    mode: AgentMode = AgentMode.BUILD
    status: SessionStatus = SessionStatus.PENDING
    plan: Optional[Plan] = None
    messages: List[SessionMessage] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    results: List[ActionResult] = field(default_factory=list)
    verifications: List[VerificationResult] = field(default_factory=list)
    repairs: List[RepairAttempt] = field(default_factory=list)
    pending_permission: Optional[PermissionRequest] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def append_message(self, message: SessionMessage) -> SessionMessage:
        """Append one conversation event and update session activity time."""
        self.messages.append(message)
        self.updated_at = time.time()
        return message

    @property
    def last_message(self) -> Optional[SessionMessage]:
        """Return the newest conversation event, if one exists."""
        return self.messages[-1] if self.messages else None

    def to_dict(self) -> Dict[str, Any]:
        return {"schema_version": self.SCHEMA_VERSION, **_serialize(self.__dict__)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSession":
        version = data.get("schema_version", cls.SCHEMA_VERSION)
        if version != cls.SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported agent session schema version: {version}"
            )
        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            task=Task.from_dict(data["task"]) if data.get("task") else None,
            mode=AgentMode(data.get("mode", AgentMode.BUILD.value)),
            status=SessionStatus(data.get("status", SessionStatus.PENDING.value)),
            plan=Plan.from_dict(data["plan"]) if data.get("plan") else None,
            messages=[
                SessionMessage.from_dict(item)
                for item in data.get("messages", [])
            ],
            observations=[
                Observation.from_dict(item) for item in data.get("observations", [])
            ],
            actions=[Action.from_dict(item) for item in data.get("actions", [])],
            results=[
                ActionResult.from_dict(item) for item in data.get("results", [])
            ],
            verifications=[
                VerificationResult.from_dict(item)
                for item in data.get("verifications", [])
            ],
            repairs=[
                RepairAttempt.from_dict(item) for item in data.get("repairs", [])
            ],
            pending_permission=(
                PermissionRequest.from_dict(data["pending_permission"])
                if data.get("pending_permission") else None
            ),
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
        )
