"""Unit tests for kicad_api.models."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kicad_api.models import Component, Wire, Junction, Pin, Net


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
    assert c.unit == 1
    assert "R1" in repr(c)


def test_wire_model():
    w = Wire(start_mm=(10.0, 20.0), end_mm=(30.0, 40.0))
    assert w.start_mm == (10.0, 20.0)
    assert w.end_mm == (30.0, 40.0)
    assert w.id is not None
    assert "Wire" in repr(w)


def test_junction_model():
    j = Junction(position_mm=(50.0, 60.0))
    assert j.position_mm == (50.0, 60.0)
    assert j.id is not None
    assert "Junction" in repr(j)


def test_pin_model():
    p = Pin(number="1", name="VCC", position_mm=(100.0, 95.0), pin_type="power_in", parent_ref="U1")
    assert p.number == "1"
    assert p.name == "VCC"
    assert p.position_mm == (100.0, 95.0)
    assert p.pin_type == "power_in"
    assert p.parent_ref == "U1"


def test_net_model():
    n = Net(name="GND")
    assert n.name == "GND"
    assert len(n.pins) == 0
