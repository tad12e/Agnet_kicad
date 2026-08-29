"""KiCad plugin agent loop adapter using kicad_agent."""

import json
from kicad_agent.providers.llm import AnthropicProvider
from kicad_agent.verification.simulation import run_ngspice_simulation as run_simulation
from .tools import (
    get_board_state, place_component,
    add_trace, run_drc,
)

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
                "analysis":     {"type": "string", "description": "SPICE analysis e.g. .tran 1us 1ms"}
            },
            "required": ["netlist_path"]
        }
    }
]

SYSTEM_PROMPT = """You are an expert KiCad PCB design agent with deep knowledge of electronics engineering.
You can place components, route traces, run DRC checks, and simulate circuits using ngspice.
"""

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

def run_agent(user_message: str, on_tool_call=None, on_response=None, model: str = "claude-3-7-sonnet-20250219"):
    provider = AnthropicProvider()
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = provider.generate_response(
            messages=messages,
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT,
            model=model,
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
