"""Stable capability catalog for the KiCad MCP tool surface.

The catalog describes the public MCP tools without changing their schemas or
dispatch behavior.  Tool definitions remain owned by the existing MCP and
agent modules; this module only provides stable grouping and version metadata
for clients that need to discover capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Tuple

from ..agent.tools import (
    ALL_TOOLS_SCHEMA,
    PCB_READ_TOOLS_SCHEMA,
    PCB_WRITE_TOOLS_SCHEMA,
    SCHEMATIC_READ_SCHEMA,
    SCHEMATIC_WRITE_SCHEMA,
)
from .session import SESSION_TOOLS_SCHEMA, TIER2_TOOLS_SCHEMA


CATALOG_VERSION = "1.0.0"
"""Semantic version of the capability catalog shape and group assignments."""

# A descriptive alias keeps the version easy to find for integrations that
# refer to the catalog specifically as the MCP tool catalog.
MCP_TOOL_CATALOG_VERSION = CATALOG_VERSION


@dataclass(frozen=True)
class CapabilityGroup:
    """A stable, ordered group of MCP tool names."""

    id: str
    title: str
    description: str
    tool_names: Tuple[str, ...]

    @property
    def tools(self) -> Tuple[str, ...]:
        """Compatibility-friendly alias for consumers that call them tools."""
        return self.tool_names

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation of this group."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tools": list(self.tool_names),
        }


def _names(*schemas: Any) -> Tuple[str, ...]:
    """Extract ordered, unique names from tool schema collections."""
    result = []
    seen = set()
    for schema in schemas:
        for tool in schema:
            name = tool["name"]
            if name not in seen:
                result.append(name)
                seen.add(name)
    return tuple(result)


CAPABILITY_GROUPS: Tuple[CapabilityGroup, ...] = (
    CapabilityGroup(
        id="session",
        title="Session",
        description="Open, save, and inspect active KiCad documents and server state.",
        tool_names=_names(SESSION_TOOLS_SCHEMA),
    ),
    CapabilityGroup(
        id="automation",
        title="Automation",
        description="Run a complete design task through the built-in planning agent.",
        tool_names=_names(TIER2_TOOLS_SCHEMA),
    ),
    CapabilityGroup(
        id="schematic-inspection",
        title="Schematic inspection",
        description="Inspect symbols, connectivity, and electrical rules in schematics.",
        tool_names=_names(SCHEMATIC_READ_SCHEMA),
    ),
    CapabilityGroup(
        id="schematic-editing",
        title="Schematic editing",
        description="Create and modify schematic symbols, wires, labels, junctions, and buses.",
        tool_names=_names(SCHEMATIC_WRITE_SCHEMA),
    ),
    CapabilityGroup(
        id="pcb-inspection",
        title="PCB inspection",
        description="Inspect board structure, footprints, nets, connectivity, and design rules.",
        tool_names=_names(PCB_READ_TOOLS_SCHEMA),
    ),
    CapabilityGroup(
        id="pcb-editing",
        title="PCB editing",
        description="Create and modify boards, footprints, routing, zones, and outlines.",
        tool_names=_names(PCB_WRITE_TOOLS_SCHEMA),
    ),
)

CAPABILITY_GROUPS_BY_ID: Mapping[str, CapabilityGroup] = MappingProxyType(
    {group.id: group for group in CAPABILITY_GROUPS}
)

_catalog_tool_names = _names(
    SESSION_TOOLS_SCHEMA,
    TIER2_TOOLS_SCHEMA,
    ALL_TOOLS_SCHEMA,
)

MCP_TOOL_CATALOG: Mapping[str, Any] = MappingProxyType(
    {
        "version": CATALOG_VERSION,
        "groups": CAPABILITY_GROUPS,
        "tool_names": _catalog_tool_names,
    }
)


def get_capability_groups() -> Tuple[CapabilityGroup, ...]:
    """Return all capability groups in stable catalog order."""
    return CAPABILITY_GROUPS


def get_capability_group(group_id: str) -> CapabilityGroup:
    """Return one capability group or raise ``KeyError`` for an unknown ID."""
    return CAPABILITY_GROUPS_BY_ID[group_id]


def get_tool_catalog() -> Dict[str, Any]:
    """Return a JSON-serializable snapshot of the stable tool catalog."""
    return {
        "version": CATALOG_VERSION,
        "groups": [group.as_dict() for group in CAPABILITY_GROUPS],
        "tool_names": list(_catalog_tool_names),
    }


__all__ = [
    "CATALOG_VERSION",
    "MCP_TOOL_CATALOG_VERSION",
    "CapabilityGroup",
    "CAPABILITY_GROUPS",
    "CAPABILITY_GROUPS_BY_ID",
    "MCP_TOOL_CATALOG",
    "get_capability_groups",
    "get_capability_group",
    "get_tool_catalog",
]
