"""Unit tests for the MCP server session and tool surface.

All file-writing tests run against a scratch copy of the schematic
fixture (lib-independent ops only: labels and junctions need no KiCad
symbol libraries), so they pass with or without KiCad installed.
"""

import os
import shutil

from kicad_agent.agent.tools import ALL_TOOLS_SCHEMA
from kicad_agent.mcp.server import all_tool_definitions
from kicad_agent.mcp.session import MCPSession


def _fresh_session():
    return MCPSession(mode="sexpr")


def test_mcp_tool_schemas_complete():
    tools = all_tool_definitions()
    assert len(tools) == 36  # 5 session + 1 tier2 + 18 pcb + 12 schematic
    assert len(ALL_TOOLS_SCHEMA) == 30
    names = [t["name"] for t in tools]
    for expected in (
        "open_schematic", "open_pcb", "save_schematic", "save_pcb",
        "session_info", "run_design_task",
        "get_schematic_state", "get_symbol_pins", "search_symbols",
        "verify_schematic_connectivity",
        "add_symbol", "add_wire", "add_junction", "add_label",
        "add_bus", "move_symbol", "rotate_symbol", "delete_symbol",
        "add_footprint", "add_track",
    ):
        assert expected in names, f"missing tool: {expected}"
    for tool in tools:
        assert tool["description"], f"{tool['name']} has no description"
        schema = tool["input_schema"]
        assert schema.get("type") == "object", f"{tool['name']} schema is not an object"
        assert isinstance(schema.get("properties", {}), dict)
    by_name = {t["name"]: t for t in tools}
    assert by_name["add_symbol"]["input_schema"]["required"] == [
        "lib_id", "reference", "x", "y"]
    assert by_name["add_wire"]["input_schema"]["required"] == ["start", "end"]
    assert by_name["open_schematic"]["input_schema"]["required"] == ["path"]
    assert by_name["run_design_task"]["input_schema"]["required"] == ["task"]


def test_mcp_session_info():
    out = _fresh_session().dispatch("session_info", {})
    assert out["status"] == "success"
    assert out["mode"] == "sexpr"
    assert out["live"] is False
    assert out["schematic"] is None
    assert out["pcb"] is None


def test_mcp_no_document_errors():
    session = _fresh_session()
    out = session.dispatch("get_schematic_state", {})
    assert out["status"] == "error"
    assert out["code"] == "NO_ACTIVE_DOCUMENT"
    out = session.dispatch("add_wire", {"start": [0, 0], "end": [5, 0]})
    assert out["status"] == "error"
    assert out["code"] == "NO_ACTIVE_DOCUMENT"
    out = session.dispatch(
        "open_schematic", {"path": os.path.join("nope", "missing.kicad_sch")})
    assert out["status"] == "error"
    assert out["code"] == "FILE_NOT_FOUND"
    out = session.dispatch("open_schematic", {})
    assert out["status"] == "error"
    assert out["code"] == "MISSING_ARGUMENT"
