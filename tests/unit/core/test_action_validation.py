"""Focused tests for runtime action validation diagnostics."""

from kicad_agent.agent.tools import tool_call_to_action
from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.core.errors import ErrorCategory
from kicad_agent.core.validator import ActionValidator


def test_validator_rejects_cross_domain_action_with_structured_diagnostic():
    action = Action(
        action_type=ActionType.ADD_SYMBOL,
        domain=ActionDomain.PCB,
        parameters={"reference": "R1", "lib_id": "Device:R", "x": 1, "y": 2},
    )

    errors = ActionValidator.validate_action(action)

    assert errors
    assert errors[0].category == ErrorCategory.INVALID_ACTION
    assert errors[0].context["code"] == "domain_mismatch"
    assert errors[0].context["expected"] == ["schematic"]


def test_validator_reports_parameter_types_and_values():
    action = Action(
        action_type=ActionType.ADD_WIRE,
        domain=ActionDomain.SCHEMATIC,
        parameters={"start": [0, "bad"], "end": [1], "net_name": 42},
    )

    errors = ActionValidator.validate_action(action)

    codes = {error.context["code"] for error in errors}
    assert "invalid_parameter_type" in codes
    assert "invalid_parameter" in codes


def test_validator_checks_declared_and_implicit_preconditions():
    action = Action(
        action_type=ActionType.MOVE_FOOTPRINT,
        parameters={"reference": "U9", "x": 10, "y": 20},
        preconditions=["R1 exists"],
    )

    errors = ActionValidator.validate_action(action, current_state={"components": [{"ref": "R1"}]})

    assert len(errors) == 1
    assert errors[0].category == ErrorCategory.MISSING_OBJECT
    assert errors[0].context["code"] == "missing_object"


def test_unknown_tool_is_not_silently_executed_as_get_state():
    action = tool_call_to_action("not_a_tool", {}, domain="pcb")

    errors = ActionValidator.validate_action(action, current_state={})

    assert errors
    assert errors[0].context["code"] == "unknown_tool"
