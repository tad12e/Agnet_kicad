"""Client-side representation of a net (electrical connection).

C++ context:
    In KiCad's Eeschema, connectivity is managed by the CONNECTION_GRAPH
    (defined in eeschema/connection_graph.h). It builds a graph of
    SCH_CONNECTION objects that group connected pins/wires into nets.

    A "net" is identified by name (e.g., "GND", "Net-(R1-Pad2)") and
    contains references to all connected items.

    This is a FUTURE stub — net inspection will be implemented when
    we add the GetSchematicNetlist IPC command.
"""

from __future__ import annotations

from typing import List


class Net:
    """Represents an electrical net (group of connected pins/wires).

    Attributes:
        name: Net name (e.g., "GND", "VCC", "Net-(R1-Pad2)").
        pins: List of (component_ref, pin_number) tuples on this net.
    """

    def __init__(
        self,
        name: str,
        pins: List[tuple] | None = None,
    ):
        self.name = name
        self.pins = pins or []

    def __repr__(self) -> str:
        return f"Net(name={self.name!r}, pins={len(self.pins)})"
