"""Unit tests for backend abstraction."""

import os
from tests import mock_pcbnew
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.backends.sexpr import SexprBackend
from kicad_agent.core.actions import Action, ActionType


def test_pcbnew_backend_offline():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    act = Action(
        action_type=ActionType.ADD_FOOTPRINT,
        parameters={"reference": "R10", "x": 100.0, "y": 100.0, "value": "10k"},
    )
    res = backend.execute(act)
    assert res.success
    assert res.data["reference"] == "R10"

    act_drc = Action(action_type=ActionType.RUN_DRC)
    res_drc = backend.execute(act_drc)
    assert res_drc.success


def test_sexpr_backend_offline(tmp_path):
    sch_file = os.path.join(tmp_path, "test.kicad_sch")
    with open(sch_file, "w", encoding="utf-8") as f:
        f.write('(kicad_sch (version 20260306) (generator "eeschema")\n)\n')

    backend = SexprBackend(sch_filepath=sch_file)
    act = Action(
        action_type=ActionType.ADD_SYMBOL,
        parameters={"lib_id": "Device:R", "reference": "R1", "value": "10k", "x": 100.0, "y": 100.0},
    )
    res = backend.execute(act)
    assert res.success
    assert res.data["reference"] == "R1"
