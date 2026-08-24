"""Test CreateItems using kipy's NNG connection + our protobuf definitions."""
import sys
sys.path.insert(0, ".")

# Use our own client (protobuf 7.x compatible) for everything
from kicad_api.ipc.client import KiCadIPCClient
from kicad_api.ipc.messages import get_editor_command_protos, DocumentType
from proto.schematic.schematic_types_pb2 import Junction
from google.protobuf.any_pb2 import Any
import uuid

def main():
    print("Step 1: Connecting...")
    client = KiCadIPCClient()
    client.connect()
    print("✓ Connected!")

    print("Step 2: Getting open documents...")
    _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
    cmd = GetOpenDocuments()
    cmd.type = DocumentType.DOCTYPE_SCHEMATIC
    resp = client.send(cmd, GetOpenDocumentsResponse)
    
    if not resp.documents:
        print("⚠ No schematic documents open!")
        return
    
    doc = resp.documents[0]
    print(f"✓ Document: {doc}")

    # Step 3: Create a Junction
    print("Step 3: Creating Junction at (100mm, 100mm)...")
    junction = Junction()
    junction.id.value = str(uuid.uuid4())
    junction.position.x_nm = 100_000_000  # 100mm in nm
    junction.position.y_nm = 100_000_000

    any_item = Any()
    any_item.Pack(junction)

    CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()
    cmd = CreateItems()
    cmd.header.document.CopyFrom(doc)
    cmd.items.append(any_item)

    print(f"  Header:\n{cmd.header}")
    
    resp = client.send(cmd, CreateItemsResponse)
    print(f"✓ SUCCESS! Created {len(resp.created_items)} items")
    for item in resp.created_items:
        print(f"  Status: {item.status}")

if __name__ == "__main__":
    main()
