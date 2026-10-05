"""Unit tests for two-level verification (Action-level and Goal-level)."""

from kicad_agent.agent.verifier import AgentVerifier
from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.core.results import ActionResult
from kicad_agent.tasks.task import Task, TaskType


def test_action_level_verification_placement():
    verifier = AgentVerifier()
    act = Action(
        action_type=ActionType.ADD_FOOTPRINT,
        domain=ActionDomain.PCB,
        parameters={"reference": "R1", "x": 10.0, "y": 20.0},
    )
    res = ActionResult(action_id=act.action_id, success=True, data={"reference": "R1", "x": 10.0, "y": 20.0})
    state = {"components": [{"reference": "R1", "x": 10.0, "y": 20.0}]}

    v_res = verifier.verify_action(act, res, expected={"state": state})
    assert v_res.passed


def test_action_level_verification_failed_action():
    verifier = AgentVerifier()
    act = Action(action_type=ActionType.ADD_WIRE, domain=ActionDomain.SCHEMATIC, parameters={"start": (0, 0), "end": (10, 0)})
    res = ActionResult(action_id=act.action_id, success=False)
    v_res = verifier.verify_action(act, res)
    assert not v_res.passed


def test_goal_level_verification_satisfaction():
    verifier = AgentVerifier()
    task = Task(
        task_id="task-100",
        task_type=TaskType.BUILD_CIRCUIT,
        requirements={
            "components": [
                {"reference": "D1", "type": "led"},
                {"reference": "R1", "type": "resistor"},
            ]
        },
    )
    # State has both D1 and R1
    complete_state = {"components": [{"reference": "D1"}, {"reference": "R1"}]}
    v_res = verifier.verify_task(task, complete_state)
    assert v_res.passed

    # State missing R1
    incomplete_state = {"components": [{"reference": "D1"}]}
    v_res_fail = verifier.verify_task(task, incomplete_state)
    assert not v_res_fail.passed
    assert "R1" in v_res_fail.message
