"""Unit tests for the S-expression schematic summarizer (cascade Step 2)."""

import os

import pytest

from kicad_agent.schematic.sexpr_summary import (
    summarize_schematic_text,
    summarize_wire,
    unquote,
)

FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "..", "fixtures", "schematic",
)


def _fixture(name):
    with open(os.path.join(FIXTURE, name), encoding="utf-8", errors="ignore") as f:
        return f.read()


def test_first_kicad_sch_summary():
    try:
        contents = _fixture("simple_schematic.kicad_sch")
    except FileNotFoundError:
        contents = open(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "first.kicad_sch"),
            encoding="utf-8", errors="ignore",
        ).read()
    summary = summarize_schematic_text(contents)
    assert summary["unknown_blocks"] == []
    assert isinstance(summary["symbols"], list)


def test_repo_first_schematic_exact():
    contents = open(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "first.kicad_sch"),
        encoding="utf-8", errors="ignore",
    ).read()
    summary = summarize_schematic_text(contents)
    assert len(summary["symbols"]) == 20
    assert len(summary["junctions"]) == 12
    assert len(summary["wires"]) == 53
    assert summary["unknown_blocks"] == []
    gnd = [s for s in summary["symbols"] if s["reference"] == "#PWR08"][0]
    assert gnd["value"] == "GND"
    assert gnd["lib_id"] == "power:GND"
    assert gnd["x_mm"] == pytest.approx(36.83)
    assert gnd["y_mm"] == pytest.approx(118.11)


SYNTHETIC = """(kicad_sch (version 20260306) (generator "eeschema")
  (uuid "root-uuid")
  (paper "A4")
  (lib_symbols (symbol "Device:R" (pin_numbers) (uuid "lib-uuid")))
  (symbol (lib_id "Device:R") (at 10 20 0) (uuid "s1")
    (property "Reference" "R1") (property "Value" "10k"))
  (wire (pts (xy 0 0) (xy 5 0) (xy 5 5)) (uuid "w1"))
  (bus (pts (xy 1 1) (xy 2 2)) (uuid "b1"))
  (junction (at 5 0) (uuid "j1"))
  (label "NET_A" (at 5 0) (uuid "l1"))
  (global_label "GND" (at 0 0) (uuid "g1"))
  (sheet (at 0 0) (size 1 1) (uuid "sh1")
    (property "Sheetname" "sub") (property "Sheetfile" "sub.kicad_sch"))
  (mystery_block (at 0 0))
)
"""


def test_synthetic_blocks():
    summary = summarize_schematic_text(SYNTHETIC)
    assert [s["reference"] for s in summary["symbols"]] == ["R1"]
    assert summary["symbols"][0]["lib_id"] == "Device:R"
    # Polyline wire -> 2 segments sharing the id.
    segs = [w for w in summary["wires"] if w["id"] == "w1"]
    assert len(segs) == 2
    assert segs[0]["end_mm"] == pytest.approx([5.0, 0.0])
    assert [w["kind"] for w in summary["wires"] if w["id"] == "b1"] == ["bus"]
    assert summary["junctions"] == [{"id": "j1", "x_mm": 5.0, "y_mm": 0.0}]
    labels = {label["id"]: label for label in summary["labels"]}
    assert labels["l1"]["text"] == "NET_A"
    assert labels["l1"]["label_type"] == "local_label"
    assert labels["g1"]["label_type"] == "global_label"
    assert summary["sheets"] == [
        {"id": "sh1", "name": "sub", "filename": "sub.kicad_sch"}
    ]
    # Library definitions are skipped, truly unknown blocks counted.
    assert summary["unknown_blocks"] == [{"type": "mystery_block"}]


def test_polyline_segment_chaining():
    wire = ["wire", ["pts", ["xy", "0", "0"], ["xy", "1", "0"], ["xy", "1", "1"]],
            ["uuid", '"w"']]
    segs = summarize_wire(wire, "wire")
    assert [(s["start_mm"], s["end_mm"]) for s in segs] == [
        ([0.0, 0.0], [1.0, 0.0]),
        ([1.0, 0.0], [1.0, 1.0]),
    ]


def test_rejects_empty_and_non_schematic():
    with pytest.raises(ValueError):
        summarize_schematic_text("   \n")
    with pytest.raises(ValueError):
        summarize_schematic_text("(kicad_pcb (version 1))")


def test_unquote():
    assert unquote('"abc"') == "abc"
    assert unquote("abc") == "abc"
    assert unquote(123) == ""
