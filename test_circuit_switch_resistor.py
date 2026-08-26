"""Test connecting a switch and a resistor with a wire."""
import sys
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

    print("\nStep 2: Placing Switch SW1...")
    sw_pos = (100.0, 100.0)
    sw = sch.components.add(
        lib_id="Switch:SW_Push",
        reference="SW1",
        value="SW_Push",
        position=sw_pos,
    )
    print(f"  [OK] Placed {sw.reference} at {sw_pos} (UUID: {sw.id})")

    # Switch Pin 2 is at (sw_x + 5.08, sw_y) = (105.08, 100.0)
    sw_pin2 = (sw_pos[0] + 5.08, sw_pos[1])

    print("\nStep 3: Placing Resistor R1...")
    # Resistor Pin 1 is at (r_x, r_y + 3.81).
    # To align with Y=100.0, we place R1 at (130.0, 100.0 - 3.81) = (130.0, 96.19)
    r_pos = (130.0, 96.19)
    r = sch.components.add(
        lib_id="Device:R",
        reference="R1",
        value="10k",
        position=r_pos,
    )
    print(f"  [OK] Placed {r.reference} at {r_pos} (UUID: {r.id})")

    # Resistor Pin 1 is at (130.0, 100.0)
    r_pin1 = (r_pos[0], r_pos[1] + 3.81)

    print(f"\nStep 4: Connecting SW1 Pin 2 {sw_pin2} to R1 Pin 1 {r_pin1} with a wire...")
    wire = sch.wires.add(
        start=sw_pin2,
        end=r_pin1,
    )
    print(f"  [OK] Added wire: {wire}")

    print("\n" + "=" * 50)
    print("[SUCCESS] Connected SW1 and R1 with a wire cleanly!")
    print("=" * 50)

if __name__ == "__main__":
    main()
