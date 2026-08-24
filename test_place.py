"""Test placing a component on the active KiCad schematic."""
import sys
import time
from google.protobuf.any_pb2 import Any

from kicad_api.ipc.client import KiCadIPCClient
from kicad_api.schematic.schematic import SchematicAPI

def main():
    print("Connecting to KiCad IPC...")
    client = KiCadIPCClient()
    client.connect()
    print("✓ Connected to KiCad socket!")

    sch = SchematicAPI(client=client)
    doc = sch.document_proto

    import os

    candidate_paths = [
        r"C:\Users\hp\ECE\test\Agent",
        r"C:/Users/hp/ECE/test/Agent",
        r"C:\Users\hp\ECE",
        r"C:/Users/hp/ECE",
    ]

    for p in candidate_paths:
        doc.project.name = "Agent"
        doc.project.path = p

        # Test placing a Junction via CreateItems
        try:
            from proto.common.commands.editor_commands_pb2 import CreateItems, CreateItemsResponse
            from proto.schematic.schematic_types_pb2 import Junction
            import uuid

            junction = Junction()
            junction.id.value = str(uuid.uuid4())
            junction.position.x_nm = int(100.0 * 1_000_000)  # 100mm
            junction.position.y_nm = int(100.0 * 1_000_000)  # 100mm

            any_junc = Any()
            any_junc.Pack(junction)

            cmd_junc = CreateItems()
            cmd_junc.header.document.CopyFrom(doc)
            cmd_junc.items.append(any_junc)

            resp_junc = client.send(cmd_junc, CreateItemsResponse)
            print(f"✓ SUCCESS with project path '{p}'! Created items: {len(resp_junc.created_items)}")
            break
        except Exception as e:
            print(f"⚠ Attempt with path '{p}' failed: {e}")

if __name__ == "__main__":
    main()
