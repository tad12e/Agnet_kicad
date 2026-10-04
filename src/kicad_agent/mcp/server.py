"""KiCad AI agent MCP server (stdio transport).

External AI models connect over stdin/stdout and operate only through
the tool schemas below - every write runs through the agent's own
backends, never through model-written S-expressions.

Usage:
    python -m kicad_agent.mcp.server [--backend sexpr|ipc|auto]
                                     [--sch FILE] [--pcb FILE]

Tools: 5 session tools (open/save/info), 18 PCB primitives, 12
schematic primitives, and run_design_task (Tier 2 whole-job agent).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict, List, Optional

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from ..agent.tools import ALL_TOOLS_SCHEMA
from .session import SERVER_TOOLS_SCHEMA, TIER2_TOOLS_SCHEMA, MCPSession

SERVER_NAME = "kicad-agent"


def all_tool_definitions() -> List[Dict[str, Any]]:
    """Every tool the server exposes, in listing order."""
    return SERVER_TOOLS_SCHEMA + ALL_TOOLS_SCHEMA


def build_server(session: MCPSession) -> Server:
    server = Server(SERVER_NAME)

    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["input_schema"],
            )
            for t in all_tool_definitions()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        result = session.dispatch(name, arguments or {})
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]

    return server


async def serve(session: MCPSession) -> None:
    server = build_server(session)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def create_session(
    backend: str = "sexpr",
    sch: Optional[str] = None,
    pcb: Optional[str] = None,
    socket_path: Optional[str] = None,
) -> MCPSession:
    session = MCPSession(mode=backend, socket_path=socket_path)
    if sch:
        opened = session.open_schematic(sch)
        if opened.get("status") != "success":
            raise SystemExit(f"Cannot open schematic: {opened.get('message')}")
    if pcb:
        opened = session.open_pcb(pcb)
        if opened.get("status") != "success":
            raise SystemExit(f"Cannot open board: {opened.get('message')}")
    return session


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="KiCad AI agent MCP server (stdio).")
    parser.add_argument(
        "--backend", default="sexpr", choices=("sexpr", "ipc", "auto"),
        help="sexpr: files only; ipc: live KiCad lanes with file fallback; "
             "auto: live when KiCad's socket exists, else files only.",
    )
    parser.add_argument("--sch", default=None, help="Pre-open a .kicad_sch file.")
    parser.add_argument("--pcb", default=None, help="Pre-open a .kicad_pcb file.")
    parser.add_argument("--socket", default=None, help="Override the KiCad IPC socket path.")
    args = parser.parse_args(argv)
    session = create_session(args.backend, args.sch, args.pcb, args.socket)
    asyncio.run(serve(session))


if __name__ == "__main__":
    main()
