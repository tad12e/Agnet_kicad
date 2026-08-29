"""Unit tests for agent lifecycle: observe, plan, execute, verify, repair."""

from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.agent.error_analyzer import ErrorAnalyzer
from kicad_agent.agent.planner import Planner
from kicad_agent.agent.repair import RepairEngine
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.core.actions import Action, ActionType
from kicad_agent.core.errors import AgentError, ErrorCategory
from kicad_agent.core.results import ActionResult


def test_planner_request_generation():
    planner = Planner()
    plan = planner.plan_request("Place resistor R1 (10k) at (100, 100)", domain="pcb")
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.action_type == ActionType.ADD_FOOTPRINT
    assert action.parameters["reference"] == "R1"
    assert action.parameters["x"] == 100.0


def test_error_analyzer():
    analyzer = ErrorAnalyzer()
    err = analyzer.analyze(Exception("R1 already exists on the board"), operation="place_footprint")
    assert err.category == ErrorCategory.PLACEMENT_ERROR
    assert err.recoverable


def test_repair_engine():
    engine = RepairEngine()
    act = Action(
        action_type=ActionType.ADD_FOOTPRINT,
        parameters={"reference": "R1", "x": 100.0, "y": 100.0},
    )
    failed_res = ActionResult(
        action_id=act.action_id,
        success=False,
        error=AgentError(category=ErrorCategory.PLACEMENT_ERROR, message="R1 already exists on the board"),
    )
    repaired_act = engine.attempt_repair(act, failed_res)
    assert repaired_act is not None
    assert repaired_act.parameters["reference"] == "R2"


def test_agent_orchestrator_run():
    backend = PcbnewBackend()
    backend.connect()
    agent = KiCadAgent(backend=backend)

    result = agent.run("Place resistor R1 (10k) at (100, 100)", domain="pcb")
    assert result["success"]
    assert len(result["results"]) > 0
