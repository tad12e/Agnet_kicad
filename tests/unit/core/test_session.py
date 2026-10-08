from kicad_agent.core.session import (
    AgentSession,
    MessageType,
    SessionMessage,
)


def test_session_round_trips_ordered_tool_conversation():
    session = AgentSession(user_request="Inspect the board")
    user = session.append(SessionMessage.user(session.user_request))
    call = session.append(
        SessionMessage.assistant(
            "I will inspect the board.",
            tool_name="get_board_info",
            arguments={"include_tracks": True},
            tool_call_id="call-1",
        )
    )
    session.append(
        SessionMessage.tool_result(
            "get_board_info",
            {"components": []},
            tool_call_id=call.tool_call_id,
        )
    )

    restored = AgentSession.from_dict(session.to_dict())

    assert restored.messages[0].message_id == user.message_id
    assert restored.messages[1].message_type is MessageType.TOOL_CALL
    assert restored.messages[2].message_type is MessageType.TOOL_RESULT
    assert restored.pending_tool_calls() == []


def test_pending_tool_calls_and_recent_messages_are_bounded():
    session = AgentSession()
    call = session.append(
        SessionMessage.assistant(
            tool_name="inspect_pcb",
            tool_call_id="call-1",
        )
    )
    session.append(SessionMessage.user("follow up"))

    assert session.pending_tool_calls() == [call]
    assert session.recent_messages(1)[0].content == "follow up"
    assert session.recent_messages(0) == []
