"""Unit tests for schematic pin geometry and wire-endpoint reports."""

import pytest

from kicad_agent.schematic.pin_geometry import (
    endpoint_report,
    resolve_pin_tips,
    rotate_point_ccw,
)


def test_rotate_point_ccw():
    assert rotate_point_ccw(1.0, 0.0, 0) == pytest.approx((1.0, 0.0))
    assert rotate_point_ccw(0.0, 3.81, 90) == pytest.approx((-3.81, 0.0))
    assert rotate_point_ccw(1.0, 0.0, 180) == pytest.approx((-1.0, 0.0))
    assert rotate_point_ccw(7.62, 0.0, 0) == pytest.approx((7.62, 0.0))


def _sch(symbols="", wires="", junctions="", labels=""):
    return f"""(kicad_sch (version 20260306) (generator "eeschema")
  (uuid "root-uuid")
  (paper "A4")
  (lib_symbols)
{symbols}
{wires}
{junctions}
{labels}
)
"""


def test_clean_elbow_and_junction():
    # Closed rectangle loop: every corner is a 2-end elbow; the junction
    # sits on one corner. No dangling ends anywhere.
    text = _sch(
        wires='  (wire (pts (xy 0 0) (xy 5 0) (xy 5 5) (xy 0 5) (xy 0 0)) (uuid "w1"))\n'
              '  (junction (at 5 0) (uuid "j1"))',
    )
    report = endpoint_report(text)
    assert report["errors"] == []
    assert report["stats"]["wire_segments"] == 4


def test_dangling_end_is_error():
    text = _sch(wires='  (wire (pts (xy 0 0) (xy 5 0)) (uuid "w1"))')
    report = endpoint_report(text)
    kinds = [e["kind"] for e in report["errors"]]
    assert kinds.count("dangling_end") == 2


def test_three_way_meet_without_junction_is_error():
    # Outer ends terminate on labels, so the ONLY defect is the
    # junction-less 3-way meet at (5, 0).
    text = _sch(
        wires='  (wire (pts (xy 0 0) (xy 5 0)) (uuid "w1"))\n'
              '  (wire (pts (xy 5 0) (xy 9 0)) (uuid "w2"))\n'
              '  (wire (pts (xy 5 0) (xy 5 5)) (uuid "w3"))',
        labels='  (label "A" (at 0 0) (uuid "l1"))\n'
               '  (label "B" (at 9 0) (uuid "l2"))\n'
               '  (label "C" (at 5 5) (uuid "l3"))',
    )
    report = endpoint_report(text)
    assert [e["kind"] for e in report["errors"]] == ["missing_junction"]


def test_duplicate_reference_is_error():
    sym = ('  (symbol (lib_id "Device:R") (at 10 20 0) (uuid "s%s")\n'
           '    (property "Reference" "R1"))')
    text = _sch(symbols=sym % 1 + "\n" + sym % 2)
    report = endpoint_report(text)
    assert any(e["kind"] == "duplicate_reference" for e in report["errors"])


def test_unresolvable_library_warns_but_passes():
    text = _sch(
        symbols='  (symbol (lib_id "NoLib:NoSym") (at 10 20 0) (uuid "s1")\n'
                '    (property "Reference" "X1"))',
        wires='  (wire (pts (xy 0 0) (xy 0 0)) (uuid "w1"))',
    )
    report = endpoint_report(text)
    assert report["errors"] == []
    assert any(w["kind"] == "unresolved_library" for w in report["warnings"])


def test_device_r_pin_tips_when_library_present():
    tips = resolve_pin_tips("Device:R", 100.0, 100.0, 0.0)
    if tips is None:
        pytest.skip("KiCad symbol library not installed")
    assert tips["1"] == pytest.approx((100.0, 103.81))
    assert tips["2"] == pytest.approx((100.0, 96.19))
    rotated = resolve_pin_tips("Device:R", 100.0, 100.0, 90.0)
    assert rotated is not None
    assert rotated["1"] == pytest.approx((96.19, 100.0))
    assert rotated["2"] == pytest.approx((103.81, 100.0))
