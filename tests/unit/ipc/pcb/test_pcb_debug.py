"""Unit tests for PCB geometry debug probes."""

from kicad_agent.ipc.messages import DocumentType
from kicad_agent.ipc.pcb import debug_pcb
from kicad_agent.ipc.pcb.debug_pcb import (
    PCBDebugError,
    _base_proto,
    _board_proto,
    _editor_proto,
)

DocumentSpecifier = _base_proto("DocumentSpecifier")


def _doc():
    doc = DocumentSpecifier()
    doc.type = DocumentType.DOCTYPE_PCB
    doc.board_filename = "dbg.kicad_pcb"
    return doc


class _FakeGeoClient:
    def __init__(self):
        self.hit_pos = None
        self.bbox_mode = None

    def send(self, command, response_type):
        name = type(command).__name__
        if name == "HitTest":
            HitTestResponse = _editor_proto("HitTestResponse")
            resp = HitTestResponse()
            self.hit_pos = (command.position.x_nm, command.position.y_nm)
            resp.result = 2
            return resp
        if name == "GetBoundingBox":
            GetBoundingBoxResponse = _editor_proto("GetBoundingBoxResponse")
            KIID = _base_proto("KIID")
            Box2 = _base_proto("Box2")
            Vector2 = _base_proto("Vector2")
            self.bbox_mode = command.mode
            resp = GetBoundingBoxResponse()
            for kid in command.items:
                out = KIID()
                out.value = kid.value
                resp.items.append(out)
                box = Box2()
                pos = Vector2()
                pos.x_nm = 10_000_000
                pos.y_nm = 20_000_000
                size = Vector2()
                size.x_nm = 5_000_000
                size.y_nm = 1_000_000
                box.position.CopyFrom(pos)
                box.size.CopyFrom(size)
                resp.boxes.append(box)
            return resp
        raise AssertionError(f"unexpected: {name}")


def test_hit_test_reports_hit_and_nm():
    client = _FakeGeoClient()
    out = debug_pcb.hit_test(client, _doc(), "k1", 1.5, 2.5)
    assert out == {"hit": True, "raw": 2}
    assert client.hit_pos == (1_500_000, 2_500_000)


def test_get_bboxes_mm_conversion_and_mode():
    client = _FakeGeoClient()
    out = debug_pcb.get_bboxes(client, _doc(), ["a", "b"], mode=2)
    assert client.bbox_mode == 2
    assert [b["kiid"] for b in out] == ["a", "b"]
    assert out[0]["x_mm"] == 10.0
    assert out[0]["w_mm"] == 5.0


def test_get_bboxes_empty_rejected():
    client = _FakeGeoClient()
    try:
        debug_pcb.get_bboxes(client, _doc(), [])
    except PCBDebugError as e:
        assert "at least one KIID" in str(e)
    else:
        raise AssertionError("expected PCBDebugError")


def test_selection_and_save_selection():
    class _FakeSelClient:
        def __init__(self):
            self.sel_types = None

        def send(self, command, response_type):
            name = type(command).__name__
            if name == "GetSelection":
                SelectionResponse = _editor_proto("SelectionResponse")
                self.sel_types = list(command.types)
                return SelectionResponse()
            if name == "SaveSelectionToString":
                SavedSelectionResponse = _editor_proto(
                    "SavedSelectionResponse")
                resp = SavedSelectionResponse()
                kid = _base_proto("KIID")()
                kid.value = "sel-1"
                resp.ids.append(kid)
                resp.contents = "(footprint sel)"
                return resp
            raise AssertionError(f"unexpected: {name}")

    client = _FakeSelClient()
    assert debug_pcb.get_selection(client, _doc(), item_types=[1]) == []
    assert client.sel_types == [1]
    saved = debug_pcb.save_selection(client)
    assert saved == {"ids": ["sel-1"], "contents": "(footprint sel)"}


class _FakeRulesClient:
    def __init__(self, by_class=None):
        self.by_class = None
        self.pad_layer = None
        self.padstack_layers = None

    def send(self, command, response_type):
        name = type(command).__name__
        if name == "GetOpenDocuments":
            GetOpenDocumentsResponse = _editor_proto(
                "GetOpenDocumentsResponse")
            resp = GetOpenDocumentsResponse()
            doc = resp.documents.add()
            doc.type = DocumentType.DOCTYPE_PCB
            doc.board_filename = "dbg.kicad_pcb"
            return resp
        if name == "GetBoardDesignRules":
            BoardDesignRulesResponse = _board_proto(
                "BoardDesignRulesResponse")
            resp = BoardDesignRulesResponse()
            resp.custom_rules_status = 2
            return resp
        if name == "GetCustomDesignRules":
            CustomRulesResponse = _board_proto("CustomRulesResponse")
            resp = CustomRulesResponse()
            resp.status = 3
            resp.error_text = "line 1: bad rule"
            return resp
        if name == "GetNets":
            from kicad_agent.ipc.pcb.messages_pcb import get_board_type as _bt
            NetsResponse = _board_proto("NetsResponse")
            Net = _bt("Net")
            NetCode = _bt("NetCode")
            resp = NetsResponse()
            net = Net()
            net.name = "GND"
            code = NetCode()
            code.value = 1
            net.code.CopyFrom(code)
            resp.nets.append(net)
            return resp
        if name == "GetNetClassForNets":
            NetClassForNetsResponse = _board_proto(
                "NetClassForNetsResponse")
            return NetClassForNetsResponse()
        if name == "GetItemsByNetClass":
            GetItemsResponse = _editor_proto("GetItemsResponse")
            self.by_class = list(command.net_classes)
            resp = GetItemsResponse()
            from kicad_agent.ipc.messages import ItemRequestStatus
            resp.status = ItemRequestStatus.IRS_OK
            return resp
        if name == "GetPadShapeAsPolygon":
            PadShapeAsPolygonResponse = _board_proto(
                "PadShapeAsPolygonResponse")
            KIID = _base_proto("KIID")
            self.pad_layer = command.layer
            resp = PadShapeAsPolygonResponse()
            for pad in command.pads:
                out = KIID()
                out.value = pad.value
                resp.pads.append(out)
                resp.polygons.add()
            return resp
        if name == "CheckPadstackPresenceOnLayers":
            PadstackPresenceResponse = _board_proto(
                "PadstackPresenceResponse")
            self.padstack_layers = list(command.layers)
            resp = PadstackPresenceResponse()
            entry = resp.entries.add()
            entry.item.value = "via-1"
            entry.layer = command.layers[0] if command.layers else 0
            entry.presence = 1
            return resp
        if name == "GetBoardEditorAppearanceSettings":
            BoardEditorAppearanceSettings = _board_proto(
                "BoardEditorAppearanceSettings")
            resp = BoardEditorAppearanceSettings()
            resp.inactive_layer_display = 2
            return resp
        raise AssertionError(f"unexpected: {name}")


def test_rules_probes():
    client = _FakeRulesClient()
    assert debug_pcb.get_design_rules(
        client, _doc())["custom_rules_status"] == 2
    custom = debug_pcb.get_custom_rules(client, _doc())
    assert custom["status"] == 3
    assert custom["error_text"] == "line 1: bad rule"


def test_netclass_probes():
    client = _FakeRulesClient()
    assert debug_pcb.get_netclass_for_nets(client, _doc(), ["GND"]) == {}
    assert debug_pcb.get_items_by_netclass(
        client, _doc(), ["Default"]) == []
    assert client.by_class == ["Default"]


def test_netclass_unknown_net_fails():
    client = _FakeRulesClient()
    try:
        debug_pcb.get_netclass_for_nets(client, _doc(), ["NOPE"])
    except PCBDebugError as e:
        assert "not found" in str(e)
    else:
        raise AssertionError("expected PCBDebugError")


def test_pad_probes():
    client = _FakeRulesClient()
    polys = debug_pcb.get_pad_polygon(client, _doc(), ["p1"], layer=3)
    assert len(polys) == 1 and polys[0]["pad"] == "p1"
    assert client.pad_layer == 3
    entries = debug_pcb.check_padstack(client, _doc(), ["via-1"], [3])
    assert entries[0]["presence"] == 1
    assert client.padstack_layers == [3]


def test_appearance():
    client = _FakeRulesClient()
    assert debug_pcb.get_appearance(client)["inactive_layer_display"] == 2

