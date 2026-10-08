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
from ..providers.llm import LLMProvider

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
    {
        "name": "start_llm_task",
        "description": "Start an iterative LLM-driven KiCad task and return its session, trace, and current status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Plain-English KiCad task"},
                "domain": {"type": "string", "description": "'schematic' or 'pcb'"},
                "max_steps": {"type": "integer", "description": "Maximum provider/tool turns"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "llm_session_info",
        "description": "Inspect the active iterative LLM task session.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "resolve_llm_approval",
        "description": "Approve or deny the pending high-risk LLM tool call and continue the same session.",
        "input_schema": {
            "type": "object",
            "properties": {
                "approved": {"type": "boolean"},
            },
            "required": ["approved"],
        },
    },
    {
        "name": "cancel_llm_task",
        "description": "Request cooperative cancellation of the active iterative LLM task.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "save_llm_session",
        "description": "Persist the active iterative LLM conversation to a JSON snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "load_llm_session",
        "description": "Restore an iterative LLM conversation from a JSON snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "domain": {"type": "string"},
            },
            "required": ["path"],
        },
    },
]

TIER2_TOOLS_SCHEMA = [
    {
        "name": "run_design_task",
        "description": "Give the iterative LLM agent a whole design job in plain English (e.g. 'add a power LED with a 1k series resistor'). It can inspect, act, verify, recover, and pause for approval.",
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

    def __init__(
        self,
        mode: str = "sexpr",
        socket_path: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
    ):
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
        self.llm_agent = None
        self.llm_domain: Optional[str] = None
        self.llm_provider = provider

    def _new_llm_agent(self, backend: KiCadBackend):
        from ..agent.agent import KiCadAgent
        from ..providers.factory import configured_provider

        provider = self.llm_provider
        if provider is None:
            provider = configured_provider()
            if provider is None:
                raise RuntimeError(
                    "No LLM provider configured and ANTHROPIC_API_KEY is unset."
                )
        return KiCadAgent(backend=backend, provider=provider)

    def _llm_backend(self, domain: str) -> KiCadBackend:
        if domain == "schematic":
            if not self.sch_path:
                raise ValueError("No schematic open. Call open_schematic first.")
            return self.sch_backend
        if domain == "pcb":
            if not self.pcb_path:
                raise ValueError("No board open. Call open_pcb first.")
            return self.pcb_backend
        raise ValueError("Domain must be 'schematic' or 'pcb'.")

    def start_llm_task(
        self,
        task: str,
        domain: str = "schematic",
        max_steps: int = 20,
    ) -> Dict[str, Any]:
        if not task.strip():
            return {"status": "error", "code": "MISSING_ARGUMENT",
                    "message": "start_llm_task requires a non-empty 'task'"}
        domain = (domain or "schematic").lower()
        try:
            backend = self._llm_backend(domain)
            self.llm_agent = self._new_llm_agent(backend)
            self.llm_domain = domain
            return self.llm_agent.run_llm(task, domain=domain, max_steps=max_steps)
        except RuntimeError as exc:
            return {"status": "error", "code": "NO_PROVIDER",
                    "message": str(exc)}
        except (ValueError, TypeError) as exc:
            return {"status": "error", "code": "BAD_REQUEST", "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "code": "AGENT_FAILED",
                    "message": f"LLM task failed: {exc}"}

    def llm_session_info(self) -> Dict[str, Any]:
        if self.llm_agent is None:
            return {"status": "error", "code": "NO_ACTIVE_LLM_SESSION",
                    "message": "No iterative LLM task is active."}
        session = self.llm_agent.state.session
        return {
            "status": "success",
            "session_id": session.session_id,
            "domain": session.domain,
            "session_status": session.status,
            "message_count": len(session.messages),
            "metadata": session.metadata,
        }

    def resolve_llm_approval(self, approved: bool) -> Dict[str, Any]:
        if self.llm_agent is None:
            return {"status": "error", "code": "NO_ACTIVE_LLM_SESSION",
                    "message": "No iterative LLM task is active."}
        try:
            return self.llm_agent.resolve_llm_approval(approved)
        except ValueError as exc:
            return {"status": "error", "code": "BAD_SESSION_STATE",
                    "message": str(exc)}

    def cancel_llm_task(self) -> Dict[str, Any]:
        if self.llm_agent is None:
            return {"status": "error", "code": "NO_ACTIVE_LLM_SESSION",
                    "message": "No iterative LLM task is active."}
        try:
            return self.llm_agent.cancel_llm()
        except ValueError as exc:
            return {"status": "error", "code": "BAD_SESSION_STATE",
                    "message": str(exc)}

    def save_llm_session(self, path: str) -> Dict[str, Any]:
        if self.llm_agent is None:
            return {"status": "error", "code": "NO_ACTIVE_LLM_SESSION",
                    "message": "No iterative LLM task is active."}
        if not path:
            return {"status": "error", "code": "MISSING_ARGUMENT",
                    "message": "save_llm_session requires 'path'"}
        try:
            saved = self.llm_agent.save_llm_session(path)
            return {"status": "success", "path": saved,
                    "session_id": self.llm_agent.state.session.session_id}
        except Exception as exc:
            return {"status": "error", "code": "SESSION_SAVE_FAILED",
                    "message": str(exc)}

    def load_llm_session(self, path: str, domain: str = "schematic") -> Dict[str, Any]:
        if not path:
            return {"status": "error", "code": "MISSING_ARGUMENT",
                    "message": "load_llm_session requires 'path'"}
        domain = (domain or "schematic").lower()
        try:
            backend = self._llm_backend(domain)
            self.llm_agent = self._new_llm_agent(backend)
            self.llm_domain = domain
            session = self.llm_agent.load_llm_session(path)
            return {"status": "success", "session": session.to_dict()}
        except RuntimeError as exc:
            return {"status": "error", "code": "NO_PROVIDER",
                    "message": str(exc)}
        except (ValueError, TypeError) as exc:
            return {"status": "error", "code": "BAD_REQUEST", "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "code": "SESSION_LOAD_FAILED",
                    "message": str(exc)}

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
        if tool_name == "start_llm_task":
            return self.start_llm_task(
                str(args.get("task", "") or ""),
                str(args.get("domain", "schematic") or "schematic"),
                int(args.get("max_steps", 20) or 20),
            )
        if tool_name == "llm_session_info":
            return self.llm_session_info()
        if tool_name == "resolve_llm_approval":
            if "approved" not in args:
                return {"status": "error", "code": "MISSING_ARGUMENT",
                        "message": "resolve_llm_approval requires 'approved'"}
            return self.resolve_llm_approval(bool(args["approved"]))
        if tool_name == "cancel_llm_task":
            return self.cancel_llm_task()
        if tool_name == "save_llm_session":
            return self.save_llm_session(str(args.get("path", "") or ""))
        if tool_name == "load_llm_session":
            return self.load_llm_session(
                str(args.get("path", "") or ""),
                str(args.get("domain", "schematic") or "schematic"),
            )
        if tool_name == "run_design_task":
            from .tier2 import run_design_task

            return run_design_task(
                self, str(args.get("task", "") or ""),
                str(args.get("domain", "schematic") or "schematic"),
            )
        try:
            if tool_name in SCHEMATIC_TOOL_NAMES:
                if tool_name not in ("search_symbols",) and not self.sch_path:
                    return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                            "message": "No schematic open. Call open_schematic first."}
                return self.sch_tools.execute_tool(tool_name, args)
            return self.pcb_tools.execute_tool(tool_name, args)
        except Exception as e:  # never leak a traceback over the wire
            return {"status": "error", "code": "TOOL_FAILED",
                    "message": f"{tool_name} failed: {e}"}
