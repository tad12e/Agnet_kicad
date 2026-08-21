import anthropic
import json
from .tools import (
    get_board_state, place_component, 
    add_trace, run_drc
)
from .simulation import run_ngspice_simulation as run_simulation

# ── Tool definitions sent to Claude ──────────────────────────────

TOOLS = [
    {
        "name": "get_board_state",
        "description": "Read the current PCB board state — all components, nets, and unconnected count. ALWAYS call this first before making any changes.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "place_component",
        "description": "Place a footprint on the PCB board at a specific position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ref":            {"type": "string", "description": "Reference designator e.g. R1, C1, U1"},
                "value":          {"type": "string", "description": "Component value e.g. 10k, 100nF"},
                "footprint_lib":  {"type": "string", "description": "Library folder e.g. Resistor_SMD.pretty"},
                "footprint_name": {"type": "string", "description": "Footprint e.g. R_0402, C_0402"},
                "x":              {"type": "number", "description": "X position in mm"},
                "y":              {"type": "number", "description": "Y position in mm"}
            },
            "required": ["ref", "value", "footprint_lib", "footprint_name", "x", "y"]
        }
    },
    {
        "name": "add_trace",
        "description": "Draw a copper trace between two points on the PCB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x1": {"type": "number"}, "y1": {"type": "number"},
                "x2": {"type": "number"}, "y2": {"type": "number"},
                "width_mm": {"type": "number", "description": "Trace width in mm, default 0.25"}
            },
            "required": ["x1", "y1", "x2", "y2"]
        }
    },
    {
        "name": "run_drc",
        "description": "Run Design Rule Check. Returns unconnected pads and errors. Call after placing components.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "run_simulation",
        "description": "Run ngspice SPICE simulation on a netlist file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "netlist_path": {"type": "string", "description": "Full path to .cir netlist file"},
                "analysis":     {"type": "string", "description": "SPICE analysis e.g. .ac dec 100 1 1Meg"}
            },
            "required": ["netlist_path"]
        }
    }
]

SYSTEM_PROMPT = """You are an expert KiCad PCB design agent with deep knowledge of electronics engineering.

You can place components, route traces, run DRC checks, and simulate circuits using ngspice.

## Rules
1. ALWAYS call get_board_state first to understand what's already on the board
2. Place components with minimum 5mm spacing between them
3. Start component placement at x=100, y=100 and increment by 10mm
4. After placing components, ALWAYS run run_drc to verify
5. Never place a component at the same position as an existing one
6. For resistors use: footprint_lib="Resistor_SMD.pretty", footprint_name="R_0402"
7. For capacitors use: footprint_lib="Capacitor_SMD.pretty", footprint_name="C_0402"

## On tool call errors
If a tool returns an ERROR string, stop and report it to the user. Do not retry blindly.

## Communication style
After completing all tool calls, give a brief summary of what was done in plain English.
Include component values, positions, and any DRC results.
"""

# ── Tool dispatcher ───────────────────────────────────────────────

TOOL_MAP = {
    "get_board_state": lambda args: get_board_state(),
    "place_component": lambda args: place_component(**args),
    "add_trace":       lambda args: add_trace(**args),
    "run_drc":         lambda args: run_drc(),
    "run_simulation":  lambda args: run_simulation(**args),
}

def dispatch(tool_name: str, tool_input: dict) -> str:
    if tool_name not in TOOL_MAP:
        return f"Unknown tool: {tool_name}"
    try:
        return str(TOOL_MAP[tool_name](tool_input))
    except Exception as e:
        return f"Tool error: {e}"

# ── Agent loop ────────────────────────────────────────────────────

def run_agent(user_message: str, on_tool_call=None, on_response=None, model: str = "claude-3-7-sonnet-20250219"):
    """
    Run the agent loop for a single user message.
    
    Args:
        user_message: Natural language instruction from user
        on_tool_call: optional callback(tool_name, args, result) for UI updates
        on_response: optional callback(text) when agent finishes
        model: Claude model identifier
    """
    client = anthropic.Anthropic()
    
    messages = [{"role": "user", "content": user_message}]
    
    while True:
        response = client.messages.create(
            model=model,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )
        
        messages.append({
            "role": "assistant",
            "content": response.content
        })
        
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    if on_response:
                        on_response(block.text)
                    return block.text
            return ""
        
        if response.stop_reason == "tool_use":
            tool_results = []
            
            for block in response.content:
                if block.type == "tool_use":
                    result = dispatch(block.name, block.input)
                    
                    if on_tool_call:
                        on_tool_call(block.name, block.input, result)
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            
            messages.append({
                "role": "user",
                "content": tool_results
            })
