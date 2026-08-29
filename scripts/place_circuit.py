"""Demonstration script: Connect switch and resistor with wire."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".site-packages")))

from kicad_agent.schematic import Schematic


def main():
    sch = Schematic()
    print("Step 1: Placing Switch SW1...")
    sw = sch.components.add(
        lib_id="Switch:SW_Push",
        reference="SW1",
        value="SW_Push",
        position=(100.0, 100.0),
    )
    print(f"  [OK] Placed {sw.reference} (UUID: {sw.id})")

    print("\nStep 2: Placing Resistor R1...")
    r = sch.components.add(
        lib_id="Device:R",
        reference="R1",
        value="10k",
        position=(130.0, 96.19),
    )
    print(f"  [OK] Placed {r.reference} (UUID: {r.id})")

    print("\nStep 3: Connecting with wire...")
    wire = sch.wires.add(
        start=(105.08, 100.0),
        end=(130.0, 100.0),
    )
    print(f"  [OK] Added wire: {wire}")
    print("\n[SUCCESS] Circuit placed cleanly!")


if __name__ == "__main__":
    main()
