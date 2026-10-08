"""Plan representation for ordering and dependency tracking of Actions."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .actions import Action
from .goals import Goal


@dataclass
class PlanStage:
    """A named, ordered stage in a multi-step execution plan."""

    name: str
    description: str = ""
    order: int = 0
    action_ids: List[str] = field(default_factory=list)
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "action_ids": self.action_ids,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStage":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            order=int(data.get("order", 0)),
            action_ids=list(data.get("action_ids", [])),
            completed=bool(data.get("completed", False)),
        )


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
    stages: List[PlanStage] = field(default_factory=list)
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
            "stages": [s.to_dict() for s in self.stages],
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        return cls(
            plan_id=data.get("plan_id", str(uuid.uuid4())),
            goals=[Goal.from_dict(item) for item in data.get("goals", [])],
            actions=[Action.from_dict(item) for item in data.get("actions", [])],
            stages=[PlanStage.from_dict(item) for item in data.get("stages", [])],
            dependencies={
                str(key): list(value)
                for key, value in data.get("dependencies", {}).items()
            },
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
        )
