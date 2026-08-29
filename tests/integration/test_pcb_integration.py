"""Integration test for PCB subsystem and AI Agent pipeline."""

import os
from tests import mock_pcbnew
from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.pcb.board import Board


def test_pcb_board_end_to_end(tmp_path):
    board_path = os.path.join(tmp_path, "board.kicad_pcb")
    with open(board_path, "w", encoding="utf-8") as f:
        f.write('(kicad_pcb (version 20260206) (generator "pcbnew")\n)\n')

    board = Board(filepath=board_path)
    fp = board.footprints.add(
        footprint_id="Resistor_SMD:R_0805_2012Metric",
        reference="R1",
        value="10k",
        position=(100.0, 100.0),
    )
    assert fp.reference == "R1"

    tr = board.tracks.add(
        start=(100.0, 100.0),
        end=(120.0, 100.0),
        width_mm=0.3,
    )
    assert tr.width_mm == 0.3

    via = board.vias.add(
        at=(120.0, 100.0),
        size_mm=0.8,
        drill_mm=0.4,
    )
    assert via.drill_mm == 0.4


def test_pcb_natural_language_pipeline():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    agent = KiCadAgent(backend=backend)
    
    # Run multi-component creation
    result = agent.run("Create a PCB with an Arduino Leonardo, LED, and resistor")
    assert result["success"]
    assert len(result["results"]) >= 3
    assert result["transaction_state"] == "committed"
