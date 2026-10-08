"""Runtime validation for the action intermediate representation."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .actions import Action, ActionDomain, ActionType
from .errors import AgentError, ErrorCategory, ErrorSeverity


class ActionValidator:
    """Validate action type, domain, parameters, and state preconditions.

    Validation is intentionally kept at the runtime boundary.  Callers may
    still use the historical ``validate_action`` static API, while execution
    paths can rely on the same diagnostics before touching a backend.
    """

    _PCB_ACTIONS: Set[ActionType] = {
        ActionType.GET_BOARD_STATE, ActionType.GET_NETS, ActionType.CREATE_BOARD,
        ActionType.LOAD_BOARD, ActionType.SAVE_BOARD, ActionType.ADD_FOOTPRINT,
        ActionType.REMOVE_FOOTPRINT, ActionType.DELETE_FOOTPRINT,
        ActionType.MOVE_FOOTPRINT, ActionType.ROTATE_FOOTPRINT, ActionType.CREATE_NET,
        ActionType.ASSIGN_NET, ActionType.ADD_PAD, ActionType.MODIFY_PAD,
        ActionType.ADD_TRACK, ActionType.REMOVE_TRACK, ActionType.ROUTE_TRACK,
        ActionType.ADD_VIA, ActionType.CREATE_ZONE, ActionType.ADD_ZONE,
        ActionType.FILL_ZONE, ActionType.CREATE_BOARD_OUTLINE,
        ActionType.MODIFY_BOARD_OUTLINE, ActionType.RUN_DRC,
        ActionType.CHECK_CONNECTIVITY, ActionType.CHECK_GEOMETRY,
        ActionType.CHECK_PLACEMENT, ActionType.VERIFY_PLACEMENT,
    }
    _SCHEMATIC_ACTIONS: Set[ActionType] = {
        ActionType.GET_SCHEMATIC_STATE, ActionType.GET_SYMBOL_PINS,
        ActionType.LOAD_DOCUMENT, ActionType.SAVE_DOCUMENT, ActionType.RUN_ERC,
        ActionType.CHECK_CONNECTIVITY, ActionType.VERIFY_CONNECTIVITY,
        ActionType.ADD_SYMBOL, ActionType.MOVE_SYMBOL, ActionType.ROTATE_SYMBOL,
        ActionType.DELETE_SYMBOL, ActionType.ADD_WIRE, ActionType.ADD_JUNCTION,
        ActionType.ADD_LABEL, ActionType.ADD_BUS, ActionType.ADD_POWER,
    }
    _READ_ONLY: Set[ActionType] = {
        ActionType.GET_STATE, ActionType.GET_BOARD_STATE,
        ActionType.GET_SCHEMATIC_STATE, ActionType.GET_SYMBOL_PINS,
        ActionType.GET_NETS, ActionType.RUN_DRC, ActionType.RUN_ERC,
        ActionType.CHECK_CONNECTIVITY, ActionType.CHECK_GEOMETRY,
        ActionType.CHECK_PLACEMENT, ActionType.VERIFY_CONNECTIVITY,
        ActionType.VERIFY_PLACEMENT,
    }

    @classmethod
    def validate_action(
        cls, action: Action, current_state: Optional[Dict[str, Any]] = None
    ) -> List[AgentError]:
        errors: List[AgentError] = []
        action_type = getattr(action, "action_type", None)
        domain = getattr(action, "domain", None)
        parameters = getattr(action, "parameters", None)

        if not isinstance(action_type, ActionType):
            errors.append(cls._error("invalid_action_type", "Action type is not a known ActionType.", action))
            return errors
        if not isinstance(domain, ActionDomain):
            errors.append(cls._error("invalid_domain", "Action domain is not a known ActionDomain.", action))
        if not isinstance(parameters, dict):
            errors.append(cls._error("invalid_parameters", "Action parameters must be an object.", action))
            return errors

        if parameters.get("_unknown_tool"):
            errors.append(cls._error(
                "unknown_tool", f"Unknown tool '{parameters['_unknown_tool']}'.", action
            ))

        expected_domains = cls._expected_domains(action_type)
        if expected_domains and domain not in expected_domains:
            errors.append(cls._error(
                "domain_mismatch",
                f"Action '{action_type.value}' is not valid for domain '{domain.value}'.",
                action,
                expected=list(sorted(d.value for d in expected_domains)),
                actual=domain.value,
            ))

        errors.extend(cls._validate_parameters(action_type, parameters, action))
        if current_state is not None:
            errors.extend(cls._validate_preconditions(action, current_state))
        return errors

    @classmethod
    def _expected_domains(cls, action_type: ActionType) -> Set[ActionDomain]:
        if action_type == ActionType.GET_STATE or action_type in {
            ActionType.UNDO_ACTION, ActionType.RUN_SIMULATION,
        }:
            return set()
        domains: Set[ActionDomain] = set()
        if action_type in cls._PCB_ACTIONS:
            domains.add(ActionDomain.PCB)
        if action_type in cls._SCHEMATIC_ACTIONS:
            domains.add(ActionDomain.SCHEMATIC)
        return domains

    @classmethod
    def _validate_parameters(
        cls, action_type: ActionType, p: Dict[str, Any], action: Action
    ) -> List[AgentError]:
        errors: List[AgentError] = []

        def required(names: Iterable[str]) -> None:
            for name in names:
                if name not in p or p[name] is None:
                    errors.append(cls._error(
                        "missing_parameter", f"Missing required parameter '{name}'.",
                        action, parameter=name,
                    ))

        def number(name: str, positive: bool = False) -> None:
            value = p.get(name)
            if value is None:
                return
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                errors.append(cls._error(
                    "invalid_parameter_type", f"Parameter '{name}' must be a finite number.",
                    action, parameter=name, expected="number", actual=type(value).__name__,
                ))
            elif positive and value <= 0:
                errors.append(cls._error(
                    "invalid_parameter_value", f"Parameter '{name}' must be positive.",
                    action, parameter=name, expected="> 0", actual=value,
                ))

        def coordinate_pair(name: str) -> None:
            value = p.get(name)
            if value is None:
                return
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                errors.append(cls._error(
                    "invalid_parameter", f"Parameter '{name}' must contain exactly two coordinates.",
                    action, parameter=name, expected="[x, y]",
                ))
                return
            for index, coordinate in enumerate(value):
                if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) or not math.isfinite(coordinate):
                    errors.append(cls._error(
                        "invalid_parameter_type", f"Parameter '{name}[{index}]' must be a finite number.",
                        action, parameter=f"{name}[{index}]",
                    ))

        if action_type in {
            ActionType.ADD_FOOTPRINT, ActionType.MOVE_FOOTPRINT,
            ActionType.ROTATE_FOOTPRINT, ActionType.REMOVE_FOOTPRINT,
            ActionType.ADD_SYMBOL, ActionType.MOVE_SYMBOL,
            ActionType.ROTATE_SYMBOL, ActionType.DELETE_SYMBOL,
        }:
            if "reference" not in p and "ref" not in p:
                required(["reference"])
            reference_key = "reference" if "reference" in p else "ref"
            if reference_key in p and not isinstance(p[reference_key], str):
                errors.append(cls._error(
                    "invalid_parameter_type", "Parameter 'reference' must be a string.",
                    action, parameter=reference_key,
                ))
        if action_type in {ActionType.ADD_FOOTPRINT, ActionType.MOVE_FOOTPRINT,
                           ActionType.ADD_SYMBOL, ActionType.MOVE_SYMBOL}:
            required(["x", "y"])
            number("x")
            number("y")
        if action_type in {ActionType.ROTATE_FOOTPRINT, ActionType.ROTATE_SYMBOL}:
            required(["angle"])
            number("angle")
        if action_type == ActionType.ADD_SYMBOL:
            if "lib_id" in p and not isinstance(p["lib_id"], str):
                errors.append(cls._error("invalid_parameter_type", "Parameter 'lib_id' must be a string.", action, parameter="lib_id"))
        if action_type == ActionType.ADD_TRACK:
            if "start" in p:
                coordinate_pair("start")
            else:
                required(["x1", "y1"])
                number("x1")
                number("y1")
            if "end" in p:
                coordinate_pair("end")
            else:
                required(["x2", "y2"])
                number("x2")
                number("y2")
            if "width_mm" in p:
                number("width_mm", positive=True)
        if action_type in {ActionType.ADD_WIRE, ActionType.ADD_BUS}:
            required(["start", "end"])
            coordinate_pair("start")
            coordinate_pair("end")
        if action_type == ActionType.ADD_JUNCTION:
            required(["x", "y"])
            number("x")
            number("y")
        if action_type == ActionType.ADD_LABEL:
            required(["text", "x", "y"])
            if "text" in p and not isinstance(p["text"], str):
                errors.append(cls._error("invalid_parameter_type", "Parameter 'text' must be a string.", action, parameter="text"))
            number("x")
            number("y")
        if action_type == ActionType.ADD_POWER:
            if not any(p.get(key) for key in ("symbol", "name", "value")):
                errors.append(cls._error("missing_parameter", "ADD_POWER requires a non-empty symbol, name, or value.", action))
            required(["x", "y"])
            number("x")
            number("y")
        if action_type == ActionType.CREATE_BOARD_OUTLINE:
            required(["width", "height"])
            number("width", positive=True)
            number("height", positive=True)
        if action_type in {ActionType.LOAD_BOARD, ActionType.LOAD_DOCUMENT}:
            required(["filepath"])
            if "filepath" in p and not isinstance(p["filepath"], str):
                errors.append(cls._error("invalid_parameter_type", "Parameter 'filepath' must be a string.", action, parameter="filepath"))
        return errors

    @classmethod
    def _validate_preconditions(cls, action: Action, state: Dict[str, Any]) -> List[AgentError]:
        errors: List[AgentError] = []
        components = state.get("components", [])
        refs = {
            item.get("ref", item.get("reference", "")) if isinstance(item, dict) else item
            for item in components
        }
        ref = action.parameters.get("reference", action.parameters.get("ref", ""))
        requires_existing = action.action_type in {
            ActionType.MOVE_FOOTPRINT, ActionType.ROTATE_FOOTPRINT,
            ActionType.REMOVE_FOOTPRINT, ActionType.DELETE_FOOTPRINT,
            ActionType.MOVE_SYMBOL, ActionType.ROTATE_SYMBOL, ActionType.DELETE_SYMBOL,
        }
        if requires_existing and ref and ref not in refs:
            errors.append(cls._error(
                "missing_object", f"Component '{ref}' does not exist for '{action.action_type.value}'.",
                action, target_object=ref, expected="existing component",
            ))
        if action.action_type in {ActionType.ADD_FOOTPRINT, ActionType.ADD_SYMBOL} and ref and ref in refs:
            errors.append(cls._error(
                "duplicate_object", f"Component '{ref}' already exists in the design.",
                action, target_object=ref,
            ))
        for precondition in getattr(action, "preconditions", []) or []:
            if not isinstance(precondition, str) or not precondition.strip():
                errors.append(cls._error("invalid_precondition", "Preconditions must be non-empty strings.", action))
                continue
            if precondition.lower().endswith(" exists"):
                required_ref = precondition[:-7].strip()
                if required_ref and required_ref not in refs:
                    errors.append(cls._error(
                        "precondition_failed", f"Precondition '{precondition}' is not satisfied.",
                        action, target_object=required_ref, precondition=precondition,
                    ))
        return errors

    @staticmethod
    def _error(code: str, message: str, action: Action, **details: Any) -> AgentError:
        return AgentError(
            category=ErrorCategory.INVALID_ACTION if code in {"invalid_action_type", "domain_mismatch", "unknown_tool"} else (
                ErrorCategory.MISSING_OBJECT if code in {"missing_object", "precondition_failed"} else ErrorCategory.INVALID_PARAMETER
            ),
            message=message,
            operation=getattr(getattr(action, "action_type", None), "value", None),
            context={"code": code, **details},
            severity=ErrorSeverity.ERROR,
            recoverable=False,
        )
