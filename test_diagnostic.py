"""Diagnostic: dump exactly what KiCad returns for document, then attempt placement."""
import os
import sys
import re
import uuid
import traceback

PROTO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "proto"))
if PROTO_DIR not in sys.path:
    sys.path.insert(0, PROTO_DIR)
sys.path.insert(0, ".")

from google.protobuf.any_pb2 import Any
from google.protobuf import text_format

from kicad_api.ipc.client import KiCadIPCClient
from kicad_api.ipc.messages import (
    get_editor_command_protos,
    get_schematic_command_protos,
    DocumentType,
    get_schematic_type_protos,
)
from proto.schematic.schematic_types_pb2 import (
    SchematicPin,
    SchematicPinOrientation,
    SchematicPinShape,
)
from proto.common.types.base_types_pb2 import ElectricalPinType


def main():
    print("=" * 60)
    print("KiCad IPC Diagnostic - Symbol Placement")
    print("=" * 60)

    # Step 1: Connect
    print("\n[1] Connecting to KiCad IPC socket...")
    client = KiCadIPCClient(timeout_ms=15000)
    client.connect()
    print("    OK: Connected!")

    # Step 2: Get open documents - dump full proto
    print("\n[2] GetOpenDocuments...")
    _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
    cmd = GetOpenDocuments()
    cmd.type = DocumentType.DOCTYPE_SCHEMATIC
    resp = client.send(cmd, GetOpenDocumentsResponse)

    if not resp.documents:
        print("    FAIL: No schematic documents open!")
        return

    doc = resp.documents[0]
    print("    Full DocumentSpecifier proto:")
    print("    " + text_format.MessageToString(doc, indent=4).replace("\n", "\n    "))

    print(f"\n    board_filename = '{doc.board_filename}'")
    print(f"    project.name  = '{doc.project.name}'")
    print(f"    project.path  = '{doc.project.path}'")
    print(f"    type          = {doc.type}")

    # Step 3: Get schematic hierarchy
    print("\n[3] GetSchematicHierarchy...")
    try:
        GetSchematicHierarchy, SchematicHierarchyResponse, _, _ = get_schematic_command_protos()
        cmd_hier = GetSchematicHierarchy()
        cmd_hier.document.CopyFrom(doc)
        resp_hier = client.send(cmd_hier, SchematicHierarchyResponse)
        print("    Full SchematicHierarchyResponse:")
        print("    " + text_format.MessageToString(resp_hier, indent=4).replace("\n", "\n    "))
        
        if resp_hier.top_level_sheets:
            root = resp_hier.top_level_sheets[0]
            sheet_path_uuids = [uid.value for uid in root.path.path]
            print(f"\n    Root sheet path UUIDs: {sheet_path_uuids}")
        else:
            print("    No top_level_sheets returned")
            sheet_path_uuids = []
    except Exception as e:
        print(f"    ERROR: {e}")
        traceback.print_exc()
        sheet_path_uuids = []

    # Step 3b: Also try reading UUID from file
    print("\n[3b] Reading root sheet UUID from .kicad_sch file...")
    file_uuid = None
    for search_dir in [r"C:\Users\hp\ECE\test\Agent", os.getcwd()]:
        sch_file = os.path.join(search_dir, doc.board_filename or "Agent.kicad_sch")
        if os.path.exists(sch_file):
            with open(sch_file, "r", encoding="utf-8", errors="ignore") as f:
                m = re.search(r'\(uuid\s+"?([0-9a-fA-F\-]{36})"?\)', f.read(4096))
                if m:
                    file_uuid = m.group(1)
                    print(f"    Found in {sch_file}: {file_uuid}")
                    break
    if not file_uuid:
        print("    Could not find UUID in schematic file")

    # Step 4: Build and send a simple Junction first (known working)
    print("\n[4] Testing Junction placement (known working type)...")
    from proto.schematic.schematic_types_pb2 import Junction
    
    junction = Junction()
    junction.id.value = str(uuid.uuid4())
    junction.position.x_nm = 100_000_000
    junction.position.y_nm = 100_000_000

    any_junc = Any()
    any_junc.Pack(junction)

    CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()
    cmd_junc = CreateItems()
    cmd_junc.header.document.CopyFrom(doc)
    cmd_junc.items.append(any_junc)

    try:
        resp_junc = client.send(cmd_junc, CreateItemsResponse)
        print(f"    OK: Created {len(resp_junc.created_items)} junction(s)")
        for item in resp_junc.created_items:
            print(f"    Item status: {text_format.MessageToString(item.status).strip()}")
    except Exception as e:
        print(f"    ERROR: {type(e).__name__}: {e}")
        print("    Cannot even place a junction - stopping here.")
        return

    # Step 5: Now try symbol
    print("\n[5] Building SchematicSymbolInstance for R1...")
    (SchematicSymbolInstance,) = get_schematic_type_protos()

    sym = SchematicSymbolInstance()
    sym.id.value = str(uuid.uuid4())
    sym.position.x_nm = 120_000_000
    sym.position.y_nm = 80_000_000

    # Set sheet path - use hierarchy response if available, else file UUID
    if sheet_path_uuids:
        for uid in sheet_path_uuids:
            sym.path.path.add().value = uid
        print(f"    Using hierarchy path: {sheet_path_uuids}")
    elif file_uuid:
        sym.path.path.add().value = file_uuid
        print(f"    Using file UUID: {file_uuid}")
    else:
        print("    WARNING: No sheet path available!")

    sym.transform.orientation = 1  # SSO_0
    sym.unit.unit = 1

    # Definition
    sym.definition.id.library_nickname = "Device"
    sym.definition.id.entry_name = "R"
    sym.definition.unit_count = 1
    sym.definition.body_style_count = 1

    # Definition Fields (SchematicField has: name, text, visible, show_name, allow_auto_place, is_private)
    sym.definition.reference_field.name = "Reference"
    sym.definition.reference_field.text.text = "R"
    sym.definition.reference_field.visible = True

    sym.definition.value_field.name = "Value"
    sym.definition.value_field.text.text = "R"
    sym.definition.value_field.visible = True

    sym.definition.footprint_field.name = "Footprint"
    sym.definition.footprint_field.text.text = ""
    sym.definition.footprint_field.visible = False

    sym.definition.datasheet_field.name = "Datasheet"
    sym.definition.datasheet_field.text.text = "~"
    sym.definition.datasheet_field.visible = False

    sym.definition.description_field.name = "Description"
    sym.definition.description_field.text.text = "Resistor"
    sym.definition.description_field.visible = False

    # Instance Fields
    sym.reference_field.name = "Reference"
    sym.reference_field.text.text = "R1"
    sym.reference_field.text.position.x_nm = 120_000_000
    sym.reference_field.text.position.y_nm = 77_460_000
    sym.reference_field.visible = True

    sym.value_field.name = "Value"
    sym.value_field.text.text = "10k"
    sym.value_field.text.position.x_nm = 120_000_000
    sym.value_field.text.position.y_nm = 82_540_000
    sym.value_field.visible = True

    sym.footprint_field.name = "Footprint"
    sym.footprint_field.text.text = ""
    sym.footprint_field.visible = False

    sym.datasheet_field.name = "Datasheet"
    sym.datasheet_field.text.text = "~"
    sym.datasheet_field.visible = False

    sym.description_field.name = "Description"
    sym.description_field.text.text = "Resistor"
    sym.description_field.visible = False

    # Pins in definition
    pin1 = SchematicPin()
    pin1.id.value = str(uuid.uuid4())
    pin1.name = "~"
    pin1.number = "1"
    pin1.position.x_nm = 0
    pin1.position.y_nm = -2_540_000
    pin1.length.value_nm = 2_540_000
    pin1.orientation = SchematicPinOrientation.SPO_DOWN
    pin1.electrical_type = ElectricalPinType.EPT_PASSIVE
    pin1.shape = SchematicPinShape.SPS_LINE
    pin1.visible = True

    any_pin1 = Any()
    any_pin1.Pack(pin1)
    c1 = sym.definition.items.add()
    c1.item.CopyFrom(any_pin1)
    c1.unit.unit = 1
    c1.body_style.style = 1

    pin2 = SchematicPin()
    pin2.id.value = str(uuid.uuid4())
    pin2.name = "~"
    pin2.number = "2"
    pin2.position.x_nm = 0
    pin2.position.y_nm = 2_540_000
    pin2.length.value_nm = 2_540_000
    pin2.orientation = SchematicPinOrientation.SPO_UP
    pin2.electrical_type = ElectricalPinType.EPT_PASSIVE
    pin2.shape = SchematicPinShape.SPS_LINE
    pin2.visible = True

    any_pin2 = Any()
    any_pin2.Pack(pin2)
    c2 = sym.definition.items.add()
    c2.item.CopyFrom(any_pin2)
    c2.unit.unit = 1
    c2.body_style.style = 1

    # Dump the full symbol proto
    sym_text = text_format.MessageToString(sym, indent=2)
    print(f"    Symbol proto ({len(sym_text)} chars):")
    # Print first 80 lines
    for i, line in enumerate(sym_text.split("\n")[:80]):
        print(f"      {line}")
    if len(sym_text.split("\n")) > 80:
        print(f"      ... ({len(sym_text.split(chr(10)))} total lines)")

    # Pack into Any
    any_sym = Any()
    any_sym.Pack(sym)
    print(f"\n    Any type_url: {any_sym.type_url}")

    # Send CreateItems
    print("\n[6] Sending CreateItems with symbol...")
    cmd_create = CreateItems()
    cmd_create.header.document.CopyFrom(doc)
    cmd_create.items.append(any_sym)

    print("    CreateItems header:")
    print("    " + text_format.MessageToString(cmd_create.header, indent=4).replace("\n", "\n    "))

    try:
        resp_create = client.send(cmd_create, CreateItemsResponse)
        print(f"\n    SUCCESS! Created {len(resp_create.created_items)} item(s)")
        for item in resp_create.created_items:
            print(f"    Status: {text_format.MessageToString(item.status).strip()}")
    except Exception as e:
        print(f"\n    ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
