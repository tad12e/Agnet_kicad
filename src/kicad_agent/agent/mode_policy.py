"""Safety policy for the controller's explicit operating modes."""

from __future__ import annotations

from typing import FrozenSet

from ..core.actions import ActionType
from ..core.contracts import AgentMode


READ_ONLY_ACTIONS: FrozenSet[ActionType] = frozenset(
    {
        ActionType.GET_STATE,
        ActionType.GET_SCHEMATIC_STATE,
        ActionType.GET_BOARD_STATE,
        ActionType.GET_SYMBOL_PINS,
        ActionType.GET_NETS,
        ActionType.RUN_DRC,
        ActionType.RUN_ERC,
        ActionType.CHECK_CONNECTIVITY,
        ActionType.VERIFY_CONNECTIVITY,
        ActionType.CHECK_GEOMETRY,
        ActionType.CHECK_PLACEMENT,
        ActionType.VERIFY_PLACEMENT,
        ActionType.RUN_SIMULATION,
    }
)

# Repairs may adjust or remove existing design objects, but must not create a
# new design or silently turn a repair request into a build.
REPAIR_ACTIONS: FrozenSet[ActionType] = frozenset(
    {
        ActionType.MOVE_FOOTPRINT,
        ActionType.ROTATE_FOOTPRINT,
        ActionType.REMOVE_FOOTPRINT,
        ActionType.DELETE_FOOTPRINT,
        ActionType.REMOVE_TRACK,
        ActionType.MODIFY_PAD,
        ActionType.MODIFY_BOARD_OUTLINE,
        ActionType.ADD_TRACK,
        ActionType.ROUTE_TRACK,
        ActionType.ADD_VIA,
        ActionType.CREATE_ZONE,
        ActionType.ADD_ZONE,
        ActionType.FILL_ZONE,
        ActionType.ADD_WIRE,
        ActionType.ADD_JUNCTION,
        ActionType.ADD_LABEL,
        ActionType.ADD_BUS,
        ActionType.ADD_POWER,
    }
)


def normalize_mode(mode: AgentMode | str) -> AgentMode:
    """Return an AgentMode while preserving build as the default."""
    if isinstance(mode, AgentMode):
        return mode
    return AgentMode(str(mode).lower())


def action_allowed(mode: AgentMode, action_type: ActionType) -> bool:
    """Check whether an action is safe to execute in ``mode``."""
    if mode is AgentMode.BUILD:
        return True
    if mode is AgentMode.PLAN:
        return False
    if mode is AgentMode.VERIFY:
        return action_type in READ_ONLY_ACTIONS
    if mode is AgentMode.REPAIR:
        return action_type in READ_ONLY_ACTIONS or action_type in REPAIR_ACTIONS
    return False
