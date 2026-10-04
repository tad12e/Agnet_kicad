"""Unit tests for the schematic connectivity verifier."""

from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.core.results import ActionResult
from kicad_agent.verification.schematic_connectivity import (
    SchematicConnectivityVerifier,
)


def _text(symbols="", wires="", junctions="", labels=""):
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


def _action():
    return Action(
        action_type=ActionType.ADD_WIRE,
        domain=ActionDomain.SCHEMATIC,
        parameters={"start": (0, 0), "end": (5, 0)},
    )


def _result(ok=True):
    return ActionResult(action_id="a1", success=ok)


def test_passes_on_clean_text():
    verifier = SchematicConnectivityVerifier()
    text = _text(
        wires='  (wire (pts (xy 0 0) (xy 5 0) (xy 5 5) (xy 0 5) (xy 0 0)) (uuid "w1"))\n'
              '  (junction (at 5 0) (uuid "j1"))',
    )
    out = verifier.verify(_action(), _result(), expected={"schematic_text": text})
    assert out.passed
    assert out.verifier_name == "schematic_connectivity"


def test_fails_on_dangling_end():
    verifier = SchematicConnectivityVerifier()
    text = _text(wires='  (wire (pts (xy 0 0) (xy 5 0)) (uuid "w1"))')
    out = verifier.verify(_action(), _result(), expected={"schematic_text": text})
    assert not out.passed
    assert "lands on nothing" in out.message


def test_fails_without_text():
    verifier = SchematicConnectivityVerifier()
    out = verifier.verify(_action(), _result(), expected={})
    assert not out.passed


def test_fails_on_failed_action():
    verifier = SchematicConnectivityVerifier()
    out = verifier.verify(_action(), _result(ok=False), expected={"schematic_text": _text()})
    assert not out.passed
