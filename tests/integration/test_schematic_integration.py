"""Integration test for Schematic subsystem."""

import os
from kicad_agent.schematic.schematic import Schematic


def test_schematic_end_to_end(tmp_path):
    sch_path = os.path.join(tmp_path, "schematic.kicad_sch")
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write('(kicad_sch (version 20260306) (generator "eeschema")\n)\n')

    sch = Schematic(filepath=sch_path)
    sym = sch.components.add(
        lib_id="Device:R",
        reference="R1",
        value="10k",
        position=(100.0, 100.0),
    )
    assert sym.reference == "R1"

    w = sch.wires.add(
        start=(100.0, 96.19),
        end=(130.0, 96.19),
    )
    assert w.id is not None
