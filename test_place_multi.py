"""Test placing multiple components via SchematicAPI."""
import sys
sys.path.insert(0, ".site-packages")
sys.path.insert(0, ".")

from kicad_api.ipc.client import KiCadIPCClient
from kicad_api.schematic.schematic import SchematicAPI

def main():
    print("Connecting to KiCad IPC...")
    client = KiCadIPCClient()
    client.connect()
    print("[OK] Connected!")

    sch = SchematicAPI(client=client)

    components_to_place = [
        ("Device:R", "R4", "10k", (120.0, 80.0)),
        ("Device:C", "C1", "100nF", (140.0, 80.0)),
        ("Device:LED", "D1", "RED", (160.0, 80.0)),
    ]

    for lib_id, ref, val, pos in components_to_place:
        print(f"Placing {ref} ({val}) at {pos}...")
        comp = sch.components.add(
            lib_id=lib_id,
            reference=ref,
            value=val,
            position=pos,
        )
        print(f"  -> Placed {comp.reference} with UUID: {comp.id}")

    print("\n[SUCCESS] All components placed successfully without any crashes!")

if __name__ == "__main__":
    main()
