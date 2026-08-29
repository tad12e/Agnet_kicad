"""Unit tests for PCB domain operations and S-expression engine."""

import os
from kicad_agent.pcb.board import Board
from kicad_agent.pcb.operations import PCBOperations
from kicad_agent.backends.sexpr import SexprBackend


def test_board_initialization(sample_pcb_file):
    board = Board(filepath=sample_pcb_file)
    assert board.filepath == sample_pcb_file
    assert board.footprints is not None
    assert board.tracks is not None
    assert board.vias is not None
    assert board.zones is not None


def test_pcb_operations_with_sexpr(tmp_path):
    pcb_file = os.path.join(tmp_path, "test.kicad_pcb")
    with open(pcb_file, "w", encoding="utf-8") as f:
        f.write('(kicad_pcb (version 20260206) (generator "pcbnew")\n)\n')

    backend = SexprBackend(pcb_filepath=pcb_file)
    ops = PCBOperations(backend)

    res_fp = ops.place_footprint(
        footprint_id="Resistor_SMD:R_0402",
        reference="R1",
        value="10k",
        x=100.0,
        y=100.0,
    )
    assert res_fp.success
    assert "uuid" in res_fp.data

    res_track = ops.add_track(
        start=(100.0, 100.0),
        end=(120.0, 100.0),
        width_mm=0.25,
    )
    assert res_track.success

    res_via = ops.add_via(
        at=(120.0, 100.0),
        size_mm=0.8,
        drill_mm=0.4,
    )
    assert res_via.success
