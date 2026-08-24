"""Test placing symbol R1 via live IPC API with pre-cached symbol definition."""
import sys
sys.path.insert(0, r"C:\Users\hp\OneDrive\Documents\KiCad\10.0\3rdparty\Python311\site-packages")
sys.path.insert(0, ".site-packages")
sys.path.insert(0, ".")

import uuid
from google.protobuf.any_pb2 import Any

from kicad_api.ipc.client import KiCadIPCClient
from kicad_api.ipc.messages import get_editor_command_protos, DocumentType, get_schematic_type_protos

def main():
    print("Step 1: Connecting to KiCad IPC...")
    client = KiCadIPCClient()
    client.connect()
    print("✓ Connected to KiCad socket!")

    # 1. Get open schematic document
    print("Step 2: Getting open schematic document...")
    _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
    cmd_doc = GetOpenDocuments()
    cmd_doc.type = DocumentType.DOCTYPE_SCHEMATIC
    resp_doc = client.send(cmd_doc, GetOpenDocumentsResponse)
    if not resp_doc.documents:
        print("⚠ No schematic document open! Open the Schematic Editor in KiCad first.")
        return

    doc = resp_doc.documents[0]
    # Set the matching project name and path
    doc.project.name = "Agent"
    doc.project.path = r"C:\Users\hp\ECE\test\Agent"

    # Set root sheet path UUID from Agent.kicad_sch
    root_sheet_uuid = "2fb8f65d-99c3-4933-ad30-63700ce7c984"
    doc.sheet_path.Clear()
    kiid_elem = doc.sheet_path.path.add()
    kiid_elem.value = root_sheet_uuid

    print(f"✓ Document Specifier Configured:")
    print(f"  project: '{doc.project.name}' @ '{doc.project.path}'")
    print(f"  sheet_path: {[k.value for k in doc.sheet_path.path]}")

    # 2. Build Symbol R1
    print("Step 3: Building Symbol R1 (10k) message...")
    (SchematicSymbolInstance,) = get_schematic_type_protos()
    CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()

    sym_proto = SchematicSymbolInstance()
    sym_proto.id.value = str(uuid.uuid4())
    sym_proto.position.x_nm = int(100.0 * 1_000_000)  # 100mm
    sym_proto.position.y_nm = int(100.0 * 1_000_000)  # 100mm

    # Set matching sheet path
    sym_proto.path.path.add().value = root_sheet_uuid

    # Reference library ID (matches the cached lib_symbols Device:R)
    sym_proto.definition.id.library_nickname = "Device"
    sym_proto.definition.id.entry_name = "R"
    sym_proto.definition.unit_count = 1
    sym_proto.transform.orientation = 1
    sym_proto.unit.unit = 1

    # Instance Fields
    sym_proto.reference_field.name = "Reference"
    sym_proto.reference_field.text.text = "R1"
    sym_proto.reference_field.visible = True

    sym_proto.value_field.name = "Value"
    sym_proto.value_field.text.text = "10k"
    sym_proto.value_field.visible = True

    # Pack into Any
    any_item = Any()
    any_item.Pack(sym_proto)

    cmd = CreateItems()
    cmd.header.document.CopyFrom(doc)
    cmd.items.append(any_item)

    print("Step 4: Sending CreateItems over live IPC API...")
    try:
        resp = client.send(cmd, CreateItemsResponse)
        print(f"✓ SUCCESS! Created {len(resp.created_items)} items on the schematic!")
        for item in resp.created_items:
            print(f"  Item Status: {item.status}")
    except Exception as e:
        print(f"⚠ Result: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
