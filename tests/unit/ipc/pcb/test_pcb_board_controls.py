"""Unit tests for Group A board controls (reads + origin/layer writes).

Covers snapshot.get_items_by_net, snapshot.get_connected_items,
snapshot.get_visible_layers, snapshot.get_active_layer and
mutations.set_board_origin / set_visible_layers / set_active_layer.
"""

from typing import List

from google.protobuf.empty_pb2 import Empty
import pytest

from kicad_agent.ipc.messages import (
    CommitAction,
    DocumentType,
    ItemRequestStatus,
    get_base_type_protos,
)
from kicad_agent.ipc.pcb.messages_pcb import (
    get_base_type,
    get_board_command,
    get_board_type,
    get_commit_protos,
    get_item_mutation,
)
from kicad_agent.ipc.pcb.mutations_pcb import (
    PCBMutationError,
    set_active_layer,
    set_board_origin,
    set_visible_layers,
)
from kicad_agent.ipc.pcb.snapshot import PCBSnapshotReader

BeginCommit, BeginCommitResponse, EndCommit, EndCommitResponse = get_commit_protos()
GetNets = get_board_command("GetNets")
NetsResponse = get_board_command("NetsResponse")
GetItemsByNet = get_board_command("GetItemsByNet")
GetConnectedItems = get_board_command("GetConnectedItems")
GetItemsResponse = get_item_mutation("GetItemsResponse")
GetVisibleLayers = get_board_command("GetVisibleLayers")
BoardLayers = get_board_command("BoardLayers")
SetVisibleLayers = get_board_command("SetVisibleLayers")
GetActiveLayer = get_board_command("GetActiveLayer")
SetActiveLayer = get_board_command("SetActiveLayer")
BoardLayerResponse = get_board_command("BoardLayerResponse")
SetBoardOrigin = get_board_command("SetBoardOrigin")
Track = get_board_type("Track")
DocumentSpecifier = get_base_type("DocumentSpecifier")


def _fake_doc():
    doc = DocumentSpecifier()
    doc.type = DocumentType.DOCTYPE_PCB
    doc.board_filename = "test_board.kicad_pcb"
    return doc


class _ScriptedBoardClient:
    """Scripts board-query responses; records commits and last payloads."""

    def __init__(self, by_net_behavior="ok"):
        self.by_net_behavior = by_net_behavior
        self.is_connected = True
        self.begun = 0
        self.committed = 0
        self.dropped = 0
        self.last_by_net_types = None
        self.last_by_net_codes = None
        self.last_connected_ids = None
        self.last_connected_types = None
        self.last_visible_layers = None
        self.last_active_layer = None
        self.last_origin = None
        self.last_origin_kind = None
        self.assigned_id = "kiid-test-001"

    def _pcb_doc_response(self):
        from kicad_agent.ipc.messages import get_editor_command_protos
        GetOpenDocumentsResponse = get_editor_command_protos()[3]
        resp = GetOpenDocumentsResponse()
        doc = resp.documents.add()
        doc.type = DocumentType.DOCTYPE_PCB
        doc.board_filename = "test_board.kicad_pcb"
        return resp

    def send(self, command, response_type):
        name = type(command).__name__
        if name == "GetOpenDocuments":
            return self._pcb_doc_response()
        if name == "BeginCommit":
            self.begun += 1
            resp = BeginCommitResponse()
            resp.id.value = "commit-board-1"
            return resp
        if name == "EndCommit":
            if command.action == CommitAction.CMA_DROP:
                self.dropped += 1
            else:
                self.committed += 1
            return EndCommitResponse()

        if isinstance(command, GetNets):
            resp = NetsResponse()
            gnd = resp.nets.add()
            gnd.name = "GND"
            gnd.code.value = 1
            vcc = resp.nets.add()
            vcc.name = "VCC"
            vcc.code.value = 2
            return resp

        if isinstance(command, GetItemsByNet):
            if self.by_net_behavior == "rejected":
                resp = GetItemsResponse()
                resp.status = ItemRequestStatus.IRS_DOCUMENT_NOT_FOUND
                return resp
            self.last_by_net_types = list(command.types)
            self.last_by_net_codes = sorted(n.code.value for n in command.nets)
            resp = GetItemsResponse()
            resp.status = ItemRequestStatus.IRS_OK
            track = Track()
            track.id.value = "track-on-gnd"
            track.net.name = "GND"
            track.net.code.value = 1
            packed = resp.items.add()
            packed.Pack(track)
            return resp

        if isinstance(command, GetConnectedItems):
            self.last_connected_ids = sorted(k.value for k in command.items)
            self.last_connected_types = list(command.types)
            resp = GetItemsResponse()
            resp.status = ItemRequestStatus.IRS_OK
            return resp

        if isinstance(command, GetVisibleLayers):
            resp = BoardLayers()
            resp.layers.extend([3, 34])
            return resp

        if isinstance(command, SetVisibleLayers):
            self.last_visible_layers = list(command.layers)
            return Empty()

        if isinstance(command, GetActiveLayer):
            resp = BoardLayerResponse()
            resp.layer = 3
            return resp

        if isinstance(command, SetActiveLayer):
            self.last_active_layer = command.layer
            return Empty()

        if isinstance(command, SetBoardOrigin):
            self.last_origin_kind = command.type
            self.last_origin = (
                command.origin.x_nm / 1_000_000.0,
                command.origin.y_nm / 1_000_000.0,
            )
            return Empty()

        raise AssertionError(f"unexpected command: {type(command).__name__}")


def test_get_items_by_net_resolves_names_and_types():
    client = _ScriptedBoardClient()
    reader = PCBSnapshotReader(client)

    items = reader.get_items_by_net(["GND"], item_types=[11])
    assert len(items) == 1
    assert client.last_by_net_codes == [1]
    assert client.last_by_net_types == [11]

    track = Track()
    items[0].Unpack(track)
    assert track.id.value == "track-on-gnd"


def test_get_items_by_net_unknown_name_fails_cleanly():
    client = _ScriptedBoardClient()
    reader = PCBSnapshotReader(client)

    with pytest.raises(RuntimeError, match="Net 'NOPE' not found on board"):
        reader.get_items_by_net(["NOPE"])


def test_get_items_by_net_rejected():
    client = _ScriptedBoardClient(by_net_behavior="rejected")
    reader = PCBSnapshotReader(client)

    with pytest.raises(RuntimeError, match="GetItemsByNet rejected"):
        reader.get_items_by_net(["GND"])


def test_get_connected_items_sends_ids_and_types():
    client = _ScriptedBoardClient()
    reader = PCBSnapshotReader(client)

    items = reader.get_connected_items(["a1", "b2"], item_types=[11, 12])
    assert items == []
    assert client.last_connected_ids == ["a1", "b2"]
    assert client.last_connected_types == [11, 12]


def test_get_visible_layers():
    client = _ScriptedBoardClient()
    reader = PCBSnapshotReader(client)

    assert reader.get_visible_layers() == [3, 34]


def test_get_active_layer():
    client = _ScriptedBoardClient()
    reader = PCBSnapshotReader(client)

    assert reader.get_active_layer() == 3


def test_set_visible_layers():
    client = _ScriptedBoardClient()
    doc = _fake_doc()

    set_visible_layers(client, doc, [3, 34])
    assert client.last_visible_layers == [3, 34]


def test_set_visible_layers_empty_refused():
    client = _ScriptedBoardClient()
    doc = _fake_doc()

    with pytest.raises(PCBMutationError, match="at least one layer"):
        set_visible_layers(client, doc, [])


def test_set_active_layer():
    client = _ScriptedBoardClient()
    doc = _fake_doc()

    assert set_active_layer(client, doc, 34) == 34
    assert client.last_active_layer == 34


def test_set_board_origin_grid_in_commit():
    client = _ScriptedBoardClient()
    doc = _fake_doc()

    set_board_origin(client, doc, origin_mm=(10.0, 20.0), origin_kind="grid")
    assert client.begun == 1
    assert client.committed == 1
    assert client.dropped == 0
    assert client.last_origin == (10.0, 20.0)
    # BOT_GRID == 1 per board_commands.proto
    assert client.last_origin_kind == 1


def test_set_board_origin_bad_kind_fails_before_commit():
    client = _ScriptedBoardClient()
    doc = _fake_doc()

    with pytest.raises(PCBMutationError, match="origin_kind must be"):
        set_board_origin(client, doc, origin_mm=(0.0, 0.0), origin_kind="moon")
    assert client.begun == 0

