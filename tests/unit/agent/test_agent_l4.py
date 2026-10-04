"""Agent-level L4 failover composition tests (Part 9).

An IPCBackend without its own fallback adopts the agent-level one, so a
schematic NL request succeeds end-to-end through failover with markers.
"""

import os

from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.backends.ipc import IPCBackend
from kicad_agent.backends.sexpr import SexprBackend
from kicad_agent.ipc.exceptions import IPCRequestError
from kicad_agent.ipc.messages import ApiStatusCode, DocumentType, get_editor_command_protos

_GetOpenDocumentsResponse = get_editor_command_protos()[3]

SCH_SEED = '(kicad_sch (version 20260306) (generator "eeschema")\n)\n'


class _LiveRefusingClient:
    """Resolves documents/reads but refuses every mutating commit."""

    is_connected = True

    def send(self, command, response_type):
        name = type(command).__name__
        if name == "GetOpenDocuments":
            resp = _GetOpenDocumentsResponse()
            doc = resp.documents.add()
            doc.type = DocumentType.DOCTYPE_SCHEMATIC
            doc.board_filename = "L4.kicad_sch"
            return resp
        if name == "GetItems":
            resp = response_type()
            resp.status = 1  # IRS_OK, zero items
            return resp
        raise IPCRequestError(
            status_code=ApiStatusCode.AS_NOT_READY,
            error_message="KiCad is not ready to reply",
        )


def _agent_with_failover(tmp_path):
    sch_file = os.path.join(str(tmp_path), "l4.kicad_sch")
    with open(sch_file, "w", encoding="utf-8") as f:
        f.write(SCH_SEED)
    fallback = SexprBackend(sch_filepath=sch_file)
    backend = IPCBackend(client=_LiveRefusingClient())
    agent = KiCadAgent(backend=backend, fallback=fallback)
    return agent, sch_file


def test_agent_attaches_fallback_to_ipc_backend(tmp_path):
    agent, _ = _agent_with_failover(tmp_path)
    assert agent.backend.fallback is not None
    assert agent.backend.fallback.name == "sexpr"


def test_agent_preserves_backend_own_fallback(tmp_path):
    own = SexprBackend(sch_filepath=os.path.join(str(tmp_path), "own.kicad_sch"))
    other = SexprBackend(sch_filepath=os.path.join(str(tmp_path), "other.kicad_sch"))
    backend = IPCBackend(client=_LiveRefusingClient(), fallback=own)
    agent = KiCadAgent(backend=backend, fallback=other)
    assert agent.backend.fallback is own


def test_schematic_request_succeeds_through_failover(tmp_path):
    agent, sch_file = _agent_with_failover(tmp_path)
    result = agent.run("place resistor R99 (10k) at (100, 100)", domain="schematic")
    assert result["success"] is True
    assert result["results"][0]["result"]["backend_used"] == "ipc->sexpr"
    with open(sch_file, encoding="utf-8") as f:
        assert "R99" in f.read()


def test_schematic_request_fails_honestly_without_fallback():
    backend = IPCBackend(client=_LiveRefusingClient())
    agent = KiCadAgent(backend=backend)
    result = agent.run("place resistor R99 (10k) at (100, 100)", domain="schematic")
    assert result["success"] is False
    assert result["transaction_state"] == "rolled_back"
