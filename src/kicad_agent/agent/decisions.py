"""Structured Decision representation for LLM-driven KiCad Agent.

Defines the explicit decision protocol between LLM reasoning and the agent runtime.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.actions import Action


class DecisionType(str, enum.Enum):
    """Classification of an LLM agent decision."""
    TOOL_CALL = "TOOL_CALL"
    ASK_USER = "ASK_USER"
    PLAN_UPDATE = "PLAN_UPDATE"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"


@dataclass
class AgentDecision:
    """Structured decision returned by the LLM reasoning engine.

    Attributes:
        decision_type: Type of decision (TOOL_CALL, ASK_USER, COMPLETE, FAIL, PLAN_UPDATE).
        tool_name: Name of tool to execute (if decision_type == TOOL_CALL).
        arguments: Parameters payload for tool call.
        action: Resolved Action IR (populated by agent runtime).
        reasoning_summary: Concise rationale explaining why this step was chosen.
        goal_status: High-level status of the engineering goal ('in_progress', 'completed', 'failed', 'blocked').
        confidence: Optional confidence metric (0.0 to 1.0).
        user_question: Question to present to the user if decision_type == ASK_USER.
        stage_updates: Updated list of stages/milestones if decision_type == PLAN_UPDATE.
        timestamp: Unix epoch timestamp when decision was generated.
    """
    decision_type: DecisionType = DecisionType.TOOL_CALL
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    action: Optional[Action] = None
    reasoning_summary: str = ""
    goal_status: str = "in_progress"
    confidence: float = 1.0
    user_question: Optional[str] = None
    stage_updates: Optional[List[str]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize decision to dictionary."""
        return {
            "decision_type": self.decision_type.value,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "action": self.action.to_dict() if self.action else None,
            "reasoning_summary": self.reasoning_summary,
            "goal_status": self.goal_status,
            "confidence": self.confidence,
            "user_question": self.user_question,
            "stage_updates": self.stage_updates,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentDecision:
        """Construct AgentDecision from dictionary representation."""
        raw_type = data.get("decision_type", DecisionType.TOOL_CALL.value)
        try:
            dec_type = DecisionType(raw_type)
        except ValueError:
            dec_type = DecisionType.TOOL_CALL

        action_obj = None
        if "action" in data and isinstance(data["action"], dict):
            action_obj = Action.from_dict(data["action"])

        return cls(
            decision_type=dec_type,
            tool_name=data.get("tool_name"),
            arguments=data.get("arguments", {}),
            action=action_obj,
            reasoning_summary=data.get("reasoning_summary", ""),
            goal_status=data.get("goal_status", "in_progress"),
            confidence=float(data.get("confidence", 1.0)),
            user_question=data.get("user_question"),
            stage_updates=data.get("stage_updates"),
            timestamp=data.get("timestamp", time.time()),
        )
