"""MCP server session: backend wiring, open-document state, tool dispatch.

One MCPSession lives for the whole stdio server process. It holds the
PCB and schematic backends (live IPC lanes with S-expression file
fallback, or pure file mode) plus the currently opened design files,
and routes every tool call to the right ToolRegistry.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..agent.tools import (
    ALL_TOOLS_SCHEMA,
    SCHEMATIC_READ_SCHEMA,
    SCHEMATIC_WRITE_SCHEMA,
    ToolRegistry,
)
from ..backends.base import KiCadBackend
from ..backends.ipc import IPCBackend
from ..backends.ipc_pcb import IPCPCBBackend
from ..backends.sexpr import SexprBackend
from ..core.actions import Action, ActionDomain, ActionType

SCHEMATIC_TOOL_NAMES = frozenset(
    t["name"] for t in SCHEMATIC_READ_SCHEMA + SCHEMATIC_WRITE_SCHEMA
)

SESSION_TOOLS_SCHEMA = [
    {
        "name": "open_schematic",
        "description": "Open a .kicad_sch file as the active schematic for later tool calls. In live (IPC) mode, open the same file in KiCad so reads and writes hit the same document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the .kicad_sch file"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "open_pcb",
        "description": "Open a .kicad_pcb file as the active board for later tool calls. In live (IPC) mode, open the same file in KiCad so reads and writes hit the same document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the .kicad_pcb file"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "save_schematic",
        "description": "Save the active schematic. In file mode every write is already on disk, so this is a no-op confirmation. In live mode it saves the open KiCad document.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "save_pcb",
        "description": "Save the active board. In file mode every write is already on disk, so this is a no-op confirmation. In live mode it saves the open KiCad document.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "session_info",
        "description": "Show the server session: backend mode, live/IPC availability, and which schematic/board files are open.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

TIER2_TOOLS_SCHEMA = [
    {
        "name": "run_design_task",
        "description": "Give the built-in agent a whole design job in plain English (e.g. 'add a power LED with a 1k series resistor'). The agent plans, executes, verifies, and repairs on its own. Requires an Anthropic API key on the server.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Plain-English design task"},
                "domain": {"type": "string", "description": "'schematic' (default) or 'pcb'"},
            },
            "required": ["task"],
        },
    },
]

SERVER_TOOLS_SCHEMA = SESSION_TOOLS_SCHEMA + TIER2_TOOLS_SCHEMA


def _ipc_socket_present(socket_path: Optional[str] = None) -> bool:
    """True when KiCad's IPC socket exists (API server listening)."""
    if socket_path:
        candidate = socket_path
    else:
        try:
            from ..ipc.connection import default_socket_path

            candidate = default_socket_path()
        except Exception:
            return False
    path = candidate[6:] if candidate.startswith("ipc://") else candidate
    return os.path.exists(path)


class MCPSession:
    """Backend handles, open documents, and tool routing for the server."""

    def __init__(self, mode: str = "sexpr", socket_path: Optional[str] = None):
        """mode: 'sexpr' (files only), 'ipc' (live lanes with file fallback),
        'auto' (live lanes when KiCad's socket exists, else files only)."""
        self.mode = mode
        self.socket_path = socket_path
        self.sch_path: Optional[str] = None
        self.pcb_path: Optional[str] = None

        # One shared file backend: holds open-document state for both
        # domains and serves as the fallback for both IPC lanes.
        self.file_backend = SexprBackend()
        if mode == "ipc" or (mode == "auto" and _ipc_socket_present(socket_path)):
            self.live = True
            self.sch_backend: KiCadBackend = IPCBackend(
                socket_path=socket_path, fallback=self.file_backend
            )
            self.pcb_backend: KiCadBackend = IPCPCBBackend(
                socket_path=socket_path, fallback=self.file_backend
            )
        else:
            self.live = False
            self.sch_backend = self.pcb_backend = self.file_backend

        self.sch_tools = ToolRegistry(self.sch_backend)
        self.pcb_tools = ToolRegistry(self.pcb_backend)

    # -- documents ------------------------------------------------------

    def open_schematic(self, path: str) -> Dict[str, Any]:
        resolved = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(resolved):
            return {"status": "error", "code": "FILE_NOT_FOUND",
                    "message": f"Schematic file not found: {path}"}
        if not resolved.lower().endswith(".kicad_sch"):
            return {"status": "error", "code": "WRONG_FILE_TYPE",
                    "message": f"Not a .kicad_sch file: {path}"}
        self.sch_path = resolved
        self.file_backend.load_schematic(resolved)
        if self.sch_backend is not self.file_backend:
            try:
                self.sch_backend.load_schematic(resolved)
            except Exception:
                pass  # lane targets the live KiCad document instead
        result: Dict[str, Any] = {"status": "success", "file": resolved}
        if self.live:
            result["warning"] = (
                "Live mode: open the same file in KiCad so reads and "
                "writes hit the same document."
            )
        return result

    def open_pcb(self, path: str) -> Dict[str, Any]:
        resolved = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(resolved):
            return {"status": "error", "code": "FILE_NOT_FOUND",
                    "message": f"Board file not found: {path}"}
        if not resolved.lower().endswith(".kicad_pcb"):
            return {"status": "error", "code": "WRONG_FILE_TYPE",
                    "message": f"Not a .kicad_pcb file: {path}"}
        self.pcb_path = resolved
        self.file_backend.load_board(resolved)
        if self.pcb_backend is not self.file_backend:
            try:
                self.pcb_backend.load_board(resolved)
            except Exception:
                pass  # lane targets the live KiCad document instead
        result = {"status": "success", "file": resolved}
        if self.live:
            result["warning"] = (
                "Live mode: open the same file in KiCad so reads and "
                "writes hit the same document."
            )
        return result

    def save_schematic(self) -> Dict[str, Any]:
        if not self.sch_path:
            return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                    "message": "No schematic open. Call open_schematic first."}
        if not self.live:
            return {"status": "success", "file": self.sch_path,
                    "message": "File backend writes in place; nothing left to save."}
        act = Action(action_type=ActionType.SAVE_DOCUMENT, domain=ActionDomain.SCHEMATIC)
        res = self.sch_backend.execute(act)
        return {"status": "success" if res.success else "error",
                "file": self.sch_path, "data": res.data,
                "error": str(res.error) if res.error else None}

    def save_pcb(self) -> Dict[str, Any]:
        if not self.pcb_path:
            return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                    "message": "No board open. Call open_pcb first."}
        if not self.live:
            return {"status": "success", "file": self.pcb_path,
                    "message": "File backend writes in place; nothing left to save."}
        act = Action(action_type=ActionType.SAVE_DOCUMENT, domain=ActionDomain.PCB)
        res = self.pcb_backend.execute(act)
        return {"status": "success" if res.success else "error",
                "file": self.pcb_path, "data": res.data,
                "error": str(res.error) if res.error else None}

    def session_info(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "mode": self.mode,
            "live": self.live,
            "ipc_socket_present": _ipc_socket_present(self.socket_path),
            "schematic": self.sch_path,
            "pcb": self.pcb_path,
        }

    # -- dispatch -------------------------------------------------------

    def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Route one tool call; every path returns a JSON-safe envelope."""
        args = dict(arguments or {})
        if tool_name == "open_schematic":
            if not args.get("path"):
                return {"status": "error", "code": "MISSING_ARGUMENT",
                        "message": "open_schematic requires 'path'"}
            return self.open_schematic(str(args["path"]))
        if tool_name == "open_pcb":
            if not args.get("path"):
                return {"status": "error", "code": "MISSING_ARGUMENT",
                        "message": "open_pcb requires 'path'"}
            return self.open_pcb(str(args["path"]))
        if tool_name == "save_schematic":
            return self.save_schematic()
        if tool_name == "save_pcb":
            return self.save_pcb()
        if tool_name == "session_info":
            return self.session_info()
        if tool_name == "run_design_task":
            from .tier2 import run_design_task

            return run_design_task(
                self, str(args.get("task", "") or ""),
                str(args.get("domain", "schematic") or "schematic"),
            )
        if tool_name == "verify_schematic_connectivity":
            if not self.sch_path:
                return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                        "message": "No schematic open. Call open_schematic first."}
            from ..schematic.pin_geometry import endpoint_report
            with open(self.sch_path, "r", encoding="utf-8", errors="ignore") as f:
                report = endpoint_report(f.read())
            return {
                "status": "success",
                "connected": not report["errors"],
                "errors": report["errors"],
                "warnings": [w["message"] for w in report["warnings"]],
            }
        try:
            if tool_name in SCHEMATIC_TOOL_NAMES:
                if tool_name not in ("search_symbols",) and not self.sch_path:
                    return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                            "message": "No schematic open. Call open_schematic first."}
                result = self.sch_tools.execute_tool(tool_name, args)
                if tool_name == "get_schematic_state" and result.get("status") == "success":
                    result["schematic"] = result.pop("data", {})
                return result
            if tool_name not in {
                t["name"] for t in self.pcb_tools.get_available_tools("pcb")
            }:
                return {"status": "error", "code": "UNKNOWN_TOOL",
                        "message": f"Unknown tool: {tool_name}"}
            return self.pcb_tools.execute_tool(tool_name, args)
        except Exception as e:  # never leak a traceback over the wire
            return {"status": "error", "code": "TOOL_FAILED",
                    "message": f"{tool_name} failed: {e}"}
