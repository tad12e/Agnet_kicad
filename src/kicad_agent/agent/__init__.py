"""Agent orchestration, planning, execution, verification, and repair."""

from .agent import KiCadAgent
from .context import AgentContext, DesignConstraints, ModelContext
from .controller import AgentController
from .decisions import AgentDecision, DecisionType
from .error_analyzer import ErrorAnalyzer
from .executor import Executor
from .observability import AgentTrace, TraceEvent
from .planner import Planner
from .repair import RepairEngine, RepairOutcome
from .state import AgentState
from .tools import (
    ALL_TOOLS_SCHEMA,
    PCB_READ_TOOLS_SCHEMA,
    PCB_WRITE_TOOLS_SCHEMA,
    READ_TOOLS_SCHEMA,
    SCHEMATIC_READ_TOOLS_SCHEMA,
    SCHEMATIC_WRITE_TOOLS_SCHEMA,
    WRITE_TOOLS_SCHEMA,
    ToolRegistry,
    tool_call_to_action,
)
from .verifier import AgentVerifier
from .mode_policy import action_allowed, normalize_mode

__all__ = [
    "ALL_TOOLS_SCHEMA",
    "AgentContext",
    "AgentController",
    "AgentDecision",
    "AgentState",
    "AgentTrace",
    "AgentVerifier",
    "DecisionType",
    "DesignConstraints",
    "ModelContext",
    "ErrorAnalyzer",
    "Executor",
    "KiCadAgent",
    "PCB_READ_TOOLS_SCHEMA",
    "PCB_WRITE_TOOLS_SCHEMA",
    "Planner",
    "READ_TOOLS_SCHEMA",
    "RepairEngine",
    "RepairOutcome",
    "SCHEMATIC_READ_TOOLS_SCHEMA",
    "SCHEMATIC_WRITE_TOOLS_SCHEMA",
    "ToolRegistry",
    "TraceEvent",
    "WRITE_TOOLS_SCHEMA",
    "tool_call_to_action",
    "action_allowed",
    "normalize_mode",
]
