"""Unit tests for AgentDecision and DecisionType abstractions."""

from kicad_agent.agent.decisions import AgentDecision, DecisionType
from kicad_agent.core.actions import Action, ActionType


def test_agent_decision_defaults():
    decision = AgentDecision()
    assert decision.decision_type == DecisionType.TOOL_CALL
    assert decision.confidence == 1.0
    assert decision.goal_status == "in_progress"


def test_agent_decision_tool_call_serialization():
    decision = AgentDecision(
        decision_type=DecisionType.TOOL_CALL,
        tool_name="add_symbol",
        arguments={"reference": "D1", "value": "LED", "x": 100.0, "y": 100.0},
        reasoning_summary="Placing LED D1",
        confidence=0.95,
    )
    d = decision.to_dict()
    assert d["decision_type"] == "TOOL_CALL"
    assert d["tool_name"] == "add_symbol"
    assert d["arguments"]["reference"] == "D1"

    recovered = AgentDecision.from_dict(d)
    assert recovered.decision_type == DecisionType.TOOL_CALL
    assert recovered.tool_name == "add_symbol"
    assert recovered.arguments["value"] == "LED"
    assert recovered.confidence == 0.95


def test_agent_decision_ask_user():
    decision = AgentDecision(
        decision_type=DecisionType.ASK_USER,
        user_question="What input voltage is expected?",
        reasoning_summary="Voltage rating missing",
    )
    d = decision.to_dict()
    assert d["decision_type"] == "ASK_USER"
    assert d["user_question"] == "What input voltage is expected?"

    recovered = AgentDecision.from_dict(d)
    assert recovered.decision_type == DecisionType.ASK_USER
    assert recovered.user_question == "What input voltage is expected?"


def test_agent_decision_complete():
    decision = AgentDecision(
        decision_type=DecisionType.COMPLETE,
        reasoning_summary="All 5V power supply components placed and verified.",
        goal_status="completed",
    )
    assert decision.decision_type == DecisionType.COMPLETE
    assert decision.goal_status == "completed"
