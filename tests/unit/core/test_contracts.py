from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.core.contracts import (
    AgentMode,
    AgentSession,
    AssistantMessage,
    Observation,
    PermissionDecision,
    PermissionRequest,
    RepairAttempt,
    SessionStatus,
    ToolCallMessage,
    ToolResultMessage,
    UserMessage,
)
from kicad_agent.core.tool_contracts import ToolRequest, ToolResponse
from kicad_agent.core.plans import Plan, PlanStage
from kicad_agent.core.results import ActionResult
from kicad_agent.tasks.task import Task


def _action() -> Action:
    return Action(
        action_type=ActionType.GET_STATE,
        domain=ActionDomain.SCHEMATIC,
        description="Inspect schematic",
    )


def test_session_contract_serializes_nested_runtime_objects():
    action = _action()
    session = AgentSession(
        task=Task(description="Inspect the schematic", domain="schematic"),
        mode=AgentMode.PLAN,
        status=SessionStatus.RUNNING,
        actions=[action],
        results=[ActionResult(action_id=action.action_id, success=True)],
        observations=[Observation(kind="state", message="Schematic loaded")],
        repairs=[RepairAttempt(action_id=action.action_id, attempt=1, reason="retry")],
        pending_permission=PermissionRequest(
            action=action,
            reason="The operation requires approval",
            decision=PermissionDecision.ASK,
        ),
    )

    payload = session.to_dict()

    assert payload["mode"] == "plan"
    assert payload["status"] == "running"
    assert payload["task"]["domain"] == "schematic"
    assert payload["actions"][0]["action_type"] == "get_state"
    assert payload["results"][0]["success"] is True
    assert payload["observations"][0]["kind"] == "state"
    assert payload["repairs"][0]["attempt"] == 1
    assert payload["pending_permission"]["decision"] == "ask"


def test_session_contract_round_trips_all_nested_objects():
    action = _action()
    plan = Plan(
        goals=[],
        actions=[action],
        stages=[PlanStage(name="inspect", order=1, action_ids=[action.action_id])],
    )
    original = AgentSession(
        task=Task(description="Inspect the schematic", domain="schematic"),
        mode=AgentMode.VERIFY,
        status=SessionStatus.WAITING_APPROVAL,
        plan=plan,
        actions=[action],
        results=[ActionResult(action_id=action.action_id, success=True)],
    )

    restored = AgentSession.from_dict(original.to_dict())

    assert restored.session_id == original.session_id
    assert restored.mode is AgentMode.VERIFY
    assert restored.status is SessionStatus.WAITING_APPROVAL
    assert restored.plan is not None
    assert restored.plan.stages[0].name == "inspect"
    assert restored.actions[0].action_type is action.action_type
    assert restored.results[0].success is True


def test_session_messages_round_trip_with_tool_call_and_result():
    request = ToolRequest(
        tool_name="get_schematic_state",
        arguments={"detail": "nets"},
    )
    original = AgentSession()
    original.append_message(UserMessage(content="Inspect the schematic."))
    original.append_message(
        AssistantMessage(content="I will inspect the current nets.", tool_calls=[request])
    )
    original.append_message(ToolCallMessage(request=request))
    original.append_message(
        ToolResultMessage(
            response=ToolResponse(
                tool_name=request.tool_name,
                success=True,
                data={"nets": ["GND", "VCC"]},
                request_id=request.request_id,
            )
        )
    )

    restored = AgentSession.from_dict(original.to_dict())

    assert len(restored.messages) == 4
    assert isinstance(restored.messages[0], UserMessage)
    assert isinstance(restored.messages[1], AssistantMessage)
    assert restored.messages[1].tool_calls[0].tool_name == "get_schematic_state"
    assert isinstance(restored.messages[2], ToolCallMessage)
    assert isinstance(restored.messages[3], ToolResultMessage)
    assert restored.messages[3].response.data["nets"] == ["GND", "VCC"]
