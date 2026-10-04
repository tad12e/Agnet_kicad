"""MCP (Model Context Protocol) server for the KiCad AI agent.

Exposes the agent's PCB and schematic tools to external AI models over
stdio. External models act only through these tools - they never write
S-expressions or touch design files directly.
"""
