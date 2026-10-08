"""Unit tests for agent lifecycle: observe, plan, execute, verify, repair, tools, and validation."""

import pytest

from tests import mock_pcbnew
from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.agent.error_analyzer import ErrorAnalyzer
from kicad_agent.agent.planner import Planner
from kicad_agent.agent.repair import RepairEngine
from kicad_agent.agent.tools import ToolRegistry, ALL_TOOLS_SCHEMA
from kicad_agent.providers.llm import LLMProvider
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.core.actions import Action, ActionType
from kicad_agent.core.errors import AgentError, ErrorCategory
from kicad_agent.core.goals import Goal, GoalType
from kicad_agent.core.results import ActionResult
from kicad_agent.core.validator import ActionValidator


def test_planner_request_generation():
    planner = Planner()
    plan = planner.plan_request("Place resistor R1 (10k) at (100, 100)", domain="pcb")
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.action_type == ActionType.ADD_FOOTPRINT
    assert action.parameters["reference"] == "R1"
    assert action.parameters["x"] == 100.0


def test_planner_multi_component_creation():
    planner = Planner()
    plan = planner.plan_request("Create a PCB with an Arduino Leonardo, LED, resistor and connector")
    assert len(plan.actions) >= 4
    types = [a.action_type for a in plan.actions]
    assert ActionType.CREATE_BOARD in types
    assert ActionType.CREATE_BOARD_OUTLINE in types
    assert ActionType.ADD_FOOTPRINT in types


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


def test_action_validator_preconditions():
    # Valid action
    act = Action(action_type=ActionType.ADD_FOOTPRINT, parameters={"reference": "R1", "x": 10.0, "y": 20.0})
    errs = ActionValidator.validate_action(act, current_state={"components": []})
    assert len(errs) == 0

    # Missing parameters
    bad_act = Action(action_type=ActionType.ADD_FOOTPRINT, parameters={"reference": "R1"})
    errs2 = ActionValidator.validate_action(bad_act)
    assert len(errs2) > 0

    # Moving non-existent component
    move_act = Action(action_type=ActionType.MOVE_FOOTPRINT, parameters={"reference": "U99", "x": 30.0, "y": 20.0})
    errs3 = ActionValidator.validate_action(move_act, current_state={"components": [{"ref": "R1"}]})
    assert len(errs3) > 0
    assert errs3[0].category == ErrorCategory.MISSING_OBJECT


def test_tool_registry():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    registry = ToolRegistry(backend=backend)
    tools = registry.get_available_tools()
    assert len(tools) > 10

    # Execute read tool
    res = registry.execute_tool("get_board_info", {})
    assert res["status"] == "success"

    # Execute write tool
    res_add = registry.execute_tool("add_footprint", {"reference": "R1", "x": 50.0, "y": 50.0, "value": "10k"})
    assert res_add["status"] == "success"


def test_tool_registry_guards_llm_mutations_with_action_validation():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()
    registry = ToolRegistry(backend=backend)

    result = registry.execute_guarded_tool(
        "move_footprint",
        {"reference": "U99", "x": 30.0, "y": 20.0},
    )

    assert result["status"] == "error"
    assert result["code"] == "ACTION_VALIDATION_FAILED"
    assert result["errors"][0]["category"] == "MISSING_OBJECT"


def test_tool_registry_requires_approval_for_high_risk_llm_mutations():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()
    registry = ToolRegistry(backend=backend)

    result = registry.execute_guarded_tool(
        "remove_footprint",
        {"reference": "R1"},
    )

    assert result["status"] == "approval_required"
    assert result["code"] == "APPROVAL_REQUIRED"
    assert result["risk"] == "high"


def test_agent_orchestrator_run():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    agent = KiCadAgent(backend=backend)
    result = agent.run("Place resistor R1 (10k) at (100, 100)", domain="pcb")
    assert result["success"]
    assert len(result["results"]) > 0
    assert "trace" in result
    assert len(result["trace"]["events"]) > 0


def test_agent_llm_entry_point_uses_backend_tool_registry():
    class ScriptedProvider(LLMProvider):
        def __init__(self):
            self.calls = 0

        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            self.calls += 1
            if self.calls == 1:
                return {
                    "content": "Inspecting the board.",
                    "tool_calls": [{
                        "id": "board-call",
                        "function": {
                            "name": "get_board_info",
                            "arguments": {},
                        },
                    }],
                }
            return {"content": "The board was inspected."}

    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()
    provider = ScriptedProvider()

    agent = KiCadAgent(backend=backend, provider=provider)
    result = agent.run_llm("Inspect the board")

    assert result["status"] == "completed"
    assert result["steps"] == 2
    assert provider.calls == 2
    assert agent.state.session.messages[-2].message_type.value == "tool_result"
    assert agent.state.session.messages[-1].message_type.value == "assistant"
    event_types = [event["event_type"] for event in result["trace"]["events"]]
    assert "LLM_PROVIDER_CALL" in event_types
    assert "LLM_TOOL_CALL" in event_types
    assert "LLM_TOOL_RESULT" in event_types
    assert result["trace"]["metrics"]["success"] is True


def test_agent_can_resolve_llm_approval():
    class ApprovalProvider(LLMProvider):
        def __init__(self):
            self.calls = 0

        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            self.calls += 1
            if self.calls == 1:
                return {
                    "tool_calls": [{
                        "id": "remove-call",
                        "function": {
                            "name": "remove_footprint",
                            "arguments": {"reference": "R1"},
                        },
                    }],
                }
            return {"content": "Approved action completed."}

    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()
    agent = KiCadAgent(backend=backend, provider=ApprovalProvider())

    paused = agent.run_llm("Remove R1")
    resumed = agent.resolve_llm_approval(True)

    assert paused["status"] == "waiting_approval"
    assert resumed["status"] == "completed"


def test_agent_llm_tool_result_includes_independent_verification():
    class MutationProvider(LLMProvider):
        def __init__(self):
            self.calls = 0

        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            self.calls += 1
            if self.calls == 1:
                return {
                    "tool_calls": [{
                        "id": "add-call",
                        "function": {
                            "name": "add_footprint",
                            "arguments": {
                                "reference": "R1",
                                "x": 50.0,
                                "y": 50.0,
                            },
                        },
                    }],
                }
            return {"content": "Placement verified."}

    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()
    agent = KiCadAgent(backend=backend, provider=MutationProvider())

    result = agent.run_llm("Place R1 at 50,50")

    assert result["status"] == "completed"
    tool_result = result["session"]["messages"][2]["result"]
    assert tool_result["status"] == "success"
    assert tool_result["verification"]["passed"] is True


def test_agent_can_cancel_llm_loop():
    class Provider(LLMProvider):
        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            return {"content": "done"}

    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()
    agent = KiCadAgent(backend=backend, provider=Provider())
    agent.run_llm("Inspect the board")

    with pytest.raises(ValueError, match="not active"):
        agent.cancel_llm()


def test_agent_llm_can_use_native_goal_verification():
    class Provider(LLMProvider):
        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            return {"content": "Inspection complete."}

    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()
    agent = KiCadAgent(backend=backend, provider=Provider())
    goal = Goal(
        goal_type=GoalType.INSPECTION,
        description="Inspect the current PCB",
    )

    result = agent.run_llm("Inspect the board", goal=goal)

    assert result["status"] == "completed"
    assert result["session"]["metadata"]["final_verification"]["passed"] is True
    assert result["session"]["metadata"]["final_verification"]["verifier_name"] == "intent"
