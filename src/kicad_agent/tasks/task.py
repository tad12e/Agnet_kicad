"""High-level task and intent representation for KiCad operations."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class TaskType(str, enum.Enum):
    """High-level user intent categories."""

    BUILD_CIRCUIT = "build_circuit"
    MODIFY_CIRCUIT = "modify_circuit"
    CREATE_SCHEMATIC = "create_schematic"
    CREATE_SCH = "create_schematic"
    ROUTE_BOARD = "route_board"
    FIX_DRC_ERRORS = "fix_drc_errors"
    VERIFY_DESIGN = "verify_design"
    CONVERT_SCHEMATIC_TO_PCB = "convert_schematic_to_pcb"
    CREATE_PCB = "create_pcb"
    CUSTOM = "custom"


@dataclass
class Task:
    """High-level task representing user intent before low-level action decomposition."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: TaskType = TaskType.CUSTOM
    domain: str = "schematic"
    description: str = ""
    requirements: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "domain": self.domain,
            "description": self.description,
            "requirements": self.requirements,
            "constraints": self.constraints,
            "expected_outcome": self.expected_outcome,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            task_type=TaskType(data.get("task_type", TaskType.CUSTOM.value)),
            domain=data.get("domain", "schematic"),
            description=data.get("description", ""),
            requirements=data.get("requirements", {}),
            constraints=data.get("constraints", {}),
            expected_outcome=data.get("expected_outcome"),
            metadata=data.get("metadata", {}),
        )
