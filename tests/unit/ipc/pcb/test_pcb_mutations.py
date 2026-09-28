"""Unit tests for PCB IPC mutations (Part 5)."""

from typing import List
from google.protobuf.empty_pb2 import Empty
import pytest

from kicad_agent.ipc.messages import (
    CommitAction, DocumentType, ItemDeletionStatus,
    ItemRequestStatus, ItemStatusCode,
)
from kicad_agent.ipc.pcb.messages_pcb import (
    get_base_type,
    get_board_command, get_board_type, get_commit_protos,
    get_editor_command, get_item_mutation,
)
from kicad_agent.ipc.pcb.mutations_pcb import (
    PCBMutationError, add_arc, add_copper_zone, add_footprint_instance,
    add_track, add_via, begin_commit, delete_items_by_id,
    delete_items_in_commit, end_commit, refill_zones, run_commit,
    update_item, update_item_in_commit,
)
from kicad_agent.ipc.pcb.types_pcb import pack_any

BeginCommit, BeginCommitResponse, EndCommit, EndCommitResponse = get_commit_protos()
CreateItems = get_editor_command("CreateItems")
CreateItemsResponse = get_editor_command("CreateItemsResponse")
UpdateItems = get_item_mutation("UpdateItems")
UpdateItemsResponse = get_item_mutation("UpdateItemsResponse")
DeleteItems = get_item_mutation("DeleteItems")
DeleteItemsResponse = get_item_mutation("DeleteItemsResponse")
RefillZones = get_board_command("RefillZones")
GetBoardEnabledLayers = get_board_command("GetBoardEnabledLayers")
BoardEnabledLayersResponse = get_board_command("BoardEnabledLayersResponse")
from common.commands.editor_commands_pb2 import (
    ItemCreationResult,
    ItemUpdateResult,
    ItemDeletionResult,
)
Track = get_board_type("Track")
DocumentSpecifier = get_base_type("DocumentSpecifier")


def _fake_doc():
    doc = DocumentSpecifier()
    doc.type = DocumentType.DOCTYPE_PCB
    doc.board_filename = "test_board.kicad_pcb"
    return doc


class _ScriptedPCBClient:
    def __init__(self, behavior="ok"):
        self.behavior = behavior
        self.is_connected = True
        self.begun = 0
        self.committed = 0
        self.dropped = 0
        self.commands_received: List[object] = []
        self.assigned_id = "kiid-test-001"

    def send(self, command, response_type):
        self.commands_received.append(command)

        if isinstance(command, BeginCommit):
            self.begun += 1
            resp = BeginCommitResponse()
            resp.id.value = "commit-pcb-1"
            return resp

        if isinstance(command, EndCommit):
            if command.action == CommitAction.CMA_DROP:
                self.dropped += 1
            else:
                self.committed += 1
            return EndCommitResponse()

        if isinstance(command, CreateItems):
            resp = CreateItemsResponse()
            if self.behavior == "request_rejected":
                resp.status = ItemRequestStatus.IRS_DOCUMENT_NOT_FOUND
                return resp
            if self.behavior == "count_mismatch":
                resp.status = ItemRequestStatus.IRS_OK
                return resp

            resp.status = ItemRequestStatus.IRS_OK
            for item in command.items:
                res = ItemCreationResult()
                if self.behavior == "item_error":
                    res.status.code = ItemStatusCode.ISC_INVALID_DATA
                    res.status.error_message = "bad coordinates"
                else:
                    res.status.code = ItemStatusCode.ISC_OK
                    msg_type = Track if "Track" in item.type_url else None
                    if msg_type is not None:
                        obj = msg_type()
                        item.Unpack(obj)
                        obj.id.value = self.assigned_id
                        res.item.Pack(obj)
                    else:
                        res.item.CopyFrom(item)
                resp.created_items.append(res)
            return resp

        if isinstance(command, UpdateItems):
            resp = UpdateItemsResponse()
            if self.behavior == "update_rejected":
                resp.status = ItemRequestStatus.IRS_DOCUMENT_NOT_FOUND
                return resp

            resp.status = ItemRequestStatus.IRS_OK
            for item in command.items:
                res = ItemUpdateResult()
                if self.behavior == "update_item_error":
                    res.status.code = ItemStatusCode.ISC_NONEXISTENT
                    res.status.error_message = "item not found on board"
                else:
                    res.status.code = ItemStatusCode.ISC_OK
                    res.item.CopyFrom(item)
                resp.updated_items.append(res)
            return resp

        if isinstance(command, DeleteItems):
            resp = DeleteItemsResponse()
            if self.behavior == "delete_rejected":
                resp.status = ItemRequestStatus.IRS_DOCUMENT_NOT_FOUND
                return resp

            resp.status = ItemRequestStatus.IRS_OK
            for kiid in command.item_ids:
                res = ItemDeletionResult()
                res.id.value = kiid.value
                if self.behavior == "delete_nonexistent":
                    res.status = ItemDeletionStatus.IDS_NONEXISTENT
                elif self.behavior == "delete_missing_record":
                    continue
                else:
                    res.status = ItemDeletionStatus.IDS_OK
                resp.deleted_items.append(res)
            return resp

        if isinstance(command, RefillZones):
            return Empty()

        if isinstance(command, GetBoardEnabledLayers):
            resp = BoardEnabledLayersResponse()
def test_begin_and_end_commit():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    commit_id = begin_commit(client, doc)
    assert commit_id.value == "commit-pcb-1"
    assert client.begun == 1
    end_commit(client, commit_id, doc, "test commit", drop=False)
    assert client.committed == 1
    assert client.dropped == 0


def test_end_commit_drop():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    commit_id = begin_commit(client, doc)
    end_commit(client, commit_id, doc, "rollback", drop=True)
    assert client.committed == 0
    assert client.dropped == 1


def test_run_commit_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    result = run_commit(client, doc, "do something", lambda: 42)
    assert result == 42
    assert client.begun == 1
    assert client.committed == 1
    assert client.dropped == 0


def test_run_commit_drops_on_exception():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()

    def _failing():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_commit(client, doc, "will fail", _failing)

    assert client.begun == 1
    assert client.committed == 0
    assert client.dropped == 1


def test_add_track_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    kiid = add_track(client, doc, start=(0.0, 0.0), end=(10.0, 0.0), width_mm=0.25)
    assert kiid == "kiid-test-001"
    assert client.begun == 1
    assert client.committed == 1
    assert client.dropped == 0


def test_add_track_item_error_drops_commit():
    client = _ScriptedPCBClient("item_error")
    doc = _fake_doc()
    with pytest.raises(PCBMutationError, match="bad coordinates"):
        add_track(client, doc, start=(0.0, 0.0), end=(10.0, 0.0))
    assert client.begun == 1
    assert client.committed == 0
    assert client.dropped == 1


def test_add_track_count_mismatch_drops_commit():
    client = _ScriptedPCBClient("count_mismatch")
    doc = _fake_doc()
    with pytest.raises(PCBMutationError, match="count mismatch"):
        add_track(client, doc, start=(0.0, 0.0), end=(10.0, 0.0))
    assert client.dropped == 1


def test_add_track_request_rejected_drops_commit():
    client = _ScriptedPCBClient("request_rejected")
    doc = _fake_doc()
    with pytest.raises(PCBMutationError, match="CreateItems rejected"):
        add_track(client, doc, start=(0.0, 0.0), end=(10.0, 0.0))
    assert client.dropped == 1


def test_add_arc_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    add_arc(client, doc, start=(0.0, 0.0), mid=(5.0, 5.0), end=(10.0, 0.0))
    assert client.committed == 1


def test_add_via_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    add_via(client, doc, position=(5.0, 5.0), size_mm=0.8, drill_mm=0.4)
    assert client.committed == 1


def test_add_copper_zone_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    polygon = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    add_copper_zone(client, doc, polygon=polygon, net_name="GND")
    assert client.committed == 1


def test_add_footprint_instance_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    add_footprint_instance(
        client, doc,
        reference="R1", value="10k", position=(1.0, 2.0),
        library_id="Resistor_SMD", footprint_name="R_0805_2012Metric",
    )
    assert client.committed == 1


def test_update_item_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    track = Track()
    track.id.value = "track-42"
    updated = update_item(client, doc, track)
    assert updated.id.value == "track-42"


def test_update_item_in_commit_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    track = Track()
    track.id.value = "track-42"
    updated = update_item_in_commit(client, doc, track, "move track")
    assert updated.id.value == "track-42"
    assert client.committed == 1


def test_update_item_error_drops_commit():
    client = _ScriptedPCBClient("update_item_error")
    doc = _fake_doc()
    track = Track()
    track.id.value = "track-ghost"
    with pytest.raises(PCBMutationError, match="item not found"):
        update_item_in_commit(client, doc, track, "will fail")
    assert client.dropped == 1


def test_delete_items_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    delete_items_by_id(client, doc, ["id-1", "id-2"])


def test_delete_items_in_commit_success():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    delete_items_in_commit(client, doc, ["id-1"], "delete id-1")
    assert client.committed == 1


def test_delete_nonexistent_drops_commit():
    client = _ScriptedPCBClient("delete_nonexistent")
    doc = _fake_doc()
    with pytest.raises(PCBMutationError, match="deletion status"):
        delete_items_in_commit(client, doc, ["id-ghost"], "will fail")
    assert client.dropped == 1


def test_delete_missing_record_drops_commit():
    client = _ScriptedPCBClient("delete_missing_record")
    doc = _fake_doc()
    with pytest.raises(PCBMutationError, match="no deletion record"):
        delete_items_in_commit(client, doc, ["id-vanished"], "will fail")
    assert client.dropped == 1


def test_refill_zones_blocking():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    refill_zones(client, doc, zone_ids=["z1", "z2"], block=True, max_poll_seconds=1.0, poll_interval_seconds=0.01)
    assert isinstance(client.commands_received[0], RefillZones)
    rz_cmd = client.commands_received[0]
    assert len(rz_cmd.zones) == 2
    assert rz_cmd.zones[0].value == "z1"
    assert rz_cmd.zones[1].value == "z2"


def test_refill_zones_nonblocking():
    client = _ScriptedPCBClient("ok")
    doc = _fake_doc()
    refill_zones(client, doc, block=False)
    assert len(client.commands_received) == 1
    assert isinstance(client.commands_received[0], RefillZones)

