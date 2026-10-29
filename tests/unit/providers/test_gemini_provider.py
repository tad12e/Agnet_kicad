"""Unit tests for GeminiProvider."""

from unittest.mock import MagicMock, patch
import pytest

from kicad_agent.agent.context import AgentContext
from kicad_agent.agent.decisions import DecisionType
from kicad_agent.providers.llm import GeminiProvider


def test_gemini_provider_init():
    provider = GeminiProvider(api_key="my-key-abc", model="gemini-2.5-flash")
    assert provider.api_key == "my-key-abc"
    assert provider.model == "gemini-2.5-flash"
    assert "generativelanguage.googleapis.com" in provider.base_url


def test_gemini_message_conversion():
    provider = GeminiProvider(api_key="dummy")
    messages = [
        {"role": "user", "content": "Hello"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Placing resistor"},
                {
                    "type": "tool_use",
                    "id": "call_123",
                    "name": "add_symbol",
                    "input": {"reference": "R1", "x": 100, "y": 100},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_123",
                    "content": {"status": "success"},
                }
            ],
        },
    ]

    converted = provider._convert_messages(messages, system_prompt="You are an EDA agent")

    assert converted[0]["role"] == "system"
    assert converted[0]["content"] == "You are an EDA agent"

    assert converted[1]["role"] == "user"
    assert converted[1]["content"] == "Hello"

    assert converted[2]["role"] == "assistant"
    assert converted[2]["tool_calls"][0]["id"] == "call_123"
    assert converted[2]["tool_calls"][0]["function"]["name"] == "add_symbol"

    assert converted[3]["role"] == "tool"
    assert converted[3]["tool_call_id"] == "call_123"


def test_gemini_tool_call_parsing():
    provider = GeminiProvider(api_key="dummy")

    response = {
        "content": "I am adding resistor R1",
        "tool_calls": [
            {
                "id": "call_1",
                "function": {
                    "name": "add_symbol",
                    "arguments": '{"reference": "R1", "value": "10k", "x": 100, "y": 100}',
                },
            }
        ],
    }

    decision = provider._parse_gemini_response(response)
    assert decision.decision_type == DecisionType.TOOL_CALL
    assert decision.tool_name == "add_symbol"
    assert decision.arguments["reference"] == "R1"
    assert decision.arguments["value"] == "10k"


def test_gemini_completion_parsing():
    provider = GeminiProvider(api_key="dummy")

    response = {
        "content": "The schematic is complete and all wires are connected.",
        "tool_calls": [],
    }

    decision = provider._parse_gemini_response(response)
    assert decision.decision_type == DecisionType.COMPLETE
    assert decision.goal_status == "completed"

