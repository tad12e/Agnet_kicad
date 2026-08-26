"""Test placing component via high-level SchematicAPI."""
import sys
sys.path.insert(0, r"C:\Users\hp\OneDrive\Documents\KiCad\10.0\3rdparty\Python311\site-packages")
sys.path.insert(0, ".site-packages")
sys.path.insert(0, ".")

from kicad_api.ipc.client import KiCadIPCClient
from kicad_api.schematic.schematic import SchematicAPI

def main():
    print("Step 1: Connecting to KiCad IPC...")
    client = KiCadIPCClient()
    client.connect()
    print("[OK] Connected to KiCad socket!")

    sch = SchematicAPI(client=client)
    print(f"[OK] Active Document: {sch.document_proto.board_filename}")
    print(f"  Project: '{sch.document_proto.project.name}' @ '{sch.document_proto.project.path}'")

    print("Step 2: Placing R3 (4.7k) via sch.components.add()...")
    try:
        comp = sch.components.add(
            lib_id="Device:R",
            reference="R3",
            value="4.7k",
            position=(160.0, 100.0),
        )
        print(f"[SUCCESS] Placed {comp.reference} ({comp.value}) with KIID: {comp.id}")
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
