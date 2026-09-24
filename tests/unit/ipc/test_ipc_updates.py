"""Unit tests for IPCBackend update/delete mappings (Part 7).

MOVE/DELETE_SYMBOL run fetch-mutate-write inside commits with per-item
verification; failures drop the commit and report honestly.
"""

from google.protobuf.any_pb2 import Any as ProtoAny

from proto.schematic.schematic_types_pb2 import SchematicSymbolInstance

from kicad_agent.backends.ipc import IPCBackend
from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.ipc.messages import DocumentType, get_editor_command_protos

_GetOpenDocumentsResponse = get_editor_command_protos()[3]


def _pack(msg):
    any_msg = ProtoAny()
    any_msg.Pack(msg)
    return any_msg


def _live_symbol(ref="R1", sym_id="sym-r1", x_nm=100_000_000, y_nm=100_000_000):
    sym = SchematicSymbolInstance()
    sym.id.value = sym_id
    sym.position.x_nm = x_nm
    sym.position.y_nm = y_nm
    sym.definition.id.library_nickname = "Device"
    sym.definition.id.entry_name = "R"
    sym.reference_field.text.text = ref
    sym.value_field.text.text = "10k"
    return sym


class _UpdateClient:
    """Scripts update/delete/commit responses; records lifecycle."""

    def __init__(self, update_behavior="ok", delete_behavior="ok"):
        self.update_behavior = update_behavior
        self.delete_behavior = delete_behavior
        self.is_connected = True
        self.begun = 0
        self.dropped = 0
        self.committed = 0
        self.last_update_pos = None

    def _doc_response(self):
        resp = _GetOpenDocumentsResponse()
        doc = resp.documents.add()
        doc.type = DocumentType.DOCTYPE_SCHEMATIC
        doc.board_filename = "Upd.kicad_sch"
        return resp

    def send(self, command, response_type):
        from common.commands.editor_commands_pb2 import (
            BeginCommit,
            BeginCommitResponse,
            EndCommit,
            EndCommitResponse,
            ItemCreationResult,
            ItemUpdateResult,
            ItemDeletionResult,
        )

        name = type(command).__name__
        if name == "GetOpenDocuments":
            return self._doc_response()
        if name == "BeginCommit":
            self.begun += 1
            resp = BeginCommitResponse()
            resp.id.value = "commit-7"
            return resp
        if name == "EndCommit":
            if command.action == 2:
                self.dropped += 1
            else:
                self.committed += 1
            return EndCommitResponse()
        if name == "GetItems":
            resp = response_type()
            resp.status = 1
            resp.items.append(_pack(_live_symbol()))
            return resp
        if name == "GetItemsById":
            resp = response_type()
            resp.status = 1
            resp.items.append(_pack(_live_symbol()))
            return resp
        if name == "UpdateItems":
            resp = response_type()
            resp.status = 1
            incoming = SchematicSymbolInstance()
            command.items[0].Unpack(incoming)
            self.last_update_pos = (
                incoming.position.x_nm,
                incoming.position.y_nm,
            )
            result = ItemUpdateResult()
            if self.update_behavior == "ok":
                result.status.code = 1
                result.item.Pack(incoming)
            else:
                result.status.code = 7
                result.status.error_message = "locked"
            resp.updated_items.append(result)
            return resp
        if name == "DeleteItems":
            resp = response_type()
            resp.status = 1
            for kiid in command.item_ids:
                result = ItemDeletionResult()
                result.id.value = kiid.value
                if self.delete_behavior == "ok":
                    result.status = 1  # IDS_OK
                else:
                    result.status = 2  # IDS_NONEXISTENT
            resp.deleted_items.append(result)
            return resp
        if name == "CreateItems":
            resp = response_type()
            resp.status = 1
            # Echo the sent payload back with its id preserved (pack BEFORE
            # append: repeated-field append copies the message state).
            from proto.schematic.schematic_types_pb2 import SchematicLine

            echo = SchematicLine()
            command.items[0].Unpack(echo)
            result = ItemCreationResult()
            result.status.code = 1
            result.item.Pack(echo)
            resp.created_items.append(result)
            return resp
        raise AssertionError(f"unexpected command {name}")


def _move_action(ref="R1", x=50.0, y=60.0):
    return Action(
        action_type=ActionType.MOVE_SYMBOL,
        domain=ActionDomain.SCHEMATIC,
        parameters={"reference": ref, "x": x, "y": y},
    )


def test_move_symbol_updates_position_in_commit():
    backend = IPCBackend(client=_UpdateClient())
    result = backend.execute(_move_action())
    assert result.success is True
    assert result.data["id"] == "sym-r1"
    assert result.data["x"] == 50.0
    assert backend.client.last_update_pos == (50_000_000, 60_000_000)
    assert backend.client.committed == 1
    assert backend.client.dropped == 0


def test_move_unknown_reference_fails_before_commit():
    backend = IPCBackend(client=_UpdateClient())
    result = backend.execute(_move_action(ref="ZZ9"))
    assert result.success is False
    assert "not found" in str(result.error)
    assert backend.client.begun == 0


def test_update_item_error_drops_commit():
    backend = IPCBackend(client=_UpdateClient(update_behavior="locked"))
    result = backend.execute(_move_action())
    assert result.success is False
    assert "locked" in str(result.error)
    assert backend.client.dropped == 1
    assert backend.client.committed == 0


def test_delete_symbol_by_reference():
    backend = IPCBackend(client=_UpdateClient())
    action = Action(
        action_type=ActionType.DELETE_SYMBOL,
        domain=ActionDomain.SCHEMATIC,
        parameters={"reference": "r1"},
    )
    result = backend.execute(action)
    assert result.success is True
    assert result.data["id"] == "sym-r1"
    assert backend.client.committed == 1


def test_delete_nonexistent_drops_commit():
    backend = IPCBackend(client=_UpdateClient(delete_behavior="gone"))
    action = Action(
        action_type=ActionType.DELETE_SYMBOL,
        domain=ActionDomain.SCHEMATIC,
        parameters={"id": "sym-ghost"},
    )
    result = backend.execute(action)
    assert result.success is False
    assert "sym-ghost" in str(result.error)
    assert backend.client.dropped == 1


def test_add_wire_mapped():
    backend = IPCBackend(client=_UpdateClient())
    action = Action(
        action_type=ActionType.ADD_WIRE,
        domain=ActionDomain.SCHEMATIC,
        parameters={"start": [0.0, 0.0], "end": [10.0, 0.0]},
    )
    result = backend.execute(action)
    assert result.success is True
    assert result.data["id"]
    assert backend.client.committed == 1


def test_add_label_bad_type_rejected():
    backend = IPCBackend(client=_UpdateClient())
    action = Action(
        action_type=ActionType.ADD_LABEL,
        domain=ActionDomain.SCHEMATIC,
        parameters={"text": "X", "x": 1.0, "y": 1.0, "label_type": "fancy"},
    )
    result = backend.execute(action)
    assert result.success is False
    assert "label_type" in str(result.error)
