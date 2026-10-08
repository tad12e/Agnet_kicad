from tests import mock_pcbnew
from kicad_agent.agent.controller import AgentController
from kicad_agent.agent.decisions import AgentDecision, DecisionType
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.core.contracts import AgentMode
from kicad_agent.providers.llm import MockLLMProvider


def _controller(decisions):
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()
    return AgentController(
        backend=backend, llm_provider=MockLLMProvider(decisions=decisions)
    ), backend


def test_plan_mode_returns_plan_without_executing_actions():
    controller, backend = _controller([])

    result = controller.run(
        "Place resistor R1 (10k) at (100, 100)",
        domain="pcb",
        mode=AgentMode.PLAN,
    )

    assert result["success"] is True
    assert result["status"] == "planned"
    assert result["mode"] == "plan"
    assert result["plan"]["actions"]
    assert backend.get_state("pcb").get("components", []) == []


def test_verify_mode_blocks_mutating_tool_calls():
    controller, backend = _controller(
        [
            AgentDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="add_footprint",
                arguments={"reference": "R1", "value": "10k", "x": 1, "y": 1},
            )
        ]
    )

    result = controller.run("Verify the board", domain="pcb", mode="verify")

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert result["mode"] == "verify"
    assert backend.get_state("pcb").get("components", []) == []


def test_default_mode_remains_build():
    controller, _ = _controller(
        [
            AgentDecision(
                decision_type=DecisionType.COMPLETE,
                reasoning_summary="Already complete",
            )
        ]
    )

    result = controller.run("Inspect board", domain="pcb")

    assert result["mode"] == "build"
