from kicad_agent.core.session import AgentSession, SessionMessage


def test_compaction_preserves_request_and_pending_tool_call():
    session = AgentSession(user_request="place R1", domain="pcb")
    session.append(SessionMessage.user("place R1"))
    for index in range(45):
        session.append(SessionMessage.assistant(f"step {index}"))
    session.append(
        SessionMessage.assistant(
            tool_name="add_footprint",
            tool_call_id="pending-1",
            arguments={"reference": "R1"},
        )
    )

    assert session.compact(max_messages=10) is True
    assert session.messages[0].message_type.value == "system"
    assert any(
        message.tool_call_id == "pending-1"
        for message in session.pending_tool_calls()
    )
    assert session.metadata["compacted_events"] > 0
