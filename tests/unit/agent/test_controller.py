"""Unit tests for AgentController and the iterative engineering control loop."""

from tests import mock_pcbnew
from kicad_agent.agent.controller import AgentController
from kicad_agent.agent.decisions import AgentDecision, DecisionType
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.providers.llm import MockLLMProvider


def test_controller_single_action_loop():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    # Provide scripted LLM decisions: place R1 -> COMPLETE
    llm = MockLLMProvider(decisions=[
        AgentDecision(
            decision_type=DecisionType.TOOL_CALL,
            tool_name="add_footprint",
            arguments={"reference": "R1", "value": "10k", "x": 100.0, "y": 100.0},
            reasoning_summary="Placing resistor R1",
        ),
        AgentDecision(
            decision_type=DecisionType.COMPLETE,
            reasoning_summary="Resistor placed and confirmed",
            goal_status="completed",
        ),
    ])

    controller = AgentController(backend=backend, llm_provider=llm)
    result = controller.run("Place resistor R1 (10k) at (100, 100)", domain="pcb")

    assert result["success"]
    assert result["status"] == "completed"
    assert result["transaction_state"] == "committed"
    assert len(result["completed_actions"]) == 1
    assert result["completed_actions"][0]["parameters"]["reference"] == "R1"
    assert len(result["observations"]) > 0


def test_controller_iteration_cutoff():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    # Infinite loop LLM that never completes
    def infinite_decider(ctx):
        return AgentDecision(
            decision_type=DecisionType.TOOL_CALL,
            tool_name="add_footprint",
            arguments={"reference": f"R{ctx.iteration_count}", "value": "10k", "x": 10.0 * ctx.iteration_count, "y": 20.0},
            reasoning_summary=f"Placing R{ctx.iteration_count}",
        )

    llm = MockLLMProvider(decision_fn=infinite_decider)
    controller = AgentController(backend=backend, llm_provider=llm, max_iterations=3)
    result = controller.run("Place infinite resistors", domain="pcb")

    # Should safely terminate at max_iterations and rollback incomplete goal
    assert result["iterations"] == 3
    assert result["transaction_state"] == "rolled_back"


def test_controller_rollback_on_failure():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    llm = MockLLMProvider(decisions=[
        AgentDecision(
            decision_type=DecisionType.FAIL,
            reasoning_summary="Design requirements impossible to satisfy",
        )
    ])

    controller = AgentController(backend=backend, llm_provider=llm)
    result = controller.run("Impossible task", domain="pcb")

    assert not result["success"]
    assert result["status"] == "failed"
    assert result["transaction_state"] == "rolled_back"
