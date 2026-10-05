"""Unit tests verifying MockLLMProvider and multi-turn iterative reasoning."""

import os
from tests import mock_pcbnew
from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.agent.decisions import AgentDecision, DecisionType
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.backends.sexpr import SexprBackend
from kicad_agent.providers.llm import MockLLMProvider


def test_mock_llm_led_circuit_reasoning():
    """Verify multi-turn reasoning for 'Build a simple LED circuit'."""
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    agent = KiCadAgent(backend=backend)
    result = agent.run("Build a simple LED circuit", domain="schematic")

    assert result["success"]
    assert result["status"] == "completed"
    assert result["transaction_state"] == "committed"
    assert len(result["completed_actions"]) >= 2
    # Verify both D1 and R1 were placed and observed
    refs = [a["parameters"].get("reference") for a in result["completed_actions"]]
    assert "D1" in refs
    assert "R1" in refs


def test_mock_llm_5v_regulator_circuit():
    """Verify multi-turn engineering reasoning for 'Build a 5V regulated power supply using an LM7805'."""
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    agent = KiCadAgent(backend=backend)
    result = agent.run("Build a 5V regulated power supply using an LM7805", domain="schematic")

    assert result["success"]
    assert result["status"] == "completed"
    assert result["transaction_state"] == "committed"
    # Verify LM7805 (U1), input cap (C1), output cap (C2) placed
    refs = [a["parameters"].get("reference") for a in result["completed_actions"]]
    assert "U1" in refs
    assert "C1" in refs
    assert "C2" in refs


def test_mock_llm_adaptive_error_recovery():
    """Verify adaptive error recovery: failing wire -> inspect pins -> corrected wire."""
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    # Scripted sequence simulating an initial error on ADD_WIRE, then pin inspection, then corrected wire
    scripted_decisions = [
        # Turn 1: Add LED D1
        AgentDecision(
            decision_type=DecisionType.TOOL_CALL,
            tool_name="add_symbol",
            arguments={"reference": "D1", "value": "LED", "x": 100.0, "y": 100.0},
            reasoning_summary="Placing LED D1",
        ),
        # Turn 2: Add Resistor R1
        AgentDecision(
            decision_type=DecisionType.TOOL_CALL,
            tool_name="add_symbol",
            arguments={"reference": "R1", "value": "330R", "x": 100.0, "y": 80.0},
            reasoning_summary="Placing resistor R1",
        ),
        # Turn 3: Attempt ADD_WIRE with missing/incorrect start coord (triggers validation error)
        AgentDecision(
            decision_type=DecisionType.TOOL_CALL,
            tool_name="add_wire",
            arguments={"start": None, "end": (100.0, 100.0)},
            reasoning_summary="Attempting wire connection",
        ),
        # Turn 4: LLM observes error, inspects pin coords
        AgentDecision(
            decision_type=DecisionType.TOOL_CALL,
            tool_name="get_symbol_pins",
            arguments={"reference": "D1"},
            reasoning_summary="Inspect pins of D1 to determine exact coordinates",
        ),
        # Turn 5: LLM emits corrected ADD_WIRE with valid coords
        AgentDecision(
            decision_type=DecisionType.TOOL_CALL,
            tool_name="add_wire",
            arguments={"start": (100.0, 80.0), "end": (100.0, 100.0)},
            reasoning_summary="Connecting wire with valid coordinates",
        ),
        # Turn 6: Complete
        AgentDecision(
            decision_type=DecisionType.COMPLETE,
            reasoning_summary="Circuit corrected and verified",
            goal_status="completed",
        ),
    ]

    llm = MockLLMProvider(decisions=scripted_decisions)
    agent = KiCadAgent(backend=backend, llm_provider=llm)
    result = agent.run("Build LED circuit with error recovery", domain="schematic")

    assert result["success"]
    assert result["status"] == "completed"
    # Verify the error occurred and was recorded in trace
    error_events = [e for e in result["trace"]["events"] if "VALIDATION_ERROR" in e["event_type"]]
    assert len(error_events) >= 1
    # Verify the corrected wire was executed
    wire_actions = [a for a in result["completed_actions"] if a["action_type"] == "add_wire"]
    assert len(wire_actions) == 1
