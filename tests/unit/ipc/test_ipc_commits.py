"""Unit tests for IPCBackend commit lifecycle + item verification (Part 4).

Writes must run inside BeginCommit...EndCommit, verify every item status,
and DROP the commit on any failure instead of reporting phantom success.
"""

from google.protobuf.any_pb2 import Any as ProtoAny

from proto.schematic.schematic_types_pb2 import Junction

from kicad_agent.backends.ipc import IPCBackend
from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.ipc.messages import (
    DocumentType,
    get_base_type_protos,
    get_commit_protos,
    get_editor_command_protos,
)

BeginCommit, BeginCommitResponse, EndCommit, EndCommitResponse = get_commit_protos()
CreateItems, CreateItemsResponse, _, GetOpenDocumentsResponse = get_editor_command_protos()
_, _, _, DocumentSpecifier, _ = get_base_type_protos()


def _doc_response():
    resp = GetOpenDocumentsResponse()
    doc = resp.documents.add()
    doc.type = DocumentType.DOCTYPE_SCHEMATIC
    doc.board_filename = "Commit.kicad_sch"
    return resp


class _ScriptedClient:
    """Fake client recording commit lifecycle calls."""

    def __init__(self, create_behavior="ok"):
        self.create_behavior = create_behavior
        self.is_connected = True
        self.begun = 0
        self.dropped = 0
        self.committed = 0

    def _creation_result(self, incoming):
        from common.commands.editor_commands_pb2 import ItemCreationResult

        result = ItemCreationResult()
        sent = incoming.items[0] if incoming.items else None
        junc = Junction()
        if sent is not None:
            sent.Unpack(junc)

        if self.create_behavior == "ok":
            result.status.code = 1  # ISC_OK
            if junc.id.value:
                out = Junction()
                out.CopyFrom(junc)
                result.item.Pack(out)
        elif self.create_behavior == "item_error":
            result.status.code = 7  # ISC_INVALID_DATA
            result.status.error_message = "bad diameter"
        elif self.create_behavior == "empty_id_echo":
            result.status.code = 1  # ISC_OK but no id content
            result.item.Pack(Junction())
        elif self.create_behavior == "request_rejected":
            pass  # handled at response level below
        return result

    def send(self, command, response_type):
        if isinstance(command, BeginCommit):
            self.begun += 1
            resp = BeginCommitResponse()
            resp.id.value = "commit-1"
            return resp
        if isinstance(command, EndCommit):
            if command.action == 2:  # CMA_DROP
                self.dropped += 1
            else:
                self.committed += 1
            return EndCommitResponse()
        if isinstance(command, CreateItems):
            resp = CreateItemsResponse()
            if self.create_behavior == "request_rejected":
                resp.status = 2  # IRS_DOCUMENT_NOT_FOUND
                return resp
            if self.create_behavior == "count_mismatch":
                resp.status = 1  # IRS_OK but zero items
                return resp
            resp.status = 1  # IRS_OK
            resp.created_items.append(self._creation_result(command))
            return resp
        return _doc_response()


def _junction_action():
    return Action(
        action_type=ActionType.ADD_JUNCTION,
        domain=ActionDomain.SCHEMATIC,
        parameters={"position": (10.0, 20.0)},
    )


def test_commit_success_path():
    backend = IPCBackend(client=_ScriptedClient("ok"))
    result = backend.execute(_junction_action())
    assert result.success is True
    assert result.data["items_created"] == 1
    assert result.data["id"]  # server-confirmed id, non-empty
    assert backend.client.begun == 1
    assert backend.client.committed == 1
    assert backend.client.dropped == 0


def test_item_error_drops_commit_and_fails():
    backend = IPCBackend(client=_ScriptedClient("item_error"))
    result = backend.execute(_junction_action())
    assert result.success is False
    assert "bad diameter" in str(result.error)
    assert backend.client.dropped == 1
    assert backend.client.committed == 0


def test_count_mismatch_drops_commit_and_fails():
    backend = IPCBackend(client=_ScriptedClient("count_mismatch"))
    result = backend.execute(_junction_action())
    assert result.success is False
    assert "count mismatch" in str(result.error)
    assert backend.client.dropped == 1


def test_empty_id_echo_drops_commit_and_fails():
    backend = IPCBackend(client=_ScriptedClient("empty_id_echo"))
    result = backend.execute(_junction_action())
    assert result.success is False
    assert "without an id" in str(result.error)
    assert backend.client.dropped == 1


def test_request_level_rejection_drops_commit_and_fails():
    backend = IPCBackend(client=_ScriptedClient("request_rejected"))
    result = backend.execute(_junction_action())
    assert result.success is False
    assert backend.client.dropped == 1
