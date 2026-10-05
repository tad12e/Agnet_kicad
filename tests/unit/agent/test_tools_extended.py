"""Unit tests for extended ToolRegistry, schemas, tool-to-action conversion, and observations."""

from tests import mock_pcbnew
from kicad_agent.agent.tools import ToolRegistry, tool_call_to_action
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.core.actions import ActionDomain, ActionType


def test_tool_schema_discovery():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    registry = ToolRegistry(backend)

    # Domain filtering
    sch_tools = registry.get_available_tools(domain="schematic")
    pcb_tools = registry.get_available_tools(domain="pcb")
    all_tools = registry.get_available_tools()

    sch_names = [t["name"] for t in sch_tools]
    pcb_names = [t["name"] for t in pcb_tools]

    assert "add_symbol" in sch_names
    assert "add_wire" in sch_names
    assert "get_symbol_pins" in sch_names
    assert "run_erc" in sch_names

    assert "add_footprint" in pcb_names
    assert "add_track" in pcb_names
    assert "run_drc" in pcb_names

    assert len(all_tools) >= len(sch_tools) + len(pcb_tools) - 5


def test_tool_call_to_action_mapping():
    # Schematic conversion
    act_sym = tool_call_to_action("add_symbol", {"reference": "R1", "value": "10k", "x": 50.0, "y": 50.0}, domain="schematic")
    assert act_sym.action_type == ActionType.ADD_SYMBOL
    assert act_sym.domain == ActionDomain.SCHEMATIC
    assert act_sym.parameters["reference"] == "R1"

    act_wire = tool_call_to_action("add_wire", {"start": (0, 0), "end": (10, 0)}, domain="schematic")
    assert act_wire.action_type == ActionType.ADD_WIRE
    assert act_wire.domain == ActionDomain.SCHEMATIC

    # PCB conversion
    act_fp = tool_call_to_action("add_footprint", {"reference": "C1", "x": 20.0, "y": 30.0}, domain="pcb")
    assert act_fp.action_type == ActionType.ADD_FOOTPRINT
    assert act_fp.domain == ActionDomain.PCB


def test_tool_execution_observations():
    mock_pcbnew.ResetBoard()
    backend = PcbnewBackend()
    backend._pcbnew = mock_pcbnew
    backend._board = mock_pcbnew.GetBoard()

    registry = ToolRegistry(backend)

    # Add footprint execution & observation
    res = registry.execute_tool("add_footprint", {"reference": "R1", "x": 10.0, "y": 20.0, "value": "10k"}, domain="pcb")
    assert res["status"] == "success"
    assert "observation" in res
    assert "R1" in res["observation"]
