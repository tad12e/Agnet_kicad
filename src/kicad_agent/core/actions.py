"""Domain-neutral Intermediate Representation (IR) for actions.

The LLM produces structured actions conforming to this specification,
which the validator checks against preconditions before the executor layer
deterministically translates them into KiCad backend calls.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ActionDomain(str, enum.Enum):
    """Target domain for an action."""
    PCB = "pcb"
    SCHEMATIC = "schematic"
    SYSTEM = "system"


class ActionType(str, enum.Enum):
    """Enumeration of domain actions."""
    # State & Board Lifecycle
    GET_STATE = "get_state"
    CREATE_BOARD = "create_board"
    LOAD_DOCUMENT = "load_document"
    LOAD_BOARD = "load_board"
    SAVE_DOCUMENT = "save_document"
    SAVE_BOARD = "save_board"
    
    # PCB Footprint Operations
    ADD_FOOTPRINT = "add_footprint"
    REMOVE_FOOTPRINT = "remove_footprint"
    DELETE_FOOTPRINT = "delete_footprint"
    MOVE_FOOTPRINT = "move_footprint"
    ROTATE_FOOTPRINT = "rotate_footprint"
    
    # PCB Net & Pad Operations
    CREATE_NET = "create_net"
    ASSIGN_NET = "assign_net"
    ADD_PAD = "add_pad"
    MODIFY_PAD = "modify_pad"
    
    # PCB Routing & Geometry Operations
    ADD_TRACK = "add_track"
    REMOVE_TRACK = "remove_track"
    ROUTE_TRACK = "route_track"
    ADD_VIA = "add_via"
    CREATE_ZONE = "create_zone"
    ADD_ZONE = "add_zone"
    FILL_ZONE = "fill_zone"
    CREATE_BOARD_OUTLINE = "create_board_outline"
    MODIFY_BOARD_OUTLINE = "modify_board_outline"
    
    # Verification & Checking Operations
    RUN_DRC = "run_drc"
    CHECK_CONNECTIVITY = "check_connectivity"
    VERIFY_CONNECTIVITY = "verify_connectivity"
    CHECK_GEOMETRY = "check_geometry"
    CHECK_PLACEMENT = "check_placement"
    VERIFY_PLACEMENT = "verify_placement"
    RUN_SIMULATION = "run_simulation"
    
    # Transaction / Rollback Operations
    UNDO_ACTION = "undo_action"
    
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


@dataclass
class Action:
    """Domain-neutral Intermediate Representation of a planned action.
    
    Attributes:
        action_type: Type of action to perform.
        parameters: Action-specific parameter payload.
        action_id: Unique action UUID.
        domain: Target domain (PCB, Schematic, System).
        description: Natural language summary of the action's intent.
        preconditions: Conditions required before executing (e.g. 'R1 exists', 'target location is valid').
        expected_outcome: Verifiable assertion about state after execution.
        rollback_info: State snapshot or inverse action required to undo this action.
        timestamp: Unix epoch timestamp when action was created.
    """
    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    domain: ActionDomain = ActionDomain.PCB
    description: str = ""
    preconditions: List[str] = field(default_factory=list)
    expected_outcome: Optional[Dict[str, Any]] = None
    rollback_info: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize action to dictionary."""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "domain": self.domain.value,
            "parameters": self.parameters,
            "description": self.description,
            "preconditions": self.preconditions,
            "expected_outcome": self.expected_outcome,
            "rollback_info": self.rollback_info,
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
            preconditions=data.get("preconditions", []),
            expected_outcome=data.get("expected_outcome"),
            rollback_info=data.get("rollback_info"),
            timestamp=data.get("timestamp", time.time()),
        )
