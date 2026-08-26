"""Complete script: Place Symbol R1 on KiCad Schematic via Live IPC API."""
import os
import sys
import re
import uuid

PROTO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "proto"))
if PROTO_DIR not in sys.path:
    sys.path.insert(0, PROTO_DIR)
sys.path.insert(0, ".")

from google.protobuf.any_pb2 import Any
from kicad_api.ipc.client import KiCadIPCClient
from kicad_api.ipc.messages import (
    get_editor_command_protos,
    DocumentType,
    get_schematic_type_protos,
)
from proto.schematic.schematic_types_pb2 import (
    SchematicPin,
    SchematicSymbolChild,
    SchematicPinOrientation,
    SchematicPinShape,
)
from proto.common.types.base_types_pb2 import ElectricalPinType


def get_sheet_uuid_from_file(filename):
    """Find the root sheet UUID from the active .kicad_sch file."""
    candidate_paths = [
        os.path.join(r"C:\Users\hp\ECE\test\Agent", filename),
        os.path.join(r"C:\Users\hp\webdev2\Kicad", filename),
        filename,
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                header = f.read(4096)
                m = re.search(r'\(uuid\s+"?([0-9a-fA-F\-]{36})"?\)', header)
                if m:
                    return m.group(1)
    return "2fb8f65d-99c3-4933-ad30-63700ce7c984"


def main():
    print("Step 1: Connecting to KiCad IPC socket...")
    client = KiCadIPCClient()
    client.connect()
    print("[OK] Connected!")

    print("Step 2: Getting open schematic document...")
    _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
    cmd_doc = GetOpenDocuments()
    cmd_doc.type = DocumentType.DOCTYPE_SCHEMATIC
    resp_doc = client.send(cmd_doc, GetOpenDocumentsResponse)

    if not resp_doc.documents:
        print("[!] No schematic document open! Open Agent.kicad_sch in KiCad first.")
        return

    doc = resp_doc.documents[0]
    print(f"[OK] Found open document: '{doc.board_filename}'")

    # Resolve sheet UUID
    sheet_uuid = get_sheet_uuid_from_file(doc.board_filename)
    print(f"[OK] Using Sheet UUID: {sheet_uuid}")

    # Build Symbol R1
    print("Step 3: Building Symbol R1 message with sheet UUID and pins...")
    (SchematicSymbolInstance,) = get_schematic_type_protos()

    pos_x_nm = 120_000_000  # 120mm
    pos_y_nm = 80_000_000   # 80mm

    sym = SchematicSymbolInstance()
    sym.id.value = str(uuid.uuid4())
    sym.position.x_nm = pos_x_nm
    sym.position.y_nm = pos_y_nm

    # Set sheet path UUID
    sym.path.path.add().value = sheet_uuid

    sym.transform.orientation = 1
    sym.unit.unit = 1

    sym.definition.id.library_nickname = "Device"
    sym.definition.id.entry_name = "R"
    sym.definition.unit_count = 1
    sym.definition.body_style_count = 1

    # Definition Fields
    sym.definition.reference_field.name = "Reference"
    sym.definition.reference_field.text.text = "R"
    sym.definition.reference_field.text.position.x_nm = 0
    sym.definition.reference_field.text.position.y_nm = -2_540_000
    sym.definition.reference_field.visible = True

    sym.definition.value_field.name = "Value"
    sym.definition.value_field.text.text = "R"
    sym.definition.value_field.text.position.x_nm = 0
    sym.definition.value_field.text.position.y_nm = 2_540_000
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
    sym.reference_field.text.position.x_nm = pos_x_nm
    sym.reference_field.text.position.y_nm = pos_y_nm - 2_540_000
    sym.reference_field.visible = True

    sym.value_field.name = "Value"
    sym.value_field.text.text = "10k"
    sym.value_field.text.position.x_nm = pos_x_nm
    sym.value_field.text.position.y_nm = pos_y_nm + 2_540_000
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

    # Pin 1
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

    # Pin 2
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

    # Pack into Any
    any_sym = Any()
    any_sym.Pack(sym)

    # Set project name and path to match KiCad's open project
    doc.project.name = "Agent"
    doc.project.path = r"C:/Users/hp/ECE/test/Agent"

    CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()
    cmd_create = CreateItems()
    cmd_create.header.document.CopyFrom(doc)
    cmd_create.items.append(any_sym)

    print("Step 4: Sending CreateItems over live IPC API...")
    try:
        resp_create = client.send(cmd_create, CreateItemsResponse)
        print(f"\n[SUCCESS] Successfully placed {len(resp_create.created_items)} symbol(s) in KiCad!")
        for item in resp_create.created_items:
            print(f"  Status code: {item.status.code} (ISC_OK=1)")
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
