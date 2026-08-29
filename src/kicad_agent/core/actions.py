"""Domain-neutral Intermediate Representation (IR) for actions.

The LLM produces structured actions conforming to this specification,
which the executor layer deterministically translates into KiCad backend calls.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class ActionDomain(str, enum.Enum):
    """Target domain for an action."""
    PCB = "pcb"
    SCHEMATIC = "schematic"
    SYSTEM = "system"


class ActionType(str, enum.Enum):
    """Enumeration of domain actions."""
    # State inspection
    GET_STATE = "get_state"
    LOAD_DOCUMENT = "load_document"
    SAVE_DOCUMENT = "save_document"
    
    # PCB Footprint Operations
    ADD_FOOTPRINT = "add_footprint"
    MOVE_FOOTPRINT = "move_footprint"
    ROTATE_FOOTPRINT = "rotate_footprint"
    DELETE_FOOTPRINT = "delete_footprint"
    
    # PCB Routing Operations
    ADD_TRACK = "add_track"
    ROUTE_TRACK = "route_track"
    ADD_VIA = "add_via"
    ADD_ZONE = "add_zone"
    
    # Schematic Symbol Operations
    ADD_SYMBOL = "add_symbol"
    MOVE_SYMBOL = "move_symbol"
    ROTATE_SYMBOL = "rotate_symbol"
    DELETE_SYMBOL = "delete_symbol"
    
    # Schematic Wiring Operations
    ADD_WIRE = "add_wire"
    ADD_JUNCTION = "add_junction"
    ADD_LABEL = "add_label"
    ADD_BUS = "add_bus"
    ADD_POWER = "add_power"
    
    # Verification & DRC Operations
    RUN_DRC = "run_drc"
    RUN_SIMULATION = "run_simulation"
    VERIFY_CONNECTIVITY = "verify_connectivity"
    VERIFY_PLACEMENT = "verify_placement"


@dataclass
class Action:
    """Domain-neutral Intermediate Representation of a planned action.
    
    Attributes:
        action_type: Type of action to perform.
        parameters: Action-specific parameter payload.
        action_id: Unique action UUID.
        domain: Target domain (PCB, Schematic, System).
        description: Natural language summary of the action's intent.
        expected_outcome: Verifiable assertion about state after execution.
        timestamp: Unix epoch timestamp when action was created.
    """
    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    domain: ActionDomain = ActionDomain.PCB
    description: str = ""
    expected_outcome: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize action to dictionary."""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "domain": self.domain.value,
            "parameters": self.parameters,
            "description": self.description,
            "expected_outcome": self.expected_outcome,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Action:
        """Construct Action from dictionary."""
        return cls(
            action_id=data.get("action_id", str(uuid.uuid4())),
            action_type=ActionType(data["action_type"]),
            domain=ActionDomain(data.get("domain", ActionDomain.PCB.value)),
            parameters=data.get("parameters", {}),
            description=data.get("description", ""),
            expected_outcome=data.get("expected_outcome"),
            timestamp=data.get("timestamp", time.time()),
        )
