import sys
import os
import json
import pytest

from unittest.mock import MagicMock
# Inject mock_pcbnew and mock wx before tools or agent are imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests import mock_pcbnew
sys.modules["pcbnew"] = mock_pcbnew
if "wx" not in sys.modules:
    try:
        import wx
    except ImportError:
        sys.modules["wx"] = MagicMock()

from plugin.tools import mm, nm, get_board_state, place_component, add_trace, run_drc
from plugin.agent import dispatch, TOOLS

def test_mm_conversions():
    assert mm(1.5) == 1500000
    assert nm(1500000) == 1.5

def test_get_board_state():
    state_json = get_board_state()
    state = json.loads(state_json)
    assert "components" in state
    assert "nets" in state
    assert "unconnected_pads" in state

def test_place_component():
    result = place_component(
        ref="R1",
        component_type="resistor",
        value="10k",
        x=100.0,
        y=100.0
    )
    assert "Placed R1" in result

def test_dispatch():
    res = dispatch("get_board_state", {})
    assert "components" in res

    unknown_res = dispatch("invalid_tool", {})
    assert "Unknown tool" in unknown_res
