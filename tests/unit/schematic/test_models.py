"""Unit tests for Schematic domain models."""

from kicad_agent.schematic.symbols import Component, Pin
from kicad_agent.schematic.wires import Wire
from kicad_agent.schematic.junctions import Junction
from kicad_agent.schematic.labels import Label


def test_component_model():
    c = Component(
        id="uuid-123",
        lib_id="Device:R",
        reference="R1",
        value="10k",
        position_mm=(100.0, 100.0),
        unit=1,
    )
    assert c.id == "uuid-123"
    assert c.lib_id == "Device:R"
    assert c.reference == "R1"
    assert c.value == "10k"
    assert c.position_mm == (100.0, 100.0)
    assert "R1" in repr(c)


def test_wire_model():
    w = Wire(id="wire-1", start=(10.0, 20.0), end=(30.0, 40.0))
    assert w.start_mm == (10.0, 20.0)
    assert w.end_mm == (30.0, 40.0)
    assert "Wire" in repr(w)


def test_junction_model():
    j = Junction(position_mm=(50.0, 60.0))
    assert j.position_mm == (50.0, 60.0)
    assert j.id is not None


def test_label_model():
    l = Label(name="VCC", position_mm=(10.0, 10.0), label_type="global")
    assert l.name == "VCC"
    assert l.label_type == "global"
