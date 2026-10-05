"""Structured Context and session tracking for LLM reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..tasks.task import Task


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
    iteration_count: int = 0
    max_iterations: int = 20

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
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
        }
