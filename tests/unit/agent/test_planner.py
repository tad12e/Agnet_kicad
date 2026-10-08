from kicad_agent.agent.planner import Planner
from kicad_agent.core.actions import Action, ActionType
from kicad_agent.core.plan_validator import PlanValidator
from kicad_agent.core.plans import Plan
from kicad_agent.tasks import TaskClassifier


def test_classifier_builds_structured_led_task():
    task = TaskClassifier().classify("build an LED circuit", domain="schematic")

    assert task.task_type.value == "build_circuit"
    assert task.domain == "schematic"
    assert task.requirements["components"][0]["reference"] == "D1"


def test_planner_attaches_stages_and_dependencies():
    task = TaskClassifier().classify("build an LED circuit", domain="schematic")
    plan = Planner().plan_task(task)

    assert plan.stages
    assert sum(len(stage.action_ids) for stage in plan.stages) == len(plan.actions)
    assert not plan.metadata["validation_errors"]
    assert plan.actions[1].action_id in plan.dependencies


def test_plan_validator_rejects_cycles():
    first = Action(action_type=ActionType.GET_STATE)
    second = Action(action_type=ActionType.GET_STATE)
    plan = Plan(
        actions=[first, second],
        dependencies={
            first.action_id: [second.action_id],
            second.action_id: [first.action_id],
        },
    )

    errors = PlanValidator().validate(plan)

    assert "Plan dependencies contain a cycle." in errors
