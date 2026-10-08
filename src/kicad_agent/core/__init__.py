"""Domain-neutral Intermediate Representation (IR) and execution models."""

from .actions import Action, ActionDomain, ActionType
from .errors import AgentError, ErrorCategory, ErrorSeverity
from .goals import Goal, GoalType
from .plans import Plan, PlanStage
from .plan_validator import PlanValidator
from .results import ActionResult, VerificationResult
from .transactions import Transaction, TransactionState
from .tool_contracts import (
    ToolArgument,
    ToolDefinition,
    ToolError,
    ToolRequest,
    ToolResponse,
    ToolRisk,
)
from .permissions import (
    DESTRUCTIVE_ACTIONS,
    HIGH_RISK_ACTIONS,
    PermissionCheck,
    PermissionPolicy,
)
from .validator import ActionValidator
from .session_snapshot import SessionSnapshot, SessionSnapshotStore, SnapshotError
from .contracts import (
    AgentMode,
    AgentSession,
    AssistantMessage,
    MessageRole,
    MessageType,
    SessionMessage,
    SessionStatus,
    SystemMessage,
    ToolCallMessage,
    ToolResultMessage,
    UserMessage,
)

__all__ = [
    "Action",
    "ActionDomain",
    "ActionResult",
    "ActionType",
    "ActionValidator",
    "AgentError",
    "ErrorCategory",
    "ErrorSeverity",
    "Goal",
    "GoalType",
    "Plan",
    "PlanStage",
    "PlanValidator",
    "Transaction",
    "TransactionState",
    "ToolArgument",
    "ToolDefinition",
    "ToolError",
    "ToolRequest",
    "ToolResponse",
    "DESTRUCTIVE_ACTIONS",
    "HIGH_RISK_ACTIONS",
    "PermissionCheck",
    "PermissionPolicy",
    "ToolRisk",
    "VerificationResult",
    "SessionSnapshot",
    "SessionSnapshotStore",
    "SnapshotError",
    "AgentMode",
    "AgentSession",
    "AssistantMessage",
    "MessageRole",
    "MessageType",
    "SessionMessage",
    "SessionStatus",
    "SystemMessage",
    "ToolCallMessage",
    "ToolResultMessage",
    "UserMessage",
]
