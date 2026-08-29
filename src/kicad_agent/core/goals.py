"""Goal and intent representation for circuit design requests."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class GoalType(str, enum.Enum):
    """Classification of user design goals."""
    PLACEMENT = "placement"
    RELATIVE_PLACEMENT = "relative_placement"
    ROUTING = "routing"
    CONNECTIVITY = "connectivity"
    DRC_CLEANUP = "drc_cleanup"
    SCHEMATIC_CREATION = "schematic_creation"
    INSPECTION = "inspection"
    CUSTOM = "custom"


@dataclass
class Goal:
    """High-level structured goal derived from user intent.
    
    Attributes:
        goal_id: Unique goal UUID.
        goal_type: Category of goal.
        description: Natural language specification.
        targets: Target components, nets, or objects.
        criteria: Specific verifiable acceptance criteria.
        completed: Whether this goal has been verified as met.
    """
    goal_type: GoalType
    description: str = ""
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    targets: List[str] = field(default_factory=list)
    criteria: Dict[str, Any] = field(default_factory=dict)
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize goal to dictionary."""
        return {
            "goal_id": self.goal_id,
            "goal_type": self.goal_type.value,
            "description": self.description,
            "targets": self.targets,
            "criteria": self.criteria,
            "completed": self.completed,
        }
