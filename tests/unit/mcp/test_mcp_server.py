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
    assert len(tools) == 38  # 5 session + 1 tier2 + 19 pcb + 13 schematic
    assert len(ALL_TOOLS_SCHEMA) == 32
    names = [t["name"] for t in tools]
    for expected in (
        "open_schematic", "open_pcb", "save_schematic", "save_pcb",
        "session_info", "run_design_task",
        "get_schematic_state", "get_symbol_pins", "search_symbols",
        "verify_schematic_connectivity",
        "add_symbol", "add_wire", "add_junction", "add_label",
        "add_bus", "move_symbol", "rotate_symbol", "delete_symbol",
        "add_footprint", "add_track", "run_erc",
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


def test_mcp_open_and_label_roundtrip(sample_sch_file, tmp_path):
    scratch = os.path.join(tmp_path, "scratch.kicad_sch")
    shutil.copyfile(sample_sch_file, scratch)
    session = _fresh_session()

    opened = session.dispatch("open_schematic", {"path": scratch})
    assert opened["status"] == "success"
    assert opened["file"] == os.path.abspath(scratch)

    added = session.dispatch(
        "add_label", {"text": "NET1", "x": 10.0, "y": 20.0})
    assert added["status"] == "success"
    assert added["data"]["uuid"]

    state = session.dispatch("get_schematic_state", {})
    assert state["status"] == "success"
    labels = state["schematic"]["labels"]
    assert any(label.get("text") == "NET1" for label in labels)

    check = session.dispatch("verify_schematic_connectivity", {})
    assert check["status"] == "success"
    assert isinstance(check["connected"], bool)
    assert isinstance(check["errors"], list)
    assert isinstance(check["warnings"], list)

    saved = session.dispatch("save_schematic", {})
    assert saved["status"] == "success"

    with open(scratch, "r", encoding="utf-8", errors="ignore") as f:
        assert "NET1" in f.read()


def test_mcp_tier2_guards():
    session = _fresh_session()
    out = session.dispatch("run_design_task", {"task": ""})
    assert out["status"] == "error"
    assert out["code"] == "MISSING_ARGUMENT"

    out = session.dispatch(
        "run_design_task", {"task": "x", "domain": "radio"})
    assert out["status"] == "error"
    assert out["code"] == "BAD_DOMAIN"

    saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        out = session.dispatch("run_design_task", {"task": "add an LED"})
    finally:
        if saved_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved_key
    assert out["status"] == "error"
    assert out["code"] == "NO_API_KEY"


def test_mcp_unknown_tool():
    out = _fresh_session().dispatch("frobnicate", {})
    assert out["status"] == "error"
    assert "frobnicate" in out["message"]
