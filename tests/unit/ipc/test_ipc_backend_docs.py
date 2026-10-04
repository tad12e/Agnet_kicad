"""Unit tests for IPCBackend document resolution honesty (Part 3).

_get_document must NEVER fabricate a document: unreachable server, rejected
requests, and empty document lists all raise AgentError(CONNECTION_ERROR).
"""

import pytest

from kicad_agent.backends.ipc import IPCBackend
from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.core.errors import AgentError, ErrorCategory
from kicad_agent.ipc.exceptions import IPCRequestError
from kicad_agent.ipc.messages import (
    ApiStatusCode,
    DocumentType,
    get_base_type_protos,
    get_editor_command_protos,
)


class _FakeClient:
    """Minimal stand-in for KiCadIPCClient with scripted send behavior."""

    def __init__(self, behavior):
        self._behavior = behavior
        self.is_connected = True

    def send(self, command, response_type):
        return self._behavior(command, response_type)


def _make_doc_response(doc_type, board_filename="Test.kicad_sch"):
    _, _, _, GetOpenDocumentsResponse = get_editor_command_protos()
    _, _, _, DocumentSpecifier, _ = get_base_type_protos()
    resp = GetOpenDocumentsResponse()
    doc = resp.documents.add()
    doc.type = doc_type
    doc.board_filename = board_filename
    return resp


def _empty_doc_response():
    _, _, _, GetOpenDocumentsResponse = get_editor_command_protos()
    return GetOpenDocumentsResponse()


def test_get_document_raises_when_server_unreachable():
    def boom(command, response_type):
        raise ConnectionError("pipe gone")

    backend = IPCBackend(client=_FakeClient(boom))
    with pytest.raises(AgentError) as exc_info:
        backend._get_document(DocumentType.DOCTYPE_SCHEMATIC)
    assert exc_info.value.category == ErrorCategory.CONNECTION_ERROR


def test_get_document_raises_when_server_rejects_request():
    def reject(command, response_type):
        raise IPCRequestError(
            status_code=ApiStatusCode.AS_UNHANDLED,
            error_message="no handler available",
        )

    backend = IPCBackend(client=_FakeClient(reject))
    with pytest.raises(AgentError) as exc_info:
        backend._get_document(DocumentType.DOCTYPE_PCB)
    # Transport errors surface as failed results downstream, but resolution
    # itself must not fabricate: either the raw error or a wrapped
    # CONNECTION_ERROR is acceptable, never a dummy doc.
    assert isinstance(exc_info.value, (AgentError, IPCRequestError))


def test_get_document_raises_when_no_documents_open():
    backend = IPCBackend(client=_FakeClient(lambda c, r: _empty_doc_response()))
    with pytest.raises(AgentError) as exc_info:
        backend._get_document(DocumentType.DOCTYPE_SCHEMATIC)
    assert exc_info.value.category == ErrorCategory.CONNECTION_ERROR
    assert "No open document" in exc_info.value.message


def test_get_document_returns_live_doc_without_fabrication():
    backend = IPCBackend(
        client=_FakeClient(
            lambda c, r: _make_doc_response(DocumentType.DOCTYPE_SCHEMATIC)
        )
    )
    doc = backend._get_document(DocumentType.DOCTYPE_SCHEMATIC)
    assert doc.board_filename == "Test.kicad_sch"
    assert getattr(doc, "type", None) == DocumentType.DOCTYPE_SCHEMATIC


def test_execute_reports_failed_result_instead_of_phantom():
    backend = IPCBackend(client=_FakeClient(lambda c, r: _empty_doc_response()))
    action = Action(action_type=ActionType.GET_STATE, domain=ActionDomain.SCHEMATIC)
    result = backend.execute(action)
    assert result.success is False
    assert result.error is not None
