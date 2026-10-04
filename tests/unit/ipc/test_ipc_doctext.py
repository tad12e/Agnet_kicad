"""Unit tests for IPCBackend.get_schematic_document_text (cascade Step 1)."""

import pytest

from kicad_agent.backends.ipc import IPCBackend
from kicad_agent.core.errors import AgentError
from kicad_agent.ipc.exceptions import IPCRequestError
from kicad_agent.ipc.messages import ApiStatusCode, DocumentType, get_editor_command_protos

_GetOpenDocumentsResponse = get_editor_command_protos()[3]

LIVE_TEXT = '(kicad_sch (version 20260306) (generator "eeschema") (symbol "R1"))\n'


class _DocTextClient:
    def __init__(self, behavior="ok"):
        self.behavior = behavior
        self.is_connected = True

    def send(self, command, response_type):
        name = type(command).__name__
        if name == "GetOpenDocuments":
            resp = _GetOpenDocumentsResponse()
            doc = resp.documents.add()
            doc.type = DocumentType.DOCTYPE_SCHEMATIC
            doc.board_filename = "Live.kicad_sch"
            return resp
        if name == "SaveDocumentToString":
            if self.behavior == "refused":
                raise IPCRequestError(
                    status_code=ApiStatusCode.AS_UNHANDLED,
                    error_message="no handler available",
                )
            resp = response_type()
            resp.contents = "" if self.behavior == "empty" else LIVE_TEXT
            return resp
        raise AssertionError(f"unexpected command {name}")


def _doc(backend):
    return backend._get_document(DocumentType.DOCTYPE_SCHEMATIC)


def test_live_text_returned_verbatim():
    backend = IPCBackend(client=_DocTextClient("ok"))
    assert backend.get_schematic_document_text(_doc(backend)) == LIVE_TEXT


def test_empty_contents_is_explicit_error():
    backend = IPCBackend(client=_DocTextClient("empty"))
    with pytest.raises(AgentError) as exc_info:
        backend.get_schematic_document_text(_doc(backend))
    assert "empty" in exc_info.value.message


def test_refused_handler_propagates():
    backend = IPCBackend(client=_DocTextClient("refused"))
    with pytest.raises(Exception) as exc_info:
        backend.get_schematic_document_text(_doc(backend))
    assert "no handler" in str(exc_info.value)
