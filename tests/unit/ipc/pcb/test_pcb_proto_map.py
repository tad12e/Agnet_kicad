"""Guard tests for messages_pcb name lookups (Part 5).

Prevents positional index drift from ever silently coming back:
- Every name must resolve to the real, distinct message class
- FootprintInstance != Footprint
- DeleteItems != GetItems, UpdateItems != GetOpenDocuments
- BeginCommit / EndCommit carry no header in KiCad 10.0
- RefillZones matches {board, zones}
"""

import pytest

from kicad_agent.ipc.pcb.messages_pcb import (
    get_base_type,
    get_base_type_protos,
    get_board_command,
    get_board_command_protos,
    get_board_type,
    get_board_type_protos,
    get_commit_protos,
    get_editor_command,
    get_editor_command_protos,
    get_item_mutation,
    get_item_mutation_protos,
)


def test_board_types_resolve_distinct_classes():
    Track = get_board_type("Track")
    Arc = get_board_type("Arc")
    Via = get_board_type("Via")
    Zone = get_board_type("Zone")
    Footprint = get_board_type("Footprint")
    FootprintInstance = get_board_type("FootprintInstance")

    # The bug that made footprints silently empty:
    assert FootprintInstance is not Footprint
    assert FootprintInstance.DESCRIPTOR.name == "FootprintInstance"
    assert Footprint.DESCRIPTOR.name == "Footprint"
    assert Track.DESCRIPTOR.name == "Track"
    assert Arc.DESCRIPTOR.name == "Arc"
    assert Via.DESCRIPTOR.name == "Via"
    assert Zone.DESCRIPTOR.name == "Zone"


def test_item_mutations_never_collide_with_reads():
    GetItems = get_item_mutation("GetItems")
    UpdateItems = get_item_mutation("UpdateItems")
    DeleteItems = get_item_mutation("DeleteItems")
    GetOpenDocuments = get_editor_command("GetOpenDocuments")

    # The bugs in the old tuple slices:
    assert UpdateItems is not GetOpenDocuments
    assert DeleteItems is not GetItems
    assert UpdateItems.DESCRIPTOR.name == "UpdateItems"
    assert DeleteItems.DESCRIPTOR.name == "DeleteItems"

    mutation_six = get_item_mutation_protos()
    assert len(mutation_six) == 6
    assert [c.DESCRIPTOR.name for c in mutation_six] == [
        "GetItems",
        "GetItemsResponse",
        "UpdateItems",
        "UpdateItemsResponse",
        "DeleteItems",
        "DeleteItemsResponse",
    ]


def test_begin_and_end_commit_wire_truth():
    BeginCommit, BeginCommitResponse, EndCommit, EndCommitResponse = get_commit_protos()
    # In KiCad 10.0, BeginCommit is a bare notification and EndCommit carries
    # only id/action/message — neither has an ItemHeader / document field.
    begin_fields = [f.name for f in BeginCommit().DESCRIPTOR.fields]
    end_fields = [f.name for f in EndCommit().DESCRIPTOR.fields]

    assert "header" not in begin_fields
    assert "document" not in begin_fields
    assert "header" not in end_fields
    assert set(end_fields) == {"id", "action", "message"}


def test_refill_zones_signature():
    RefillZones = get_board_command("RefillZones")
    fields = {f.name for f in RefillZones().DESCRIPTOR.fields}
    assert fields == {"board", "zones"}


def test_unknown_proto_raises_import_error():
    with pytest.raises(ImportError, match="Unknown KiCad board type 'TotallyFakeProto'"):
        get_board_type("TotallyFakeProto")
    with pytest.raises(ImportError, match="Unknown KiCad board command 'FakeCommand'"):
        get_board_command("FakeCommand")
    with pytest.raises(ImportError, match="Unknown KiCad editor command 'FakeEditorCmd'"):
        get_editor_command("FakeEditorCmd")


def test_tuple_getters_keep_stable_positions():
    # Positional callers (snapshot.py, backends/ipc.py) rely on these indices:
    board_types = get_board_type_protos()
    assert board_types[0].DESCRIPTOR.name == "Track"
    assert board_types[1].DESCRIPTOR.name == "Arc"
    assert board_types[2].DESCRIPTOR.name == "Via"
    assert board_types[4].DESCRIPTOR.name == "Zone"
    assert board_types[6].DESCRIPTOR.name == "FootprintInstance"

    editor_cmds = get_editor_command_protos()
    assert editor_cmds[0].DESCRIPTOR.name == "CreateItems"
    assert editor_cmds[1].DESCRIPTOR.name == "CreateItemsResponse"
    assert editor_cmds[2].DESCRIPTOR.name == "GetOpenDocuments"
    assert editor_cmds[4].DESCRIPTOR.name == "GetItems"
    assert editor_cmds[6].DESCRIPTOR.name == "UpdateItems"
    assert editor_cmds[8].DESCRIPTOR.name == "DeleteItems"
    assert editor_cmds[10].DESCRIPTOR.name == "GetItemsById"
