"""Diagnostic test: place symbol using EXACT same pattern as test_kipy.py (Junction).

This test does NOT call GetSchematicHierarchy or sheet_path at all.
It uses the document from GetOpenDocuments directly, just like test_kipy.py.
"""
import sys
sys.path.insert(0, r"C:\Users\hp\OneDrive\Documents\KiCad\10.0\3rdparty\Python311\site-packages")
sys.path.insert(0, ".site-packages")
sys.path.insert(0, ".")

import uuid
from google.protobuf.any_pb2 import Any

from kicad_api.ipc.client import KiCadIPCClient
from kicad_api.ipc.messages import get_editor_command_protos, DocumentType, get_schematic_type_protos

def main():
    print("Step 1: Connecting...")
    client = KiCadIPCClient()
    client.connect()
    print("✓ Connected!")

    print("Step 2: GetOpenDocuments...")
    _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
    cmd = GetOpenDocuments()
    cmd.type = DocumentType.DOCTYPE_SCHEMATIC
    resp = client.send(cmd, GetOpenDocumentsResponse)

    if not resp.documents:
        print("⚠ No schematic documents open!")
        return

    doc = resp.documents[0]
    print(f"✓ Document: board_filename='{doc.board_filename}'")
    print(f"  project.name='{doc.project.name}'  project.path='{doc.project.path}'")
    print(f"  Has sheet_path? {doc.HasField('sheet_path') if hasattr(doc, 'HasField') else 'N/A'}")
    print(f"  WhichOneof('identifier') = {doc.WhichOneof('identifier')}")

    # DO NOT query GetSchematicHierarchy. Just build and send CreateItems.
    print("Step 3: Building SchematicSymbolInstance (NO GetSchematicHierarchy call)...")
    (SchematicSymbolInstance,) = get_schematic_type_protos()
    CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()

    sym_proto = SchematicSymbolInstance()
    sym_proto.id.value = str(uuid.uuid4())
    sym_proto.position.x_nm = 100_000_000  # 100mm
    sym_proto.position.y_nm = 100_000_000  # 100mm

    # Do NOT set sym_proto.path at all — same as Junction test

    # Library reference
    sym_proto.definition.id.library_nickname = "Device"
    sym_proto.definition.id.entry_name = "R"
    sym_proto.definition.unit_count = 1
    sym_proto.transform.orientation = 1
    sym_proto.unit.unit = 1

    # Instance fields
    sym_proto.reference_field.name = "Reference"
    sym_proto.reference_field.text.text = "R5"
    sym_proto.reference_field.visible = True

    sym_proto.value_field.name = "Value"
    sym_proto.value_field.text.text = "10k"
    sym_proto.value_field.visible = True

    any_item = Any()
    any_item.Pack(sym_proto)

    cmd = CreateItems()
    cmd.header.document.CopyFrom(doc)
    cmd.items.append(any_item)

    print(f"  Header document:\n{cmd.header}")

    print("Step 4: Sending CreateItems...")
    try:
        resp = client.send(cmd, CreateItemsResponse)
        print(f"✓ SUCCESS! Created {len(resp.created_items)} items")
        for item in resp.created_items:
            print(f"  Status: {item.status}")
    except Exception as e:
        print(f"⚠ Result: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
