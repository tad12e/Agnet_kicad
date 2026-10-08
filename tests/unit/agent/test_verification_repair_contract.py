"""Focused tests for independent post-action verification and bounded repair."""

from kicad_agent.agent.repair import RepairEngine
from kicad_agent.agent.verifier import AgentVerifier
from kicad_agent.core.actions import Action, ActionType
from kicad_agent.core.results import ActionResult


def test_mutation_without_observed_state_is_not_verifiable():
    action = Action(
        action_type=ActionType.ADD_FOOTPRINT,
        parameters={"reference": "R1", "x": 10.0, "y": 10.0},
    )
    result = AgentVerifier().verify_action(
        action, ActionResult(action_id=action.action_id, success=True)
    )

    assert not result.passed
    assert result.outcome == "not_verifiable"
    assert "observation" in result.message.lower()


def test_post_action_observation_is_required_to_pass_mutation():
    action = Action(
        action_type=ActionType.ADD_FOOTPRINT,
        parameters={"reference": "R1", "x": 10.0, "y": 10.0},
    )
    result = AgentVerifier().verify_action(
        action,
        ActionResult(action_id=action.action_id, success=True),
        expected={"state": {"components": [{"ref": "R1", "x": 10.0, "y": 10.0}]}},
    )

    assert result.passed
    assert result.outcome == "passed"


def test_repair_outcome_is_bounded_and_explicit():
    engine = RepairEngine(max_retries=1)
    action = Action(
        action_type=ActionType.ADD_FOOTPRINT,
        parameters={"reference": "R1", "x": 10.0, "y": 10.0},
    )

    first = engine.repair(
        action,
        result=ActionResult(
            action_id=action.action_id,
            success=False,
            data={},
        ),
        attempt=1,
    )
    exhausted = engine.repair(action, attempt=2)

    assert first.status == "not_repairable"
    assert not first.repaired
    assert exhausted.status == "exhausted"
    assert engine.attempt_repair(action, attempt=2) is None
