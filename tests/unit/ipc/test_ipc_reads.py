"""Unit tests for IPCBackend schematic reads (Part 5).

GetItems hierarchy/netlist responses are scripted; summaries must match the
packed payloads exactly, unknowns counted, failures explicit.
"""

import pytest

from google.protobuf.any_pb2 import Any as ProtoAny

from proto.schematic.schematic_types_pb2 import (
    Junction,
    LocalLabel,
    SchematicLine,
    SchematicSymbolInstance,
)

from kicad_agent.backends.ipc import IPCBackend, summarize_schematic_item
from kicad_agent.core.errors import AgentError
from kicad_agent.ipc.messages import DocumentType, get_editor_command_protos

GetOpenDocumentsResponse = get_editor_command_protos()[3]


def _pack(msg):
    any_msg = ProtoAny()
    any_msg.Pack(msg)
    return any_msg


def _symbol():
    sym = SchematicSymbolInstance()
    sym.id.value = "sym-1"
    sym.position.x_nm = 100_000_000
    sym.position.y_nm = 200_000_000
    sym.definition.id.library_nickname = "Device"
    sym.definition.id.entry_name = "R"
    sym.reference_field.text.text = "R1"
    sym.value_field.text.text = "10k"
    return sym


def _wire():
    line = SchematicLine()
    line.id.value = "wire-1"
    line.start.x_nm = 0
    line.start.y_nm = 0
    line.end.x_nm = 10_000_000
    line.end.y_nm = 0
    line.type = 1  # SLT_WIRE
    return line


def _junction():
    junc = Junction()
    junc.id.value = "j1"
    junc.position.x_nm = 5_000_000
    junc.position.y_nm = 5_000_000
    return junc


def _label():
    lab = LocalLabel()
    lab.id.value = "l1"
    lab.position.x_nm = 1_000_000
    lab.position.y_nm = 2_000_000
    lab.text.text = "NET_A"
    return lab


class _ReadClient:
    """Scripts GetItems/Hierarchy/Netlist responses; records requests."""

    def __init__(self, netlist_error=None, items_status=1):
        self.netlist_error = netlist_error
        self.items_status = items_status
        self.is_connected = True
        self.requested_types = None

    def send(self, command, response_type):
        name = type(command).__name__
        if name == "GetOpenDocuments":
            resp = GetOpenDocumentsResponse()
            doc = resp.documents.add()
            doc.type = DocumentType.DOCTYPE_SCHEMATIC
            doc.board_filename = "Read.kicad_sch"
            return resp
        if name == "GetItems":
            self.requested_types = list(command.types)
            resp = response_type()
            resp.status = self.items_status
            if self.items_status == 1:
                for msg in (_symbol(), _wire(), _junction(), _label()):
                    resp.items.append(_pack(msg))
                stray = ProtoAny()
                stray.type_url = "type.googleapis.com/kiapi.unknown.Thing"
                resp.items.append(stray)
            return resp
        if name == "GetSchematicHierarchy":
            resp = response_type()
            top = resp.top_level_sheets.add()
            top.name = "root"
            top.filename = "read.kicad_sch"
            top.page_number = "1"
            child = top.children.add()
            child.name = "sub"
            child.filename = "sub.kicad_sch"
            child.page_number = "2"
            return resp
        if name == "GetSchematicNetlist":
            if self.netlist_error:
                raise self.netlist_error
            resp = response_type()
            net = resp.nets.add()
            net.name = "Net-(R1-Pad2)"
            return resp
        raise AssertionError(f"unexpected command {name}")


def test_summarize_each_kind():
    kind, summary = summarize_schematic_item(_pack(_symbol()))
    assert kind == "symbol"
    assert summary["reference"] == "R1"
    assert summary["value"] == "10k"
    assert summary["lib_id"] == "Device:R"
    assert summary["x_mm"] == pytest.approx(100.0)
    assert summary["y_mm"] == pytest.approx(200.0)

    kind, summary = summarize_schematic_item(_pack(_wire()))
    assert kind == "wire"
    assert summary["kind"] == "wire"
    assert summary["end_mm"][0] == pytest.approx(10.0)

    kind, summary = summarize_schematic_item(_pack(_junction()))
    assert kind == "junction"
    assert summary["x_mm"] == pytest.approx(5.0)

    kind, summary = summarize_schematic_item(_pack(_label()))
    assert kind == "label"
    assert summary["text"] == "NET_A"


def test_snapshot_lists_all_kinds_and_counts_unknowns():
    backend = IPCBackend(client=_ReadClient())
    doc = backend._get_document(DocumentType.DOCTYPE_SCHEMATIC)
    snap = backend.get_schematic_snapshot(doc)
    assert [s["reference"] for s in snap["symbols"]] == ["R1"]
    assert len(snap["wires"]) == 1
    assert len(snap["junctions"]) == 1
    assert len(snap["labels"]) == 1
    assert len(snap["unknown_items"]) == 1
    # Explicit type filter was sent (empty filter errors on KiCad < 10.0.7).
    assert backend.client.requested_types
    assert 35 in backend.client.requested_types  # KOT_SCH_SYMBOL


def test_hierarchy_and_netlist_shapes():
    backend = IPCBackend(client=_ReadClient())
    doc = backend._get_document(DocumentType.DOCTYPE_SCHEMATIC)
    sheets = backend.get_schematic_hierarchy(doc)
    assert sheets[0]["name"] == "root"
    assert sheets[0]["children"][0]["name"] == "sub"
    nets = backend.get_schematic_netlist(doc)
    assert nets == [{"name": "Net-(R1-Pad2)", "sheets": 0}]


def test_get_state_merges_and_marks_section_errors():
    from kicad_agent.ipc.exceptions import IPCRequestError
    from kicad_agent.ipc.messages import ApiStatusCode

    backend = IPCBackend(
        client=_ReadClient(
            netlist_error=IPCRequestError(
                status_code=ApiStatusCode.AS_UNIMPLEMENTED,
                error_message="not yet implemented",
            )
        )
    )
    state = backend.get_state("schematic")
    assert state["board_filename"] == "Read.kicad_sch"
    assert len(state["symbols"]) == 1
    assert state["sheets"][0]["name"] == "root"
    assert "not yet implemented" in state["nets"]["error"]


def test_get_items_rejection_raises():
    backend = IPCBackend(client=_ReadClient(items_status=3))
    doc = backend._get_document(DocumentType.DOCTYPE_SCHEMATIC)
    with pytest.raises(AgentError):
        backend.get_schematic_snapshot(doc)
