import json

import pytest

from kicad_agent.core.session import AgentSession, SessionMessage
from kicad_agent.core.session_store import SessionStore, SessionStoreError


def test_session_store_round_trips_conversation(tmp_path):
    session = AgentSession(
        user_request="Inspect the board",
        domain="pcb",
        status="waiting_approval",
        metadata={"steps": 2},
    )
    session.append(SessionMessage.user(session.user_request))
    path = tmp_path / "session.json"

    saved = SessionStore().save(session, path)
    restored = SessionStore().load(saved)

    assert restored.session_id == session.session_id
    assert restored.status == "waiting_approval"
    assert restored.metadata["steps"] == 2
    assert restored.messages[0].content == "Inspect the board"


def test_session_store_rejects_unknown_schema(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"schema_version": 999, "session": {}}),
        encoding="utf-8",
    )

    with pytest.raises(SessionStoreError, match="Unsupported session schema"):
        SessionStore().load(path)
