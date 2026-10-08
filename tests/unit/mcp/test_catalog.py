"""Tests for the stable MCP capability catalog."""

from kicad_agent.agent.tools import ALL_TOOLS_SCHEMA
from kicad_agent.mcp.catalog import (
    CATALOG_VERSION,
    CAPABILITY_GROUPS,
    MCP_TOOL_CATALOG,
    get_capability_group,
    get_tool_catalog,
)
from kicad_agent.mcp.server import all_tool_definitions


def test_catalog_groups_cover_every_exposed_tool_once():
    exposed_names = [tool["name"] for tool in all_tool_definitions()]
    grouped_names = [
        name
        for group in CAPABILITY_GROUPS
        for name in group.tool_names
    ]

    assert grouped_names == exposed_names
    assert len(grouped_names) == len(set(grouped_names))
    assert len(ALL_TOOLS_SCHEMA) == 32


def test_catalog_has_stable_version_and_group_metadata():
    catalog = get_tool_catalog()

    assert CATALOG_VERSION == "1.0.0"
    assert MCP_TOOL_CATALOG["version"] == CATALOG_VERSION
    assert [group["id"] for group in catalog["groups"]] == [
        "session",
        "automation",
        "schematic-inspection",
        "schematic-editing",
        "pcb-inspection",
        "pcb-editing",
    ]
    for group in catalog["groups"]:
        assert group["title"]
        assert group["description"]
        assert group["tools"]


def test_catalog_group_lookup():
    assert "open_schematic" in get_capability_group("session").tools
    assert "run_design_task" in get_capability_group("automation").tools
    assert "add_symbol" in get_capability_group("schematic-editing").tools
    assert "add_track" in get_capability_group("pcb-editing").tools
