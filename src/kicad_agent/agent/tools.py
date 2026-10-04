"""Structured Read and Write Tool System for the KiCad AI Agent.

Separates Read-only inspection tools from Write modification tools, providing
clean JSON schemas for LLM tool-calling and deterministic dispatching.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from ..backends.base import KiCadBackend
from ..core.actions import Action, ActionDomain, ActionType
from ..core.results import ActionResult


# ===========================================================================
# Tool Definition Schemas (for LLM Tool Calling)
# ===========================================================================

READ_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "get_board_info",
        "description": "Inspect summary of the current PCB board (dimensions, layer stack, component counts, filename).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_footprints",
        "description": "List all component footprints on the PCB with their references, values, positions, and layers.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "find_footprint",
        "description": "Find a specific footprint on the board by reference designator (e.g. 'R1', 'U1').",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator (e.g. 'R1')"},
            },
            "required": ["reference"],
        },
    },
    {
        "name": "get_nets",
        "description": "Get all electrical net names defined on the board.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_unconnected_items",
        "description": "Get count and list of unconnected pads or unrouted ratsnest lines.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_board_outline",
        "description": "Get the board outline dimensions, bounding box, and Edge.Cuts geometry.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "run_drc",
        "description": "Run KiCad PCB Design Rule Check (DRC) to find clearance, unrouted, and constraint violations.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

WRITE_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "create_board",
        "description": "Create a new blank in-memory PCB board.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "load_board",
        "description": "Load an existing .kicad_pcb file into the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Absolute or relative path to .kicad_pcb file"},
            },
            "required": ["filepath"],
        },
    },
    {
        "name": "save_board",
        "description": "Save the current PCB board state to a .kicad_pcb file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to save .kicad_pcb file (optional if loaded)"},
            },
        },
    },
    {
        "name": "add_footprint",
        "description": "Place a new footprint on the PCB board at specified coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator (e.g. 'R1', 'C1', 'LED1')"},
                "x": {"type": "number", "description": "X position in millimeters (mm)"},
                "y": {"type": "number", "description": "Y position in millimeters (mm)"},
                "value": {"type": "string", "description": "Component value (e.g. '10k', '100nF')"},
                "component_type": {"type": "string", "description": "Type: resistor, capacitor, led, inductor, diode, ic"},
                "footprint_lib": {"type": "string", "description": "Optional KiCad footprint library (e.g. 'Resistor_SMD.pretty')"},
                "footprint_name": {"type": "string", "description": "Optional footprint model name (e.g. 'R_0402_1005Metric')"},
                "rotation": {"type": "number", "description": "Rotation in degrees (0, 90, 180, 270)"},
            },
            "required": ["reference", "x", "y"],
        },
    },
    {
        "name": "move_footprint",
        "description": "Move an existing footprint on the PCB to new (X, Y) coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator of footprint to move"},
                "x": {"type": "number", "description": "New target X coordinate in mm"},
                "y": {"type": "number", "description": "New target Y coordinate in mm"},
                "rotation": {"type": "number", "description": "Optional new rotation angle"},
            },
            "required": ["reference", "x", "y"],
        },
    },
    {
        "name": "rotate_footprint",
        "description": "Rotate an existing footprint by a specified angle in degrees.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator of footprint"},
                "angle": {"type": "number", "description": "Rotation angle in degrees (e.g. 90, 180)"},
            },
            "required": ["reference", "angle"],
        },
    },
    {
        "name": "remove_footprint",
        "description": "Delete a footprint from the PCB board.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator of footprint to remove"},
            },
            "required": ["reference"],
        },
    },
    {
        "name": "add_track",
        "description": "Route a copper track segment between two coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "array", "items": {"type": "number"}, "description": "[x, y] start coordinates in mm"},
                "end": {"type": "array", "items": {"type": "number"}, "description": "[x, y] end coordinates in mm"},
                "width_mm": {"type": "number", "description": "Track width in mm (default 0.25mm)"},
                "layer": {"type": "string", "description": "Copper layer (e.g. 'F.Cu' or 'B.Cu')"},
                "net": {"type": "integer", "description": "Net code (optional)"},
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "add_via",
        "description": "Place a via connecting top and bottom copper layers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "at": {"type": "array", "items": {"type": "number"}, "description": "[x, y] position in mm"},
                "size_mm": {"type": "number", "description": "Via outer diameter (default 0.8mm)"},
                "drill_mm": {"type": "number", "description": "Via drill hole diameter (default 0.4mm)"},
                "net": {"type": "integer", "description": "Net code (optional)"},
            },
            "required": ["at"],
        },
    },
    {
        "name": "create_zone",
        "description": "Create a copper polygon zone/pour (e.g. ground plane).",
        "input_schema": {
            "type": "object",
            "properties": {
                "polygon": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "List of [x, y] vertex coordinates in mm",
                },
                "net_name": {"type": "string", "description": "Net name (e.g. 'GND')"},
                "layer": {"type": "string", "description": "Layer (default 'F.Cu')"},
            },
            "required": ["polygon", "net_name"],
        },
    },
    {
        "name": "create_board_outline",
        "description": "Create or update the PCB boundary outline on Edge.Cuts layer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "width": {"type": "number", "description": "Board width in mm"},
                "height": {"type": "number", "description": "Board height in mm"},
                "x": {"type": "number", "description": "Origin X in mm (default 0)"},
                "y": {"type": "number", "description": "Origin Y in mm (default 0)"},
            },
            "required": ["width", "height"],
        },
    },
]

SCHEMATIC_READ_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "get_schematic_state",
        "description": "Inspect the active schematic: symbols (with position and rotation), wires, junctions, labels, sheets, and file path.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_symbol_pins",
        "description": "Pin truth for a symbol: the exact coordinates wires connect to. With 'reference', returns pin tips for a placed symbol (accounts for its position and rotation); with only 'lib_id', returns library pins at the origin. Coordinates are in mm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lib_id": {"type": "string", "description": "Library id like 'Device:R' or 'Amplifier_Operational:LM358' (optional when 'reference' is given)"},
                "reference": {"type": "string", "description": "Placed reference designator like 'R1' (requires an open schematic)"},
            },
        },
    },
    {
        "name": "search_symbols",
        "description": "Search KiCad symbol libraries by name, keywords, or description (e.g. 'opamp', 'resistor'). Returns lib_ids usable with add_symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text search query"},
                "family": {"type": "string", "description": "Optional library family filter like 'Device'"},
                "limit": {"type": "integer", "description": "Maximum results to return (default 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "verify_schematic_connectivity",
        "description": "Check the active schematic's wiring: dangling wire ends and junction-less meets are errors; unconnected pins are warnings.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

SCHEMATIC_WRITE_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "add_symbol",
        "description": "Place a symbol (component) on the active schematic at (x, y). The library definition is embedded automatically. Coordinates in mm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lib_id": {"type": "string", "description": "Library id like 'Device:R', 'Device:C', 'Amplifier_Operational:LM358'"},
                "reference": {"type": "string", "description": "Reference designator (e.g. 'R1', 'C1', 'U1') - must be unique"},
                "value": {"type": "string", "description": "Component value (e.g. '10k', '100nF', 'LM358')"},
                "x": {"type": "number", "description": "X position in mm"},
                "y": {"type": "number", "description": "Y position in mm"},
                "rotation": {"type": "number", "description": "Rotation in degrees counter-clockwise (default 0)"},
            },
            "required": ["lib_id", "reference", "x", "y"],
        },
    },
    {
        "name": "add_wire",
        "description": "Draw a wire segment on the active schematic between two points. Endpoints must land on a pin tip, junction, label, or another wire end.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "array", "items": {"type": "number"}, "description": "[x, y] start point in mm"},
                "end": {"type": "array", "items": {"type": "number"}, "description": "[x, y] end point in mm"},
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "add_junction",
        "description": "Place a junction dot on the active schematic where three or more wires meet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X position in mm"},
                "y": {"type": "number", "description": "Y position in mm"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "add_label",
        "description": "Attach a net label to the active schematic (names the electrical net at that point). Coordinates in mm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Label text / net name (e.g. 'OUT', 'VCC')"},
                "x": {"type": "number", "description": "X position in mm (must sit on a wire or pin)"},
                "y": {"type": "number", "description": "Y position in mm"},
                "label_type": {"type": "string", "description": "'local' (default), 'global', or 'hierarchical'"},
                "rotation": {"type": "number", "description": "Label rotation in degrees (default 0)"},
            },
            "required": ["text", "x", "y"],
        },
    },
    {
        "name": "add_bus",
        "description": "Draw a bus segment (thick multi-net line) on the active schematic between two points. Coordinates in mm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "array", "items": {"type": "number"}, "description": "[x, y] start point in mm"},
                "end": {"type": "array", "items": {"type": "number"}, "description": "[x, y] end point in mm"},
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "move_symbol",
        "description": "Move a placed symbol on the active schematic to new coordinates. Coordinates in mm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator of the placed symbol (e.g. 'R1')"},
                "x": {"type": "number", "description": "New X position in mm"},
                "y": {"type": "number", "description": "New Y position in mm"},
                "rotation": {"type": "number", "description": "Optional new rotation in degrees (keeps current rotation when omitted)"},
            },
            "required": ["reference", "x", "y"],
        },
    },
    {
        "name": "rotate_symbol",
        "description": "Rotate a placed symbol in place on the active schematic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator of the placed symbol (e.g. 'R1')"},
                "angle": {"type": "number", "description": "New rotation angle in degrees (e.g. 90, 180, 270)"},
            },
            "required": ["reference", "angle"],
        },
    },
    {
        "name": "delete_symbol",
        "description": "Delete a placed symbol from the active schematic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator of the symbol to remove (e.g. 'R1')"},
            },
            "required": ["reference"],
        },
    },
]

ALL_TOOLS_SCHEMA = READ_TOOLS_SCHEMA + WRITE_TOOLS_SCHEMA + SCHEMATIC_READ_SCHEMA + SCHEMATIC_WRITE_SCHEMA


# ===========================================================================
# Tool Dispatcher
# ===========================================================================

class ToolRegistry:
    """Dispatches tool calls directly to KiCad backend and returns structured outputs."""

    def __init__(self, backend: KiCadBackend):
        self.backend = backend

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Return all JSON tool schemas for LLM registration."""
        return ALL_TOOLS_SCHEMA

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a named tool with arguments against the KiCad backend."""
        # Read tools
        if tool_name == "get_board_info":
            state = self.backend.get_state("pcb")
            return {"status": "success", "board_info": state}

        elif tool_name == "list_footprints":
            state = self.backend.get_state("pcb")
            return {"status": "success", "footprints": state.get("components", [])}

        elif tool_name == "find_footprint":
            ref = arguments.get("reference", "")
            state = self.backend.get_state("pcb")
            for c in state.get("components", []):
                if isinstance(c, dict) and c.get("ref", c.get("reference")) == ref:
                    return {"status": "success", "footprint": c}
            return {"status": "error", "message": f"Footprint '{ref}' not found on board"}

        elif tool_name == "get_nets":
            state = self.backend.get_state("pcb")
            return {"status": "success", "nets": state.get("nets", [])}

        elif tool_name == "get_unconnected_items":
            state = self.backend.get_state("pcb")
            return {"status": "success", "unconnected_pads": state.get("unconnected_pads", 0)}

        elif tool_name == "get_board_outline":
            return {"status": "success", "layer": "Edge.Cuts", "boundary": "rectangular"}

        elif tool_name == "run_drc":
            act = Action(action_type=ActionType.RUN_DRC, domain=ActionDomain.PCB)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "drc": res.data, "error": str(res.error) if res.error else None}

        # Schematic read tools
        elif tool_name == "get_schematic_state":
            state = self.backend.get_state("schematic")
            if not state:
                return {"status": "error", "message": "No schematic file open"}
            return {"status": "success", "schematic": state}

        elif tool_name == "get_symbol_pins":
            from ..schematic.pin_geometry import resolve_pin_tips

            ref = str(arguments.get("reference", "") or "")
            lib_id = str(arguments.get("lib_id", "") or "")
            if ref:
                state = self.backend.get_state("schematic")
                sym = next(
                    (s for s in state.get("symbols", [])
                     if s.get("reference") == ref),
                    None,
                )
                if sym is None:
                    return {"status": "error", "message": f"Symbol '{ref}' not found in active schematic"}
                lib_id = lib_id or str(sym.get("lib_id", ""))
                tips = resolve_pin_tips(
                    lib_id,
                    float(sym.get("x_mm", 0.0)),
                    float(sym.get("y_mm", 0.0)),
                    float(sym.get("rotation", 0.0)),
                )
            elif lib_id:
                tips = resolve_pin_tips(lib_id, 0.0, 0.0, 0.0)
            else:
                return {"status": "error", "message": "Provide 'lib_id' or 'reference'"}
            if tips is None:
                return {"status": "error", "message": f"Could not resolve pins for '{lib_id or ref}': library not installed or unparsable"}
            pins = [
                {"number": num, "x": pos[0], "y": pos[1]}
                for num, pos in sorted(tips.items())
            ]
            return {"status": "success", "lib_id": lib_id, "reference": ref, "pins": pins}

        elif tool_name == "search_symbols":
            from ..schematic.symbols import SymbolResolver

            resolver = SymbolResolver.get_default()
            results = resolver.search(
                str(arguments.get("query", "")),
                family=arguments.get("family"),
            )
            limit = int(arguments.get("limit", 20) or 20)
            symbols = []
            for info in results[:limit]:
                symbols.append({
                    "lib_id": info.lib_id,
                    "name": info.name,
                    "library": info.library,
                    "description": info.description,
                    "pin_count": info.pin_count,
                    "pins": [
                        {"number": p.number, "name": p.name, "type": p.pin_type}
                        for p in info.pins
                    ],
                })
            return {"status": "success", "count": len(symbols), "symbols": symbols}

        elif tool_name == "verify_schematic_connectivity":
            from ..schematic.pin_geometry import endpoint_report

            state = self.backend.get_state("schematic")
            path = state.get("file") if isinstance(state, dict) else None
            if not path:
                return {"status": "error", "message": "No schematic file open"}
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError as e:
                return {"status": "error", "message": f"Cannot read schematic: {e}"}
            report = endpoint_report(text)
            return {
                "status": "success",
                "connected": not report["errors"],
                "errors": report["errors"],
                "warnings": report["warnings"],
                "stats": report["stats"],
            }

        # Write tools
        elif tool_name == "create_board":
            act = Action(action_type=ActionType.CREATE_BOARD, domain=ActionDomain.PCB)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "load_board":
            act = Action(action_type=ActionType.LOAD_BOARD, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "save_board":
            act = Action(action_type=ActionType.SAVE_BOARD, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "add_footprint":
            act = Action(action_type=ActionType.ADD_FOOTPRINT, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "move_footprint":
            act = Action(action_type=ActionType.MOVE_FOOTPRINT, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "rotate_footprint":
            act = Action(action_type=ActionType.ROTATE_FOOTPRINT, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "remove_footprint":
            act = Action(action_type=ActionType.REMOVE_FOOTPRINT, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "add_track":
            act = Action(action_type=ActionType.ADD_TRACK, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "add_via":
            act = Action(action_type=ActionType.ADD_VIA, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "create_zone":
            act = Action(action_type=ActionType.CREATE_ZONE, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "create_board_outline":
            act = Action(action_type=ActionType.CREATE_BOARD_OUTLINE, domain=ActionDomain.PCB, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        # Schematic write tools
        elif tool_name == "add_symbol":
            act = Action(action_type=ActionType.ADD_SYMBOL, domain=ActionDomain.SCHEMATIC, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "add_wire":
            act = Action(action_type=ActionType.ADD_WIRE, domain=ActionDomain.SCHEMATIC, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "add_junction":
            act = Action(action_type=ActionType.ADD_JUNCTION, domain=ActionDomain.SCHEMATIC, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "add_label":
            act = Action(action_type=ActionType.ADD_LABEL, domain=ActionDomain.SCHEMATIC, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "add_bus":
            act = Action(action_type=ActionType.ADD_BUS, domain=ActionDomain.SCHEMATIC, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "move_symbol":
            act = Action(action_type=ActionType.MOVE_SYMBOL, domain=ActionDomain.SCHEMATIC, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "rotate_symbol":
            act = Action(action_type=ActionType.ROTATE_SYMBOL, domain=ActionDomain.SCHEMATIC, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        elif tool_name == "delete_symbol":
            act = Action(action_type=ActionType.DELETE_SYMBOL, domain=ActionDomain.SCHEMATIC, parameters=arguments)
            res = self.backend.execute(act)
            return {"status": "success" if res.success else "error", "data": res.data, "error": str(res.error) if res.error else None}

        else:
            return {"status": "error", "message": f"Unknown tool '{tool_name}'"}
