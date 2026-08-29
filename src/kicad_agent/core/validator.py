"""Action validation and precondition checking engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .actions import Action, ActionType
from .errors import AgentError, ErrorCategory, ErrorSeverity


class ActionValidator:
    """Validates actions, parameter schemas, and precondition satisfaction before execution."""

    @staticmethod
    def validate_action(action: Action, current_state: Optional[Dict[str, Any]] = None) -> List[AgentError]:
        """Validate action schema, parameters, and state preconditions.
        
        Returns:
            List of AgentError objects (empty if action is valid).
        """
        errors: List[AgentError] = []
        p = action.parameters
        t = action.action_type

        # 1. Parameter presence and type validation
        if t in (ActionType.ADD_FOOTPRINT, ActionType.MOVE_FOOTPRINT, ActionType.ROTATE_FOOTPRINT, ActionType.REMOVE_FOOTPRINT):
            if "reference" not in p and "ref" not in p:
                errors.append(AgentError(
                    category=ErrorCategory.INVALID_PARAMETER,
                    message=f"Action '{t.value}' requires 'reference' parameter",
                    operation=t.value,
                    severity=ErrorSeverity.ERROR,
                ))

        if t == ActionType.ADD_FOOTPRINT:
            if "x" not in p or "y" not in p:
                errors.append(AgentError(
                    category=ErrorCategory.INVALID_PARAMETER,
                    message="ADD_FOOTPRINT requires 'x' and 'y' coordinates",
                    operation=t.value,
                    severity=ErrorSeverity.ERROR,
                ))

        if t == ActionType.MOVE_FOOTPRINT:
            if "x" not in p or "y" not in p:
                errors.append(AgentError(
                    category=ErrorCategory.INVALID_PARAMETER,
                    message="MOVE_FOOTPRINT requires target 'x' and 'y' coordinates",
                    operation=t.value,
                    severity=ErrorSeverity.ERROR,
                ))

        if t == ActionType.ADD_TRACK:
            start = p.get("start", (p.get("x1"), p.get("y1")))
            end = p.get("end", (p.get("x2"), p.get("y2")))
            if start[0] is None or start[1] is None or end[0] is None or end[1] is None:
                errors.append(AgentError(
                    category=ErrorCategory.INVALID_PARAMETER,
                    message="ADD_TRACK requires valid start and end coordinates",
                    operation=t.value,
                    severity=ErrorSeverity.ERROR,
                ))
            if "width_mm" in p and p["width_mm"] <= 0:
                errors.append(AgentError(
                    category=ErrorCategory.INVALID_PARAMETER,
                    message=f"Track width must be positive, got {p['width_mm']}",
                    operation=t.value,
                    severity=ErrorSeverity.ERROR,
                ))

        if t == ActionType.CREATE_BOARD_OUTLINE:
            width = p.get("width", p.get("width_mm"))
            height = p.get("height", p.get("height_mm"))
            if width is None or height is None or width <= 0 or height <= 0:
                errors.append(AgentError(
                    category=ErrorCategory.INVALID_PARAMETER,
                    message="CREATE_BOARD_OUTLINE requires positive 'width' and 'height'",
                    operation=t.value,
                    severity=ErrorSeverity.ERROR,
                ))

        # 2. Precondition checking against current state
        if current_state:
            components = current_state.get("components", [])
            existing_refs = set()
            for c in components:
                if isinstance(c, dict):
                    existing_refs.add(c.get("ref", c.get("reference", "")))
                elif isinstance(c, str):
                    existing_refs.add(c)

            ref = p.get("reference", p.get("ref", ""))

            # If moving or removing, component must already exist
            if t in (ActionType.MOVE_FOOTPRINT, ActionType.ROTATE_FOOTPRINT, ActionType.REMOVE_FOOTPRINT):
                if ref and ref not in existing_refs:
                    errors.append(AgentError(
                        category=ErrorCategory.MISSING_OBJECT,
                        message=f"Component '{ref}' does not exist on the board to perform '{t.value}'",
                        operation=t.value,
                        target_object=ref,
                        severity=ErrorSeverity.ERROR,
                    ))

            # If adding, duplicate reference warning/error
            if t == ActionType.ADD_FOOTPRINT:
                if ref and ref in existing_refs:
                    errors.append(AgentError(
                        category=ErrorCategory.PLACEMENT_ERROR,
                        message=f"Component '{ref}' already exists on the board",
                        operation=t.value,
                        target_object=ref,
                        severity=ErrorSeverity.ERROR,
                    ))

        return errors
