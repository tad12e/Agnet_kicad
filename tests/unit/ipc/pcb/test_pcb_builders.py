"""Unit tests for PCB item builders (Part 5).

Verifies that builders construct valid protobuf messages matching KiCad 10.0:
- Coordinates and distances converted to nm correctly (1 mm = 1,000,000 nm)
- Angles stored as value_degrees (KiCad 10.0 proto field)
- Locked state mapped to LockedState enum (LS_LOCKED = 2, LS_UNLOCKED = 1)
- Zone outline constructed as PolySet -> PolygonWithHoles -> PolyLine -> nodes
- FootprintInstance properly nests definition, reference_field, value_field
- Round-trips through converter dicts match original inputs
"""

import pytest

from kicad_agent.ipc.pcb.types_pcb import (
    arc_to_dict,
    build_angle,
    build_arc,
    build_board_text,
    build_copper_zone,
    build_distance,
    build_footprint_instance,
    build_locked_state,
    build_net,
    build_simple_padstack,
    build_text,
    build_track,
    build_vector2,
    build_via,
    footprint_instance_to_dict,
    is_locked,
    mm_pair_to_nm,
    mm_to_nm,
    nm_pair_to_mm,
    nm_to_mm,
    pack_any,
    pad_to_dict,
    track_to_dict,
    via_to_dict,
    zone_to_dict,
)


def test_unit_conversions():
    assert mm_to_nm(1.0) == 1_000_000
    assert mm_to_nm(0.25) == 250_000
    assert nm_to_mm(1_000_000) == 1.0
    assert nm_to_mm(250_000) == 0.25
    assert mm_pair_to_nm((1.5, 2.5)) == (1_500_000, 2_500_000)
    assert nm_pair_to_mm((1_500_000, 2_500_000)) == (1.5, 2.5)


def test_scalar_builders():
    v = build_vector2(10.0, 20.0)
    assert v.x_nm == 10_000_000
    assert v.y_nm == 20_000_000

    d = build_distance(0.5)
    assert d.value_nm == 500_000

    a = build_angle(45.0)
    assert a.value_degrees == 45.0

    # LockedState enum: 2 = LS_LOCKED, 1 = LS_UNLOCKED
    ls_true = build_locked_state(True)
    ls_false = build_locked_state(False)
    assert ls_true == 2
    assert ls_false == 1
    assert is_locked(ls_true) is True
    assert is_locked(ls_false) is False

    net = build_net("VCC", 42)
    assert net.name == "VCC"
    assert net.code.value == 42


def test_build_track():
    t = build_track(
        start=(0.0, 0.0),
        end=(10.0, 5.0),
        width_mm=0.25,
        layer=3,
        net_name="GND",
        net_code=1,
        locked=True,
    )
    assert t.start.x_nm == 0
    assert t.start.y_nm == 0
    assert t.end.x_nm == 10_000_000
    assert t.end.y_nm == 5_000_000
    assert t.width.value_nm == 250_000
    assert t.layer == 3
    assert t.net.name == "GND"
    assert t.net.code.value == 1
    assert t.locked == 2

    d = track_to_dict(t)
    assert d["start"] == (0.0, 0.0)
    assert d["end"] == (10.0, 5.0)
    assert d["width_mm"] == 0.25
    assert d["net"] == "GND"
    assert d["locked"] is True


def test_build_arc():
    a = build_arc(
        start=(0.0, 0.0),
        mid=(5.0, 5.0),
        end=(10.0, 0.0),
        width_mm=0.3,
        layer=3,
        net_name="SIG",
        net_code=2,
    )
    assert a.start.x_nm == 0
    assert a.mid.x_nm == 5_000_000
    assert a.mid.y_nm == 5_000_000
    assert a.end.x_nm == 10_000_000
    assert a.width.value_nm == 300_000

    d = arc_to_dict(a)
    assert d["mid"] == (5.0, 5.0)
    assert d["width_mm"] == 0.3
    assert d["locked"] is False


def test_build_via():
    v = build_via(
        position=(15.0, 25.0),
        size_mm=0.8,
        drill_mm=0.4,
        net_name="GND",
        net_code=1,
        via_type=1,
        layers=(3, 34),
        locked=False,
    )
    assert v.position.x_nm == 15_000_000
    assert v.position.y_nm == 25_000_000
    assert v.pad_stack.drill.diameter.x_nm == 400_000
    assert len(v.pad_stack.copper_layers) == 2
    assert v.pad_stack.copper_layers[0].size.x_nm == 800_000
    assert v.type == 1

    d = via_to_dict(v)
    assert d["position"] == (15.0, 25.0)
    assert d["size_mm"] == 0.8
    assert d["drill_mm"] == 0.4
    assert d["net"] == "GND"


def test_build_copper_zone():
    polygon = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
    z = build_copper_zone(
        polygon=polygon,
        layer=3,
        net_name="GND",
        net_code=1,
        clearance_mm=0.4,
        min_thickness_mm=0.2,
    )
    assert z.name == "GND"
    assert z.filled is False
    assert z.copper_settings.clearance.value_nm == 400_000
    assert z.copper_settings.min_thickness.value_nm == 200_000

    # PolySet -> PolygonWithHoles -> PolyLine -> nodes
    assert len(z.outline.polygons) == 1
    outline = z.outline.polygons[0].outline
    assert outline.closed is True
    assert len(outline.nodes) == 4
    assert outline.nodes[0].point.x_nm == 0
    assert outline.nodes[1].point.x_nm == 20_000_000

    d = zone_to_dict(z)
    assert d["vertices"] == [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
    assert d["name"] == "GND"
    assert d["filled"] is False


def test_build_footprint_instance():
    fp = build_footprint_instance(
        reference="C1",
        value="100nF",
        position=(50.0, 60.0),
        orientation_deg=180.0,
        layer=3,
        library_id="Capacitor_SMD",
        footprint_name="C_0603_1608Metric",
    )
    assert fp.position.x_nm == 50_000_000
    assert fp.position.y_nm == 60_000_000
    assert fp.orientation.value_degrees == 180.0
    assert fp.definition.id.library_nickname == "Capacitor_SMD"
    assert fp.definition.id.entry_name == "C_0603_1608Metric"
    assert fp.reference_field.text.text.text == "C1"
    assert fp.value_field.text.text.text == "100nF"

    d = footprint_instance_to_dict(fp)
    assert d["reference"] == "C1"
    assert d["value"] == "100nF"
    assert d["position"] == (50.0, 60.0)
    assert d["orientation_deg"] == 180.0
    assert d["library"] == "Capacitor_SMD"
    assert d["footprint"] == "C_0603_1608Metric"


def test_pack_any():
    t = build_track((0.0, 0.0), (1.0, 1.0))
    packed = pack_any(t)
    assert packed.TypeName() == "kiapi.board.types.Track"
