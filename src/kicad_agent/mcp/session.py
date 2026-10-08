"""MCP server session: backend wiring, open-document state, tool dispatch.

One MCPSession lives for the whole stdio server process. It holds the
PCB and schematic backends (live IPC lanes with S-expression file
fallback, or pure file mode) plus the currently opened design files,
and routes every tool call to the right ToolRegistry.
"""

from __future__ import annotations

import os
import uuid
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
from ..core.contracts import PermissionDecision, PermissionRequest, SessionStatus
from ..core.permissions import PermissionPolicy
from ..core.session_snapshot import (
    RESUMABLE_STATUSES,
    SessionSnapshot,
    SessionSnapshotStore,
    SnapshotError,
)

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
        "name": "save_session",
            "description": "Write a versioned, checksummed session snapshot to a JSON file.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Snapshot JSON path"},
                },
                "required": ["path"],
            },
    },
    {
            "name": "resume_session",
            "description": "Validate and resume a non-terminal session snapshot from a JSON file.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Snapshot JSON path"},
                },
                "required": ["path"],
            },
    },
    {
        "name": "approve_action",
            "description": "Approve or deny a pending risky action returned by a previous tool call.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["allow", "deny"]},
                },
                "required": ["request_id", "decision"],
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
        """Create a session with an explicitly selected backend policy.

        ``sexpr`` is file-only, ``ipc`` is live-only, and ``ipc-fallback``
        explicitly opts in to S-expression failover.  ``auto`` selects live
        IPC when its socket exists, but never silently changes an IPC failure
        into a file-backend operation.
        """
        if mode not in {"sexpr", "ipc", "ipc-fallback", "auto"}:
            raise ValueError(
                "mode must be one of: sexpr, ipc, ipc-fallback, auto"
            )
        self.mode = mode
        self.socket_path = socket_path
        self.sch_path: Optional[str] = None
        self.pcb_path: Optional[str] = None

        # One shared file backend: holds open-document state for both
        # domains and serves as the fallback for both IPC lanes.
        self.file_backend = SexprBackend()
        if mode in {"ipc", "ipc-fallback"} or (
            mode == "auto" and _ipc_socket_present(socket_path)
        ):
            self.live = True
            fallback = self.file_backend if mode == "ipc-fallback" else None
            self.sch_backend: KiCadBackend = IPCBackend(
                socket_path=socket_path, fallback=fallback
            )
            self.pcb_backend: KiCadBackend = IPCPCBBackend(
                socket_path=socket_path, fallback=fallback
            )
        else:
            self.live = False
            self.sch_backend = self.pcb_backend = self.file_backend

        self.sch_tools = ToolRegistry(self.sch_backend)
        self.pcb_tools = ToolRegistry(self.pcb_backend)
        self.pending_approvals: Dict[str, PermissionRequest] = {}
        self.session_id = str(uuid.uuid4())
        self.session_status = SessionStatus.PENDING

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
        self.session_status = SessionStatus.RUNNING
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
        self.session_status = SessionStatus.RUNNING
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
            action = Action(action_type=ActionType.SAVE_DOCUMENT, domain=ActionDomain.SCHEMATIC)
            permission = self.sch_tools.permission_policy.check(action)
            if permission.request:
                self.pending_approvals[permission.request.request_id] = permission.request
                return {"status": "approval_required", "code": "APPROVAL_REQUIRED",
                        "approval_request": permission.request.to_dict()}
            return {"status": "success", "file": self.sch_path,
                    "message": "File backend writes in place; nothing left to save."}
        act = Action(action_type=ActionType.SAVE_DOCUMENT, domain=ActionDomain.SCHEMATIC)
        permission = self.sch_tools.permission_policy.check(act)
        if permission.request:
            self.pending_approvals[permission.request.request_id] = permission.request
            return {"status": "approval_required", "code": "APPROVAL_REQUIRED",
                    "approval_request": permission.request.to_dict()}
        res = self.sch_backend.execute(act)
        return {"status": "success" if res.success else "error",
                "file": self.sch_path, "data": res.data,
                "error": str(res.error) if res.error else None}

    def save_pcb(self) -> Dict[str, Any]:
        if not self.pcb_path:
            return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                    "message": "No board open. Call open_pcb first."}
        if not self.live:
            action = Action(action_type=ActionType.SAVE_DOCUMENT, domain=ActionDomain.PCB)
            permission = self.pcb_tools.permission_policy.check(action)
            if permission.request:
                self.pending_approvals[permission.request.request_id] = permission.request
                return {"status": "approval_required", "code": "APPROVAL_REQUIRED",
                        "approval_request": permission.request.to_dict()}
            return {"status": "success", "file": self.pcb_path,
                    "message": "File backend writes in place; nothing left to save."}
        act = Action(action_type=ActionType.SAVE_DOCUMENT, domain=ActionDomain.PCB)
        permission = self.pcb_tools.permission_policy.check(act)
        if permission.request:
            self.pending_approvals[permission.request.request_id] = permission.request
            return {"status": "approval_required", "code": "APPROVAL_REQUIRED",
                    "approval_request": permission.request.to_dict()}
        res = self.pcb_backend.execute(act)
        return {"status": "success" if res.success else "error",
                "file": self.pcb_path, "data": res.data,
                "error": str(res.error) if res.error else None}

    def session_info(self) -> Dict[str, Any]:
        ipc_status = None
        if self.live:
            ipc_status = {
                "schematic": self.sch_backend.connection_status(),
                "pcb": self.pcb_backend.connection_status(),
            }
        return {
            "status": "success",
            "mode": self.mode,
            "live": self.live,
            "ipc_socket_present": _ipc_socket_present(self.socket_path),
            "ipc": ipc_status,
            "schematic": self.sch_path,
            "pcb": self.pcb_path,
            "pending_approvals": len(self.pending_approvals),
            "session_id": self.session_id,
            "session_status": self.session_status.value,
        }

    def save_session(self, path: str) -> Dict[str, Any]:
        if not path:
            return {"status": "error", "code": "MISSING_ARGUMENT",
                    "message": "save_session requires 'path'"}
        snapshot = SessionSnapshot(
            session_id=self.session_id,
            status=self.session_status.value,
            mode=self.mode,
            backend=self.mode,
            schematic=self.sch_path,
            pcb=self.pcb_path,
            pending_approvals={
                request_id: request.to_dict()
                for request_id, request in self.pending_approvals.items()
            },
        )
        try:
            saved = SessionSnapshotStore.save(path, snapshot)
        except (OSError, ValueError) as exc:
            return {"status": "error", "code": "SNAPSHOT_WRITE_FAILED",
                    "message": str(exc)}
        return {"status": "success", "snapshot_version": 1, **saved}

    def resume_session(self, path: str) -> Dict[str, Any]:
        if not path:
            return {"status": "error", "code": "MISSING_ARGUMENT",
                    "message": "resume_session requires 'path'"}
        try:
            snapshot = SessionSnapshotStore.load(path)
        except SnapshotError as exc:
            return {"status": "error", "code": exc.code, "message": exc.message}
        if snapshot.status not in RESUMABLE_STATUSES:
            return {
                "status": "error",
                "code": "SESSION_NOT_RESUMABLE",
                "message": f"Session status '{snapshot.status}' is terminal.",
            }
        if snapshot.schematic and not os.path.exists(snapshot.schematic):
            return {"status": "error", "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Schematic file not found: {snapshot.schematic}"}
        if snapshot.pcb and not os.path.exists(snapshot.pcb):
            return {"status": "error", "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Board file not found: {snapshot.pcb}"}
        # Validate and decode all approval records before changing this session.
        try:
            approvals = {
                request_id: PermissionRequest.from_dict(payload)
                for request_id, payload in snapshot.pending_approvals.items()
            }
        except (KeyError, TypeError, ValueError) as exc:
            return {"status": "error", "code": "SNAPSHOT_CORRUPT",
                    "message": f"Invalid approval record: {exc}"}
        try:
            if snapshot.schematic:
                opened = self.open_schematic(snapshot.schematic)
                if opened.get("status") != "success":
                    return {"status": "error", "code": "RESUME_FAILED",
                            "message": opened.get("message", "Could not open schematic.")}
            if snapshot.pcb:
                opened = self.open_pcb(snapshot.pcb)
                if opened.get("status") != "success":
                    return {"status": "error", "code": "RESUME_FAILED",
                            "message": opened.get("message", "Could not open board.")}
        except Exception as exc:
            return {"status": "error", "code": "RESUME_FAILED", "message": str(exc)}
        self.session_id = snapshot.session_id
        self.session_status = SessionStatus(snapshot.status)
        self.pending_approvals = approvals
        return {
            "status": "success",
            "snapshot_version": 1,
            "session_id": self.session_id,
            "session_status": self.session_status.value,
            "schematic": self.sch_path,
            "pcb": self.pcb_path,
            "pending_approvals": len(self.pending_approvals),
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
        if tool_name == "save_session":
            return self.save_session(str(args.get("path", "") or ""))
        if tool_name == "resume_session":
            return self.resume_session(str(args.get("path", "") or ""))
        if tool_name == "approve_action":
            request_id = str(args.get("request_id", "") or "")
            if not request_id or request_id not in self.pending_approvals:
                return {"status": "error", "code": "UNKNOWN_APPROVAL",
                        "message": "No pending approval matches request_id."}
            try:
                decision = PermissionDecision(str(args.get("decision", "")).lower())
            except ValueError:
                return {"status": "error", "code": "BAD_DECISION",
                        "message": "decision must be 'allow' or 'deny'."}
            request = self.pending_approvals.pop(request_id)
            registry = self.sch_tools if request.action.domain is ActionDomain.SCHEMATIC else self.pcb_tools
            tool_name_for_action = request.action.action_type.value
            result = registry.execute_action(request.action, approval=decision)
            if result.get("status") == "approval_required":
                self.pending_approvals[request_id] = request
            return result
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
                if result.get("status") == "approval_required":
                    request = PermissionRequest.from_dict(result["approval_request"])
                    self.pending_approvals[request.request_id] = request
                if tool_name == "get_schematic_state" and result.get("status") == "success":
                    result["schematic"] = result.pop("data", {})
                return result
            if tool_name not in {
                t["name"] for t in self.pcb_tools.get_available_tools("pcb")
            }:
                return {"status": "error", "code": "UNKNOWN_TOOL",
                        "message": f"Unknown tool: {tool_name}"}
            result = self.pcb_tools.execute_tool(tool_name, args)
            if result.get("status") == "approval_required":
                request = PermissionRequest.from_dict(result["approval_request"])
                self.pending_approvals[request.request_id] = request
            return result
        except Exception as e:  # never leak a traceback over the wire
            return {"status": "error", "code": "TOOL_FAILED",
                    "message": f"{tool_name} failed: {e}"}
