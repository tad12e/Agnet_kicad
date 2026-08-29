"""Agent runtime state management."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.actions import Action
from ..core.plans import Plan
from ..core.results import ActionResult, VerificationResult
from ..pcb.state import PCBState
from ..schematic.state import SchematicState


@dataclass
class AgentState:
    """Runtime execution state of the KiCad AI Agent.
    
    Attributes:
        active_domain: Current active domain ('pcb' or 'schematic').
        current_plan: The active execution plan.
        executed_actions: History of executed actions.
        action_results: Results corresponding to executed actions.
        verification_history: Log of all verification checks.
        pcb_state: Latest observed PCB state.
        schematic_state: Latest observed schematic state.
        iteration_count: Number of plan/execute/repair loops executed.
        max_iterations: Maximum allowed retries before stopping.
    """
    active_domain: str = "pcb"
    current_plan: Optional[Plan] = None
    executed_actions: List[Action] = field(default_factory=list)
    action_results: List[ActionResult] = field(default_factory=list)
    verification_history: List[VerificationResult] = field(default_factory=list)
    pcb_state: Optional[PCBState] = None
    schematic_state: Optional[SchematicState] = None
    iteration_count: int = 0
    max_iterations: int = 5
