"""Agent runtime state management."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from ..core.contracts import PermissionRequest

from ..core.actions import Action
from ..core.errors import AgentError
from ..core.plans import Plan
from ..core.results import ActionResult, VerificationResult
from ..pcb.state import PCBState
from ..schematic.state import SchematicState
from ..tasks.task import Task


@dataclass
class AgentState:
    """Runtime execution state of the KiCad AI Agent.
    
    Attributes:
        active_domain: Current active domain ('pcb' or 'schematic').
        current_task: High-level engineering task currently being executed.
        current_goal: Specific active goal or milestone description.
        current_stage: Current stage name in multi-stage workflow.
        current_action: Action currently being validated or executed.
        current_plan: The active execution plan or stage plan.
        executed_actions: History of all actions executed.
        completed_actions: List of actions successfully executed and verified.
        failed_actions: List of actions that failed execution or verification.
        action_results: Results corresponding to executed actions.
        observations: History of ground-truth state observations generated after actions.
        verification_history: Log of all action and goal verification checks.
        tool_calls: History of tool decisions emitted by the LLM.
        errors: Log of structured errors encountered during session.
        repair_attempts: Count of repair attempts applied.
        final_status: Session lifecycle status ('pending', 'running', 'completed', 'failed', 'rolled_back').
        pcb_state: Latest observed PCB state.
        schematic_state: Latest observed schematic state.
        iteration_count: Number of loop iterations executed.
        max_iterations: Maximum allowed iterations before stopping.
    """
    active_domain: str = "pcb"
    current_task: Optional[Task] = None
    current_goal: Optional[str] = None
    current_stage: str = ""
    current_action: Optional[Action] = None
    current_plan: Optional[Plan] = None
    executed_actions: List[Action] = field(default_factory=list)
    completed_actions: List[Action] = field(default_factory=list)
    failed_actions: List[Action] = field(default_factory=list)
    action_results: List[ActionResult] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    verification_history: List[VerificationResult] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    pending_permission: Optional[PermissionRequest] = None
    repair_attempts: int = 0
    final_status: str = "pending"
    pcb_state: Optional[PCBState] = None
    schematic_state: Optional[SchematicState] = None
    iteration_count: int = 0
    max_iterations: int = 20

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dictionary."""
        return {
            "active_domain": self.active_domain,
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "current_goal": self.current_goal,
            "current_stage": self.current_stage,
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
            "executed_actions_count": len(self.executed_actions),
            "completed_actions_count": len(self.completed_actions),
            "failed_actions_count": len(self.failed_actions),
            "repair_attempts": self.repair_attempts,
            "final_status": self.final_status,
            "recent_observations": self.observations[-5:] if self.observations else [],
        }
