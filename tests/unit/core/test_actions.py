"""Unit tests for Core Action IR and Plan representations."""

from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.core.errors import AgentError, ErrorCategory, ErrorSeverity
from kicad_agent.core.goals import Goal, GoalType
from kicad_agent.core.plans import Plan
from kicad_agent.core.results import ActionResult, VerificationResult
from kicad_agent.core.transactions import Transaction, TransactionState


def test_action_creation_and_dict():
    action = Action(
        action_type=ActionType.ADD_FOOTPRINT,
        domain=ActionDomain.PCB,
        parameters={"reference": "R1", "x": 100.0, "y": 100.0},
        description="Place R1",
    )
    assert action.action_type == ActionType.ADD_FOOTPRINT
    assert action.domain == ActionDomain.PCB
    assert action.parameters["reference"] == "R1"

    d = action.to_dict()
    assert d["action_type"] == "add_footprint"
    assert d["domain"] == "pcb"

    restored = Action.from_dict(d)
    assert restored.action_type == ActionType.ADD_FOOTPRINT
    assert restored.parameters["reference"] == "R1"


def test_agent_error_structure():
    err = AgentError(
        category=ErrorCategory.PLACEMENT_ERROR,
        message="R1 collides with U1",
        operation="place_footprint",
        target_object="R1",
        severity=ErrorSeverity.ERROR,
    )
    assert err.category == ErrorCategory.PLACEMENT_ERROR
    assert "R1" in str(err)
    assert err.to_dict()["category"] == "PLACEMENT_ERROR"


def test_plan_and_dependencies():
    plan = Plan()
    a1 = Action(action_type=ActionType.ADD_FOOTPRINT, parameters={"reference": "R1"})
    a2 = Action(action_type=ActionType.ADD_TRACK, parameters={"start": (100, 100)})

    plan.add_action(a1)
    plan.add_action(a2, depends_on=[a1.action_id])

    assert len(plan.actions) == 2
    assert plan.dependencies[a2.action_id] == [a1.action_id]


def test_transaction_lifecycle():
    tx = Transaction()
    assert tx.state == TransactionState.PENDING

    a = Action(action_type=ActionType.ADD_FOOTPRINT)
    tx.stage(a)
    assert len(tx.staged_actions) == 1

    res = ActionResult(action_id=a.action_id, success=True)
    tx.record_result(res)
    tx.commit()
    assert tx.state == TransactionState.COMMITTED
