"""Plan representation for ordering and dependency tracking of Actions."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .actions import Action
from .goals import Goal


@dataclass
class Plan:
    """Structured plan composed of goals and ordered actions.
    
    Attributes:
        plan_id: Unique plan UUID.
        goals: High-level goals this plan aims to satisfy.
        actions: Ordered sequence of actions to execute.
        dependencies: Action ID dependency mappings (action_id -> list of prerequisite action_ids).
        metadata: Additional planner context or explanation.
        created_at: Creation timestamp.
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goals: List[Goal] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def add_action(self, action: Action, depends_on: Optional[List[str]] = None) -> Action:
        """Add an action to the plan with optional dependencies."""
        self.actions.append(action)
        if depends_on:
            self.dependencies[action.action_id] = depends_on
        return action

    def to_dict(self) -> Dict[str, Any]:
        """Serialize plan to dictionary."""
        return {
            "plan_id": self.plan_id,
            "goals": [g.to_dict() for g in self.goals],
            "actions": [a.to_dict() for a in self.actions],
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }
