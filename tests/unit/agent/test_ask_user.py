"""Unit tests for ASK_USER interactive clarification handling."""

from tests import mock_pcbnew
from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.agent.decisions import AgentDecision, DecisionType
from kicad_agent.providers.llm import MockLLMProvider


def test_ask_user_when_requirements_missing():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    # Scripted LLM decision asking for clarification
    llm = MockLLMProvider(decisions=[
        AgentDecision(
            decision_type=DecisionType.ASK_USER,
            user_question="What input and output voltage should the power supply use?",
            reasoning_summary="Missing voltage specifications in request.",
        )
    ])

    agent = KiCadAgent(backend=backend, llm_provider=llm)
    result = agent.run("Build an ambiguous power supply", domain="schematic")

    assert result["status"] == "awaiting_user"
    assert result["user_question"] == "What input and output voltage should the power supply use?"
    assert result["transaction_state"] == "pending" or result["transaction_state"] == "active"
