"""Tests for the compact external-model context contract."""

from kicad_agent.agent.context import AgentContext, ModelContext


def test_model_context_contains_compact_runtime_summary():
    context = AgentContext(
        user_request="Create an LED circuit",
        domain="schematic",
        stages=["Inspect", "Place", "Verify"],
        current_stage="Place",
        current_state_summary={"components": [{"reference": "D1"}]},
        available_tools=["get_state", "add_symbol"],
        recent_observations=["D1 placed"],
        recent_actions=[{"action_type": "add_symbol", "result": "success"}],
        last_error={"category": "validation", "error_message": "missing pin"},
        iteration_count=2,
        max_iterations=10,
    )

    model = context.to_model_context()

    assert isinstance(model, ModelContext)
    assert model.to_dict() == {
        "task": {"description": "Create an LED circuit"},
        "plan": {
            "stages": ["Inspect", "Place", "Verify"],
            "current_stage": "Place",
        },
        "current_state": {"components": [{"reference": "D1"}]},
        "available_tools": ["get_state", "add_symbol"],
        "errors": [{"category": "validation", "error_message": "missing pin"}],
        "observations": [
            "D1 placed",
            {"action_type": "add_symbol", "result": "success"},
        ],
        "iteration": 2,
        "max_iterations": 10,
    }


def test_compact_context_bounds_history_without_changing_legacy_format():
    context = AgentContext(
        recent_observations=["one", "two", "three"],
        recent_actions=[{"id": 1}, {"id": 2}, {"id": 3}],
    )

    compact = context.compact_for_llm(limit=2)

    assert compact["observations"] == [{"id": 2}, {"id": 3}]
    assert "recent_actions" in context.format_for_llm()
