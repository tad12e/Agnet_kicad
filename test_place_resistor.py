"""Test placing symbol using exact working test_kipy.py document pattern."""
import os
import sys
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


def main():
    print("Step 1: Connecting to KiCad...")
    client = KiCadIPCClient(timeout_ms=60000)
    client.connect()
    print("[OK] Connected!")

    print("Step 2: Getting open documents...")
    _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
    cmd = GetOpenDocuments()
    cmd.type = DocumentType.DOCTYPE_SCHEMATIC
    resp = client.send(cmd, GetOpenDocumentsResponse)

    if not resp.documents:
        print("[!] No schematic documents open in KiCad!")
        return

    doc = resp.documents[0]
    print(f"[OK] Document: {doc.board_filename}")

    print("Step 3: Building Resistor R1...")
    (SchematicSymbolInstance,) = get_schematic_type_protos()

    pos_x_nm = 120_000_000  # 120mm
    pos_y_nm = 80_000_000   # 80mm

    sym = SchematicSymbolInstance()
    sym.id.value = str(uuid.uuid4())
    sym.position.x_nm = pos_x_nm
    sym.position.y_nm = pos_y_nm
    import re
    sheet_uuid = "2fb8f65d-99c3-4933-ad30-63700ce7c984" # Default fallback
    try:
        sch_file = os.path.join(r"C:\Users\hp\ECE\test\Agent", doc.board_filename or "Agent.kicad_sch")
        if os.path.exists(sch_file):
            with open(sch_file, "r", encoding="utf-8", errors="ignore") as f:
                m = re.search(r'\(uuid\s+"?([0-9a-fA-F\-]{36})"?\)', f.read(4096))
                if m:
                    sheet_uuid = m.group(1)
    except Exception:
        pass
    
    sym.path.path.add().value = sheet_uuid

    sym.transform.orientation = 1
    sym.unit.unit = 1

    # Definition Metadata
    sym.definition.id.library_nickname = "Device"
    sym.definition.id.entry_name = "R"
    sym.definition.unit_count = 1
    sym.definition.body_style_count = 1

    # Definition Fields
    sym.definition.reference_field.id.value = str(uuid.uuid4())
    sym.definition.reference_field.name = "Reference"
    sym.definition.reference_field.text.text = "R"
    sym.definition.reference_field.text.position.x_nm = 0
    sym.definition.reference_field.text.position.y_nm = -2_540_000
    sym.definition.reference_field.visible = True

    sym.definition.value_field.id.value = str(uuid.uuid4())
    sym.definition.value_field.name = "Value"
    sym.definition.value_field.text.text = "R"
    sym.definition.value_field.text.position.x_nm = 0
    sym.definition.value_field.text.position.y_nm = 2_540_000
    sym.definition.value_field.visible = True

    sym.definition.footprint_field.id.value = str(uuid.uuid4())
    sym.definition.footprint_field.name = "Footprint"
    sym.definition.footprint_field.text.text = ""
    sym.definition.footprint_field.visible = False

    sym.definition.datasheet_field.id.value = str(uuid.uuid4())
    sym.definition.datasheet_field.name = "Datasheet"
    sym.definition.datasheet_field.text.text = "~"
    sym.definition.datasheet_field.visible = False

    sym.definition.description_field.id.value = str(uuid.uuid4())
    sym.definition.description_field.name = "Description"
    sym.definition.description_field.text.text = "Resistor"
    sym.definition.description_field.visible = False

    # Instance Fields
    sym.reference_field.id.value = str(uuid.uuid4())
    sym.reference_field.name = "Reference"
    sym.reference_field.text.text = "R1"
    sym.reference_field.text.position.x_nm = pos_x_nm
    sym.reference_field.text.position.y_nm = pos_y_nm - 2_540_000
    sym.reference_field.visible = True

    sym.value_field.id.value = str(uuid.uuid4())
    sym.value_field.name = "Value"
    sym.value_field.text.text = "10k"
    sym.value_field.text.position.x_nm = pos_x_nm
    sym.value_field.text.position.y_nm = pos_y_nm + 2_540_000
    sym.value_field.visible = True

    sym.footprint_field.id.value = str(uuid.uuid4())
    sym.footprint_field.name = "Footprint"
    sym.footprint_field.text.text = ""
    sym.footprint_field.visible = False

    sym.datasheet_field.id.value = str(uuid.uuid4())
    sym.datasheet_field.name = "Datasheet"
    sym.datasheet_field.text.text = "~"
    sym.datasheet_field.visible = False

    sym.description_field.id.value = str(uuid.uuid4())
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

    # Step 4: Pack and send CreateItems
    any_item = Any()
    any_item.Pack(sym)

    CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()
    cmd_create = CreateItems()
    cmd_create.header.document.CopyFrom(doc)
    cmd_create.items.append(any_item)

    print("Step 4: Sending CreateItems to KiCad...")
    try:
        resp = client.send(cmd_create, CreateItemsResponse)
        print(f"\n[SUCCESS] Created {len(resp.created_items)} items on the schematic!")
        for item in resp.created_items:
            print(f"  Status: {item.status}")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
