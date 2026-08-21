"""AI Agent layer — circuit planning and natural language interpretation.

This package will contain:
- agent.py: Main agent loop that interprets user requests
- planner/: Circuit planner that converts intent to structured plans

The agent knows about circuits and components but does NOT know about
protobuf, IPC sockets, or KiCad internals. It calls the high-level
kicad_api.schematic API.

Status: STUB — not yet implemented.
"""
