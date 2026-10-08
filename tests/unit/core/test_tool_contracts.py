from kicad_agent.core.actions import Action, ActionType
from kicad_agent.core.errors import AgentError, ErrorCategory
from kicad_agent.core.results import ActionResult
from kicad_agent.core.tool_contracts import (
    ToolArgument,
    ToolDefinition,
    ToolRequest,
    ToolResponse,
    ToolRisk,
)


def test_tool_definition_and_request_are_json_serializable():
    definition = ToolDefinition(
        name="add_wire",
        description="Connect two points",
        arguments=[
            ToolArgument("start", "array", required=True),
            ToolArgument("end", "array", required=True),
        ],
        risk=ToolRisk.MEDIUM,
        mutating=True,
    )
    request = ToolRequest("add_wire", {"start": [0, 0], "end": [1, 1]})

    assert definition.to_dict()["risk"] == "medium"
    assert definition.to_dict()["arguments"][0]["required"] is True
    assert request.to_dict()["tool_name"] == "add_wire"


def test_tool_response_preserves_structured_failure_details():
    action = Action(action_type=ActionType.ADD_WIRE)
    result = ActionResult(
        action_id=action.action_id,
        success=False,
        error=AgentError(
            category=ErrorCategory.INVALID_PARAMETER,
            message="Wire endpoint is invalid",
            recoverable=True,
        ),
        backend_used="ipc",
    )

    response = ToolResponse.from_action("add_wire", action, result)
    payload = response.to_dict()

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "INVALID_PARAMETER"
    assert payload["error"]["recoverable"] is True
    assert payload["backend"] == "ipc"
