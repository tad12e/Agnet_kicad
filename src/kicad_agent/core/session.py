"""Provider-neutral session and conversation contracts."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class MessageRole(str, enum.Enum):
    """Participant that produced a message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MessageType(str, enum.Enum):
    """Normalized event types persisted in a session."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


@dataclass
class SessionMessage:
    """A provider-independent conversation event."""

    role: MessageRole
    message_type: MessageType
    content: str = ""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the message for providers and persistence."""
        return {
            "message_id": self.message_id,
            "role": self.role.value,
            "message_type": self.message_type.value,
            "content": self.content,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "arguments": dict(self.arguments),
            "result": self.result,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMessage":
        """Restore a message and reject unknown enum values."""
        return cls(
            role=MessageRole(data["role"]),
            message_type=MessageType(data["message_type"]),
            content=str(data.get("content", "")),
            message_id=str(data.get("message_id", str(uuid.uuid4()))),
            tool_name=data.get("tool_name"),
            tool_call_id=data.get("tool_call_id"),
            arguments=dict(data.get("arguments", {})),
            result=data.get("result"),
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
        )

    @classmethod
    def user(cls, content: str, **metadata: Any) -> "SessionMessage":
        return cls(
            role=MessageRole.USER,
            message_type=MessageType.USER,
            content=content,
            metadata=metadata,
        )

    @classmethod
    def system(cls, content: str, **metadata: Any) -> "SessionMessage":
        return cls(
            role=MessageRole.SYSTEM,
            message_type=MessageType.SYSTEM,
            content=content,
            metadata=metadata,
        )

    @classmethod
    def assistant(
        cls,
        content: str = "",
        tool_name: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        tool_call_id: Optional[str] = None,
        **metadata: Any,
    ) -> "SessionMessage":
        message_type = (
            MessageType.TOOL_CALL if tool_name else MessageType.ASSISTANT
        )
        return cls(
            role=MessageRole.ASSISTANT,
            message_type=message_type,
            content=content,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=dict(arguments or {}),
            metadata=metadata,
        )

    @classmethod
    def tool_result(
        cls,
        tool_name: str,
        result: Dict[str, Any],
        tool_call_id: Optional[str] = None,
        content: str = "",
        **metadata: Any,
    ) -> "SessionMessage":
        return cls(
            role=MessageRole.TOOL,
            message_type=MessageType.TOOL_RESULT,
            content=content,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            result=dict(result),
            metadata=metadata,
        )


@dataclass
class AgentSession:
    """Durable state for one user request and its tool conversation."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_request: str = ""
    domain: str = "pcb"
    messages: List[SessionMessage] = field(default_factory=list)
    status: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def append(self, message: SessionMessage) -> SessionMessage:
        """Append an event while preserving chronological session state."""
        self.messages.append(message)
        self.updated_at = time.time()
        return message

    def recent_messages(self, limit: int = 20) -> List[SessionMessage]:
        """Return the most recent messages without mutating the session."""
        if limit < 1:
            return []
        return self.messages[-limit:]

    def pending_tool_calls(self) -> List[SessionMessage]:
        """Return tool calls that do not yet have a matching result."""
        completed = {
            message.tool_call_id
            for message in self.messages
            if message.message_type is MessageType.TOOL_RESULT
            and message.tool_call_id
        }
        return [
            message
            for message in self.messages
            if message.message_type is MessageType.TOOL_CALL
            and message.tool_call_id not in completed
        ]

    def compact(self, max_messages: int = 40) -> bool:
        """Bound history while retaining the request and pending tool pairs."""
        if max_messages < 4 or len(self.messages) <= max_messages:
            return False
        pending_ids = {
            message.tool_call_id
            for message in self.pending_tool_calls()
            if message.tool_call_id
        }
        keep = set(range(max(0, len(self.messages) - max_messages + 2), len(self.messages)))
        for index, message in enumerate(self.messages):
            if message.tool_call_id in pending_ids:
                keep.add(index)
        if self.messages:
            keep.add(0)
        removed = len(self.messages) - len(keep)
        summary = SessionMessage.system(
            f"Compacted {removed} older conversation events; recent tool evidence "
            "and pending tool calls were retained.",
            compacted_events=removed,
        )
        self.messages = [summary] + [
            message for index, message in enumerate(self.messages) if index in keep
        ]
        self.metadata["compacted_events"] = (
            int(self.metadata.get("compacted_events", 0)) + removed
        )
        self.updated_at = time.time()
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_request": self.user_request,
            "domain": self.domain,
            "messages": [message.to_dict() for message in self.messages],
            "status": self.status,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSession":
        return cls(
            session_id=str(data["session_id"]),
            user_request=str(data.get("user_request", "")),
            domain=str(data.get("domain", "pcb")),
            messages=[
                SessionMessage.from_dict(message)
                for message in data.get("messages", [])
            ],
            status=str(data.get("status", "pending")),
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
        )
