from kicad_agent.core.actions import Action, ActionType
from kicad_agent.core.contracts import PermissionDecision
from kicad_agent.core.permissions import PermissionPolicy


def test_normal_design_mutation_keeps_existing_build_behavior():
    check = PermissionPolicy().check(
        Action(action_type=ActionType.ADD_SYMBOL)
    )

    assert check.decision is PermissionDecision.ALLOW
    assert check.request is None


def test_destructive_action_emits_structured_approval_request():
    action = Action(
        action_type=ActionType.DELETE_SYMBOL,
        parameters={"reference": "U1"},
    )
    check = PermissionPolicy().check(action)

    assert check.decision is PermissionDecision.ASK
    assert check.request is not None
    assert check.request.action.action_id == action.action_id
    assert check.request.risk == "destructive"
    assert check.request.to_dict()["decision"] == "ask"


def test_explicit_denial_is_preserved():
    action = Action(action_type=ActionType.REMOVE_FOOTPRINT)
    check = PermissionPolicy().decide(action, PermissionDecision.DENY)

    assert check.decision is PermissionDecision.DENY
