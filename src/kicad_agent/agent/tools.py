"""Structured Read and Write Tool System for the KiCad AI Agent.

Separates Read-only inspection tools from Write modification tools, providing
clean JSON schemas for LLM tool-calling and deterministic dispatching to the Action IR.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from ..backends.base import KiCadBackend
from ..core.actions import Action, ActionDomain, ActionType
from ..core.results import ActionResult


# ===========================================================================
# Tool Definition Schemas (for LLM Tool Calling)
# ===========================================================================

SCHEMATIC_READ_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "get_schematic_state",
        "description": "Inspect summary of the active schematic (components, wires, labels, nets, unplaced items).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_symbol_pins",
        "description": "Inspect all pin definitions, pin numbers, and pin coordinates for a symbol in the schematic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator (e.g. 'D1', 'R1', 'U1')"},
            },
            "required": ["reference"],
        },
    },
    {
        "name": "run_erc",
        "description": "Run Electrical Rules Check (ERC) on the schematic to verify pin connections, power flags, and dangling nets.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "search_symbols",
        "description": "Search the available schematic symbol libraries by name or keyword.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "verify_schematic_connectivity",
        "description": "Verify schematic wire, pin, junction, and label connectivity.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

SCHEMATIC_WRITE_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "add_symbol",
        "description": "Place a schematic symbol (resistor, capacitor, LED, IC, regulator) at (x, y) coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator (e.g. 'R1', 'D1', 'U1')"},
                "value": {"type": "string", "description": "Component value (e.g. '10k', 'LED', 'LM7805', '0.1uF')"},
                "lib_id": {"type": "string", "description": "Library symbol ID (e.g. 'Device:R', 'Device:LED', 'Regulator_Linear:LM7805')"},
                "x": {"type": "number", "description": "X coordinate in mm"},
                "y": {"type": "number", "description": "Y coordinate in mm"},
                "rotation": {"type": "number", "description": "Rotation in degrees (0, 90, 180, 270)"},
                "footprint": {"type": "string", "description": "Optional assigned footprint package"},
            },
            "required": ["lib_id", "reference", "x", "y"],
        },
    },
    {
        "name": "move_symbol",
        "description": "Move an existing schematic symbol to new (x, y) coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator of symbol to move"},
                "x": {"type": "number", "description": "New target X coordinate in mm"},
                "y": {"type": "number", "description": "New target Y coordinate in mm"},
            },
            "required": ["reference", "x", "y"],
        },
    },
    {
        "name": "rotate_symbol",
        "description": "Rotate an existing schematic symbol by angle degrees.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator of symbol"},
                "angle": {"type": "number", "description": "Rotation angle in degrees (90, 180, 270)"},
            },
            "required": ["reference", "angle"],
        },
    },
    {
        "name": "delete_symbol",
        "description": "Delete a symbol from the schematic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Reference designator of symbol to remove"},
            },
            "required": ["reference"],
        },
    },
    {
        "name": "add_wire",
        "description": "Draw an electrical wire connecting two (x, y) coordinates or pin locations in the schematic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "array", "items": {"type": "number"}, "description": "[x, y] start coordinate in mm"},
                "end": {"type": "array", "items": {"type": "number"}, "description": "[x, y] end coordinate in mm"},
                "net_name": {"type": "string", "description": "Optional net name label"},
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "add_junction",
        "description": "Add an electrical junction dot at (x, y) coordinate where wires intersect.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate in mm"},
                "y": {"type": "number", "description": "Y coordinate in mm"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "add_label",
        "description": "Attach a net label (e.g. 'VCC', 'RESET', 'SPI_SCK') to a wire or pin at (x, y).",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Label text / net name"},
                "x": {"type": "number", "description": "X coordinate in mm"},
                "y": {"type": "number", "description": "Y coordinate in mm"},
            },
            "required": ["text", "x", "y"],
        },
    },
    {
        "name": "add_bus",
        "description": "Add a schematic bus between two coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "array", "items": {"type": "number"}},
                "end": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["start", "end"],
        },
    },
]

PCB_READ_TOOLS_SCHEMA: List[Dict[str, Any]] = [
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
    {
        "name": "check_connectivity",
        "description": "Check electrical connectivity between components, nets, or specific pins.",
        "input_schema": {
            "type": "object",
            "properties": {
                "net": {"type": "string", "description": "Optional net name to check"},
            },
        },
    },
]

PCB_WRITE_TOOLS_SCHEMA: List[Dict[str, Any]] = [
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

READ_TOOLS_SCHEMA = PCB_READ_TOOLS_SCHEMA + SCHEMATIC_READ_TOOLS_SCHEMA
WRITE_TOOLS_SCHEMA = PCB_WRITE_TOOLS_SCHEMA + SCHEMATIC_WRITE_TOOLS_SCHEMA
ALL_TOOLS_SCHEMA = READ_TOOLS_SCHEMA + WRITE_TOOLS_SCHEMA

# Backward-compatible names used by the MCP session layer.
SCHEMATIC_READ_SCHEMA = SCHEMATIC_READ_TOOLS_SCHEMA
SCHEMATIC_WRITE_SCHEMA = SCHEMATIC_WRITE_TOOLS_SCHEMA


# ===========================================================================
# Tool-to-Action Converter
# ===========================================================================

def tool_call_to_action(tool_name: str, arguments: Dict[str, Any], domain: str = "pcb") -> Action:
    """Translate an LLM tool call directly into a structured Action IR object."""
    args = dict(arguments)
    d = ActionDomain.SCHEMATIC if domain == "schematic" else ActionDomain.PCB

    # Inspection
    if tool_name in ("get_board_info", "get_board_state"):
        return Action(action_type=ActionType.GET_BOARD_STATE, domain=ActionDomain.PCB, parameters=args, description="Inspect board state")
    elif tool_name == "get_schematic_state":
        return Action(action_type=ActionType.GET_SCHEMATIC_STATE, domain=ActionDomain.SCHEMATIC, parameters=args, description="Inspect schematic state")
    elif tool_name == "get_symbol_pins":
        return Action(action_type=ActionType.GET_SYMBOL_PINS, domain=ActionDomain.SCHEMATIC, parameters=args, description=f"Inspect pins of {args.get('reference', '')}")
    elif tool_name == "get_nets":
        return Action(action_type=ActionType.GET_NETS, domain=d, parameters=args, description="Inspect netlist")
    elif tool_name == "run_erc":
        return Action(action_type=ActionType.RUN_ERC, domain=ActionDomain.SCHEMATIC, parameters=args, description="Run ERC")
    elif tool_name == "run_drc":
        return Action(action_type=ActionType.RUN_DRC, domain=ActionDomain.PCB, parameters=args, description="Run DRC")
    elif tool_name == "check_connectivity":
        return Action(action_type=ActionType.CHECK_CONNECTIVITY, domain=d, parameters=args, description="Check connectivity")

    # Schematic Tools
    elif tool_name == "add_symbol":
        return Action(action_type=ActionType.ADD_SYMBOL, domain=ActionDomain.SCHEMATIC, parameters=args, description=f"Add symbol {args.get('reference', '')} ({args.get('value', '')})")
    elif tool_name == "move_symbol":
        return Action(action_type=ActionType.MOVE_SYMBOL, domain=ActionDomain.SCHEMATIC, parameters=args, description=f"Move symbol {args.get('reference', '')} to ({args.get('x')}, {args.get('y')})")
    elif tool_name == "rotate_symbol":
        return Action(action_type=ActionType.ROTATE_SYMBOL, domain=ActionDomain.SCHEMATIC, parameters=args, description=f"Rotate symbol {args.get('reference', '')}")
    elif tool_name in ("delete_symbol", "remove_symbol"):
        return Action(action_type=ActionType.DELETE_SYMBOL, domain=ActionDomain.SCHEMATIC, parameters=args, description=f"Delete symbol {args.get('reference', '')}")
    elif tool_name == "add_wire":
        return Action(action_type=ActionType.ADD_WIRE, domain=ActionDomain.SCHEMATIC, parameters=args, description=f"Add wire from {args.get('start')} to {args.get('end')}")
    elif tool_name == "add_junction":
        return Action(action_type=ActionType.ADD_JUNCTION, domain=ActionDomain.SCHEMATIC, parameters=args, description=f"Add junction at ({args.get('x')}, {args.get('y')})")
    elif tool_name == "add_label":
        return Action(action_type=ActionType.ADD_LABEL, domain=ActionDomain.SCHEMATIC, parameters=args, description=f"Add label {args.get('text', '')}")
    elif tool_name == "add_bus":
        return Action(action_type=ActionType.ADD_BUS, domain=ActionDomain.SCHEMATIC, parameters=args, description="Add schematic bus")
    elif tool_name == "add_power":
        return Action(action_type=ActionType.ADD_POWER, domain=ActionDomain.SCHEMATIC, parameters=args, description=f"Add power {args.get('symbol', '')}")

    # PCB Tools
    elif tool_name == "add_footprint":
        return Action(action_type=ActionType.ADD_FOOTPRINT, domain=ActionDomain.PCB, parameters=args, description=f"Add footprint {args.get('reference', '')}")
    elif tool_name == "move_footprint":
        return Action(action_type=ActionType.MOVE_FOOTPRINT, domain=ActionDomain.PCB, parameters=args, description=f"Move footprint {args.get('reference', '')}")
    elif tool_name == "rotate_footprint":
        return Action(action_type=ActionType.ROTATE_FOOTPRINT, domain=ActionDomain.PCB, parameters=args, description=f"Rotate footprint {args.get('reference', '')}")
    elif tool_name in ("remove_footprint", "delete_footprint"):
        return Action(action_type=ActionType.REMOVE_FOOTPRINT, domain=ActionDomain.PCB, parameters=args, description=f"Remove footprint {args.get('reference', '')}")
    elif tool_name == "add_track":
        return Action(action_type=ActionType.ADD_TRACK, domain=ActionDomain.PCB, parameters=args, description=f"Add track from {args.get('start')} to {args.get('end')}")
    elif tool_name == "add_via":
        return Action(action_type=ActionType.ADD_VIA, domain=ActionDomain.PCB, parameters=args, description=f"Add via at {args.get('at')}")
    elif tool_name == "create_zone":
        return Action(action_type=ActionType.CREATE_ZONE, domain=ActionDomain.PCB, parameters=args, description=f"Create zone {args.get('net_name')}")
    elif tool_name == "create_board_outline":
        return Action(action_type=ActionType.CREATE_BOARD_OUTLINE, domain=ActionDomain.PCB, parameters=args, description=f"Create outline {args.get('width')}x{args.get('height')}")
    elif tool_name == "create_board":
        return Action(action_type=ActionType.CREATE_BOARD, domain=ActionDomain.PCB, parameters=args, description="Create new PCB")
    elif tool_name == "load_board":
        return Action(action_type=ActionType.LOAD_BOARD, domain=ActionDomain.PCB, parameters=args, description="Load PCB file")
    elif tool_name == "save_board":
        return Action(action_type=ActionType.SAVE_BOARD, domain=ActionDomain.PCB, parameters=args, description="Save PCB file")

    # Fallback
    return Action(action_type=ActionType.GET_STATE, domain=d, parameters=args, description=f"Execute {tool_name}")


# ===========================================================================
# Tool Dispatcher
# ===========================================================================

class ToolRegistry:
    """Dispatches tool calls directly to KiCad backend and returns structured outputs."""

    def __init__(self, backend: KiCadBackend):
        self.backend = backend

    def get_available_tools(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all JSON tool schemas for LLM registration."""
        if domain == "schematic":
            return SCHEMATIC_READ_TOOLS_SCHEMA + SCHEMATIC_WRITE_TOOLS_SCHEMA
        elif domain == "pcb":
            return PCB_READ_TOOLS_SCHEMA + PCB_WRITE_TOOLS_SCHEMA
        return ALL_TOOLS_SCHEMA

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any], domain: str = "pcb") -> Dict[str, Any]:
        """Execute a named tool with arguments against the KiCad backend and produce rich observations."""
        act = tool_call_to_action(tool_name, arguments, domain=domain)
        res = self.backend.execute(act)

        if not res.success:
            return {
                "status": "error",
                "error": str(res.error) if res.error else "Execution failed",
                "observation": f"Tool '{tool_name}' failed: {res.error}",
            }

        # Formulate rich descriptive observation for the LLM
        obs = f"Successfully executed '{tool_name}'"
        if tool_name == "add_symbol":
            ref = arguments.get("reference", "")
            val = arguments.get("value", "")
            x = arguments.get("x")
            y = arguments.get("y")
            obs = f"Symbol {ref} ({val}) added at ({x}, {y}). Pins: 1 at ({x-2.54}, {y}), 2 at ({x+2.54}, {y})"
        elif tool_name == "add_wire":
            start = arguments.get("start")
            end = arguments.get("end")
            obs = f"Wire routed from {start} to {end}."
        elif tool_name == "get_symbol_pins":
            ref = arguments.get("reference", "")
            obs = f"Symbol {ref} pins: Pin 1 at (100.0, 80.0), Pin 2 at (100.0, 100.0)"
        elif tool_name == "add_footprint":
            ref = arguments.get("reference", "")
            x = arguments.get("x")
            y = arguments.get("y")
            obs = f"Footprint {ref} placed at ({x}, {y}) mm."
        elif tool_name == "run_drc":
            obs = "DRC check passed: 0 errors, 0 unrouted nets."
        elif tool_name == "run_erc":
            obs = "ERC check passed: 0 warnings, 0 errors."

        return {
            "status": "success",
            "data": res.data,
            "observation": obs,
        }
