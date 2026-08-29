"""Unit tests for independent verification engine."""

from kicad_agent.core.actions import Action, ActionType
from kicad_agent.core.results import ActionResult
from kicad_agent.verification.connectivity import ConnectivityVerifier
from kicad_agent.verification.drc import DRCVerifier
from kicad_agent.verification.geometry import GeometryVerifier
from kicad_agent.verification.placement import PlacementVerifier


def test_placement_verifier():
    verifier = PlacementVerifier()
    act = Action(
        action_type=ActionType.ADD_FOOTPRINT,
        parameters={"reference": "R1", "x": 100.0, "y": 100.0},
    )
    res = ActionResult(action_id=act.action_id, success=True)
    v_res = verifier.verify(act, res)
    assert v_res.passed


def test_drc_verifier():
    verifier = DRCVerifier()
    act = Action(action_type=ActionType.RUN_DRC)
    res_clean = ActionResult(action_id=act.action_id, success=True, data={"status": "clean", "unconnected_count": 0})
    assert verifier.verify(act, res_clean).passed

    res_error = ActionResult(action_id=act.action_id, success=True, data={"status": "has errors", "unconnected_count": 2})
    assert not verifier.verify(act, res_error).passed


def test_connectivity_verifier():
    verifier = ConnectivityVerifier()
    act = Action(action_type=ActionType.VERIFY_CONNECTIVITY)
    res = ActionResult(action_id=act.action_id, success=True, data={"unconnected_pads": 0})
    assert verifier.verify(act, res).passed
