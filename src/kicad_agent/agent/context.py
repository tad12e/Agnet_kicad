"""Structured Context and session tracking for LLM reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..tasks.task import Task
from ..core.session import AgentSession, SessionMessage


@dataclass
class ModelContext:
    """Small provider-neutral snapshot for an external reasoning model.

    The runtime keeps richer history in :class:`AgentContext`; this contract
    deliberately contains only the information needed to choose the next
    decision.  Lists are bounded so the representation remains useful for
    smaller-context models.
    """

    task: Dict[str, Any] = field(default_factory=dict)
    plan: Dict[str, Any] = field(default_factory=dict)
    current_state: Dict[str, Any] = field(default_factory=dict)
    available_tools: List[str] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[Any] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 20

    def to_dict(self) -> Dict[str, Any]:
        """Return the stable JSON-compatible model context envelope."""
        return {
            "task": self.task,
            "plan": self.plan,
            "current_state": self.current_state,
            "available_tools": self.available_tools,
            "errors": self.errors,
            "observations": self.observations,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
        }


@dataclass
class DesignConstraints:
    """Constraints applied to the current design session."""
    min_trace_width_mm: float = 0.2
    min_clearance_mm: float = 0.2
    min_component_spacing_mm: float = 2.5
    default_grid_mm: float = 1.27
    board_width_mm: Optional[float] = None
    board_height_mm: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_trace_width_mm": self.min_trace_width_mm,
            "min_clearance_mm": self.min_clearance_mm,
            "min_component_spacing_mm": self.min_component_spacing_mm,
            "default_grid_mm": self.default_grid_mm,
            "board_width_mm": self.board_width_mm,
            "board_height_mm": self.board_height_mm,
        }


@dataclass
class AgentContext:
    """Context provided to LLM for informed, iterative engineering decisions."""
    task: Optional[Task] = None
    domain: str = "pcb"
    user_request: str = ""
    current_state_summary: Dict[str, Any] = field(default_factory=dict)
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)
    recent_observations: List[str] = field(default_factory=list)
    last_error: Optional[Dict[str, Any]] = None
    verification_history: List[Dict[str, Any]] = field(default_factory=list)
    constraints: DesignConstraints = field(default_factory=DesignConstraints)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)
    current_stage: str = ""
    plan_summary: Dict[str, Any] = field(default_factory=dict)
    iteration_count: int = 0
    max_iterations: int = 20
    session: AgentSession = field(default_factory=AgentSession)

    def append_message(self, message: SessionMessage) -> SessionMessage:
        self.session.append(message)
        self.conversation_history.append(message.to_dict())
        return message

    def to_model_context(self, limit: int = 5) -> ModelContext:
        """Build a bounded, provider-neutral context for model decision making."""
        task = self.task.to_dict() if self.task else {"description": self.user_request}
        stages = list(self.stages)
        plan = dict(self.plan_summary)
        plan.setdefault("stages", stages)
        plan.setdefault("current_stage", self.current_stage or "Execution")

        errors = [self.last_error] if self.last_error else []
        observations: List[Any] = list(self.recent_observations[-limit:])
        for action in self.recent_actions[-limit:]:
            if action not in observations:
                observations.append(action)

        return ModelContext(
            task=task,
            plan=plan,
            current_state=self.current_state_summary,
            available_tools=list(self.available_tools),
            errors=errors[-limit:],
            observations=observations[-limit:],
            iteration=self.iteration_count,
            max_iterations=self.max_iterations,
        )

    def compact_for_llm(self, limit: int = 5) -> Dict[str, Any]:
        """Return only the compact model-facing context representation."""
        return self.to_model_context(limit=limit).to_dict()

    def format_for_llm(self) -> Dict[str, Any]:
        """Compile a concise, structured dictionary of essential context for the LLM."""
        return {
            "task": self.task.to_dict() if self.task else {"description": self.user_request},
            "domain": self.domain,
            "current_stage": self.current_stage or "Execution",
            "stages": self.stages,
            "current_state": self.current_state_summary,
            "recent_actions": self.recent_actions[-5:] if self.recent_actions else [],
            "recent_observations": self.recent_observations[-5:] if self.recent_observations else [],
            "last_error": self.last_error,
            "constraints": self.constraints.to_dict(),
            "iteration": self.iteration_count,
            "max_iterations": self.max_iterations,
            "available_tools": self.available_tools,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dictionary."""
        return {
            "task": self.task.to_dict() if self.task else None,
            "domain": self.domain,
            "user_request": self.user_request,
            "current_state_summary": self.current_state_summary,
            "recent_actions": self.recent_actions,
            "recent_observations": self.recent_observations,
            "last_error": self.last_error,
            "verification_history": self.verification_history,
            "constraints": self.constraints.to_dict(),
            "user_preferences": self.user_preferences,
            "conversation_history": self.conversation_history,
            "available_tools": self.available_tools,
            "stages": self.stages,
            "current_stage": self.current_stage,
            "plan_summary": self.plan_summary,
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
        }
