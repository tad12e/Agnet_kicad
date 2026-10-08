"""KiCad Live IPC Backend.

Primary execution adapter communicating over NNG socket using Protocol Buffers
with KiCad 8/9/10/11+.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Optional, Tuple

try:
    from google.protobuf.any_pb2 import Any as ProtoAny
except ImportError:
    ProtoAny = None  # type: ignore[assignment,misc]

from ..core.actions import Action, ActionDomain, ActionType
from ..core.errors import AgentError, ErrorCategory
from ..core.results import ActionResult
from ..ipc.client import KiCadIPCClient
from ..ipc.exceptions import IPCRequestError
from ..ipc.messages import (
    ApiStatusCode,
    SCHEMATIC_ITEM_TYPES,
    CommitAction,
    DocumentType,
    ItemDeletionStatus,
    ItemRequestStatus,
    ItemStatusCode,
    KiCadObjectType,
    get_commit_protos,
    get_document_text_protos,
    get_editor_command_protos,
    get_item_by_id_protos,
    get_item_mutation_protos,
    get_schematic_command_protos,
    get_schematic_type_protos,
)
from .base import KiCadBackend


def _nm_to_mm(value) -> float:
    try:
        return float(value) / 1e6
    except (TypeError, ValueError):
        return 0.0


def _pos_mm(vec) -> tuple:
    return (_nm_to_mm(getattr(vec, "x_nm", 0)), _nm_to_mm(getattr(vec, "y_nm", 0)))


def _field_text(field) -> str:
    """Extract the string from a SchematicField (field.text.text)."""
    text = getattr(field, "text", None)
    value = getattr(text, "text", "")
    return str(value) if value is not None else ""


def _schematic_type_classes():
    """Lazily import vendored schematic message classes (Part 5)."""
    from proto.schematic.schematic_types_pb2 import (  # type: ignore[import]
        DirectiveLabel,
        GlobalLabel,
        HierarchicalLabel,
        Junction,
        LocalLabel,
        SchematicLine,
        SchematicSymbolInstance,
    )

    return {
        "SchematicSymbolInstance": SchematicSymbolInstance,
        "SchematicLine": SchematicLine,
        "Junction": Junction,
        "LocalLabel": LocalLabel,
        "GlobalLabel": GlobalLabel,
        "HierarchicalLabel": HierarchicalLabel,
        "DirectiveLabel": DirectiveLabel,
    }


_LINE_KIND = {1: "wire", 2: "bus", 3: "graphic"}


def summarize_schematic_item(any_msg):
    """Unpack one GetItems Any into (kind, summary dict) (Part 5).

    Returns ("unknown", {"type": type_url}) for unrecognized payloads so
    callers count rather than fabricate.
    """
    classes = _schematic_type_classes()
    type_url = any_msg.TypeName() if hasattr(any_msg, "TypeName") else ""
    short = type_url.rsplit(".", 1)[-1].rsplit("/", 1)[-1]
    cls = classes.get(short)
    if cls is None:
        return "unknown", {"type": type_url or "unrecognized"}
    msg = cls()
    try:
        if not any_msg.Unpack(msg):
            return "unknown", {"type": type_url}
    except Exception:
        return "unknown", {"type": type_url}

    item_id = getattr(getattr(msg, "id", None), "value", "") or ""
    if short == "SchematicSymbolInstance":
        lib = getattr(getattr(msg, "definition", None), "id", None)
        return "symbol", {
            "id": item_id,
            "reference": _field_text(getattr(msg, "reference_field", None)),
            "value": _field_text(getattr(msg, "value_field", None)),
            "lib_id": "%s:%s" % (
                getattr(lib, "library_nickname", ""),
                getattr(lib, "entry_name", ""),
            ),
            "x_mm": _pos_mm(getattr(msg, "position", None))[0],
            "y_mm": _pos_mm(getattr(msg, "position", None))[1],
        }
    if short == "SchematicLine":
        start = _pos_mm(getattr(msg, "start", None))
        end = _pos_mm(getattr(msg, "end", None))
        line_type = int(getattr(msg, "type", 0) or 0)
        return "wire", {
            "id": item_id,
            "kind": _LINE_KIND.get(line_type, f"type_{line_type}"),
            "start_mm": list(start),
            "end_mm": list(end),
        }
    if short == "Junction":
        x, y = _pos_mm(getattr(msg, "position", None))
        return "junction", {"id": item_id, "x_mm": x, "y_mm": y}
    # Label family: Local/Global/Hierarchical/Directive.
    kind = short.lower().replace("label", "_label")
    x, y = _pos_mm(getattr(msg, "position", None))
    return "label", {
        "id": item_id,
        "label_type": kind,
        "text": _field_text(msg),
        "x_mm": x,
        "y_mm": y,
    }


class IPCBackend(KiCadBackend):
    """Live KiCad IPC protocol backend (schematic lane, Part 6).

    Optional `fallback` (e.g. a file-targeted SexprBackend) receives any
    SCHEMATIC-domain action the live server cannot serve: connection loss,
    IPC refusal (NOT_READY/UNIMPLEMENTED on KiCad 10.0.4 schematic writes),
    or actions not yet mapped to IPC. Failover results are marked with
    data["fallback_used"]=True and backend_used "ipc-><name>". PCB-domain
    actions NEVER fail over (pcbnew owns PCB).
    """

    # Backend-level errors eligible for schematic failover.
    FAILOVER_CATEGORIES = frozenset({
        ErrorCategory.CONNECTION_ERROR,
        ErrorCategory.IPC_ERROR,
        ErrorCategory.INVALID_ACTION,
    })

    def __init__(self, client: Optional[KiCadIPCClient] = None, socket_path: Optional[str] = None,
                 fallback: Optional[KiCadBackend] = None):
        self.client = client or KiCadIPCClient(socket_path=socket_path)
        self.fallback = fallback
        self._doc_proto = None

    @property
    def name(self) -> str:
        return "ipc"

    def is_available(self) -> bool:
        try:
            return self.client.is_connected
        except Exception:
            return False

    def connection_status(self) -> Dict[str, Any]:
        try:
            status = dict(self.client.connection_status())
        except Exception as e:
            status = {
                "connected": False,
                "socket_path": getattr(self.client, "socket_path", None),
                "socket_present": False,
                "transport_available": False,
                "error": str(e),
            }
        status.update({
            "backend": self.name,
            "available": bool(status.get("connected", False)),
            "fallback": self.fallback.name if self.fallback is not None else None,
        })
        return status

    def connect(self) -> None:
        self.client.connect()

    def disconnect(self) -> None:
        self.client.close()
        self._doc_proto = None

    def _get_document(self, doc_type: int = DocumentType.DOCTYPE_SCHEMATIC):
        """Resolve the live open document of the requested type (Part 3).

        Honest-error contract: NEVER fabricates a document. Raises
        AgentError(CONNECTION_ERROR) when KiCad is unreachable, has no
        document of the requested type open, or rejects the request (e.g.
        AS_UNHANDLED when that editor frame is not open). Callers must
        handle it: `execute()` converts it to a failed ActionResult;
        `get_state()` lets it propagate so OBSERVE fails fast instead of
        reasoning about a phantom empty board.
        """
        if self._doc_proto is not None and getattr(self._doc_proto, "type", None) == doc_type:
            return self._doc_proto

        _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
        cmd = GetOpenDocuments()
        cmd.type = doc_type
        try:
            resp = self.client.send(cmd, GetOpenDocumentsResponse)
        except AgentError:
            raise
        except Exception as e:
            if (isinstance(e, IPCRequestError)
                    and e.status_code == ApiStatusCode.AS_UNHANDLED):
                hint = ("No handler: open that editor frame in KiCad "
                        "(e.g. double-click the .kicad_sch) and retry.")
            else:
                hint = ("Is KiCad running with the API server enabled "
                        "(Preferences > Plugins)?")
            raise AgentError(
                category=ErrorCategory.CONNECTION_ERROR,
                message=f"GetOpenDocuments failed: {e}. {hint}",
            ) from e

        for doc in resp.documents:
            if getattr(doc, "type", None) == doc_type:
                self._doc_proto = doc
                return doc
        if resp.documents:
            # Server answered but has no document of the requested type.
            self._doc_proto = resp.documents[0]
            return self._doc_proto

        raise AgentError(
            category=ErrorCategory.CONNECTION_ERROR,
            message=f"No open document of type {doc_type} in KiCad. "
            "Open a project with that editor frame and retry.",
        )

    def begin_commit(self, doc):
        """Open a KiCad edit commit; returns the commit id proto (Part 4).

        NOTE: ``BeginCommit`` carries no ItemHeader in KiCad 10.0 (kipy's
        ``Board.begin_commit`` sends a bare ``BeginCommit()``), so ``doc`` is
        accepted for API symmetry but never attached — doing so raises
        AttributeError: header.
        """
        BeginCommit, BeginCommitResponse, _, _ = get_commit_protos()
        cmd = BeginCommit()
        try:
            resp = self.client.send(cmd, BeginCommitResponse)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"BeginCommit failed: {e}",
            ) from e
        return resp.id

    def end_commit(self, commit_id, doc, message: str, drop: bool = False) -> None:
        """Close a commit (CMA_COMMIT) or roll it back (CMA_DROP).

        Same 10.0 note as begin_commit: ``EndCommit`` has only id/action/message,
        so no document header is (or can be) attached.
        """
        _, _, EndCommit, EndCommitResponse = get_commit_protos()
        cmd = EndCommit()
        cmd.id.CopyFrom(commit_id)
        cmd.action = CommitAction.CMA_DROP if drop else CommitAction.CMA_COMMIT
        cmd.message = message
        try:
            self.client.send(cmd, EndCommitResponse)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"EndCommit failed: {e}",
            ) from e

    def create_items(self, doc, packed_items: list):
        """Send CreateItems and VERIFY every result (Part 4).

        Raises AgentError unless the response-level status is IRS_OK, the
        created count matches the sent count, and every item status is
        ISC_OK. This kills the silent-echo "success" (server returning our
        payload with empty ids instead of erroring).
        Returns the raw CreateItemsResponse on success.
        """
        CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()
        cmd = CreateItems()
        cmd.header.document.CopyFrom(doc)
        cmd.items.extend(packed_items)
        try:
            resp = self.client.send(cmd, CreateItemsResponse)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"CreateItems failed: {e}",
            ) from e

        if resp.status != ItemRequestStatus.IRS_OK:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"CreateItems rejected (request status {resp.status}).",
            )
        if len(resp.created_items) != len(packed_items):
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"CreateItems count mismatch: sent {len(packed_items)}, "
                f"server returned {len(resp.created_items)}.",
            )
        failures = [
            r.status.error_message or f"code {r.status.code}"
            for r in resp.created_items
            if r.status.code != ItemStatusCode.ISC_OK
        ]
        if failures:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"CreateItems item failures: {'; '.join(failures)}",
            )
        return resp

    @staticmethod
    def _created_id(resp, message_type) -> str:
        """Unpack the first created item's id; "" when missing/unpackable."""
        try:
            item = message_type()
            if resp.created_items and resp.created_items[0].item.Unpack(item):
                return getattr(getattr(item, "id", None), "value", "") or ""
        except Exception:
            pass
        return ""

    def _run_commit(self, doc, message: str, fn):
        """Run fn() inside a commit; DROP on any failure (Part 7).

        10.0.4 note: schematic UpdateItems against a fresh session can hit
        server-side instability (upstream null-deref reports). Timeouts and
        refusals surface as IPC_ERROR/CONNECTION_ERROR and flow to the
        fallback backend via Part 6 routing. Priming workaround if the
        server wedges: make one manual edit + save in KiCad, then retry.
        """
        commit_id = self.begin_commit(doc)
        try:
            data = fn()
        except Exception:
            try:
                self.end_commit(commit_id, doc, "drop: " + message, drop=True)
            except Exception:
                pass
            raise
        self.end_commit(commit_id, doc, message)
        return data

    def get_items_by_id(self, doc, ids: list):
        """Fetch items by KIID strings via GetItemsById (Part 7)."""
        (GetItemsById,) = get_item_by_id_protos()
        _, GetItemsResponse, _, _, _, _ = get_item_mutation_protos()
        cmd = GetItemsById()
        cmd.header.document.CopyFrom(doc)
        for value in ids:
            kiid = cmd.items.add()
            kiid.value = value
        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"GetItemsById failed: {e}",
            ) from e
        if resp.status != ItemRequestStatus.IRS_OK:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"GetItemsById rejected (request status {resp.status}).",
            )
        return list(resp.items)

    def update_items(self, doc, packed_items: list):
        """Send UpdateItems and verify every result (Part 7)."""
        _, _, UpdateItems, UpdateItemsResponse, _, _ = get_item_mutation_protos()
        cmd = UpdateItems()
        cmd.header.document.CopyFrom(doc)
        cmd.items.extend(packed_items)
        try:
            resp = self.client.send(cmd, UpdateItemsResponse)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"UpdateItems failed: {e}",
            ) from e
        if resp.status != ItemRequestStatus.IRS_OK:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"UpdateItems rejected (request status {resp.status}).",
            )
        if len(resp.updated_items) != len(packed_items):
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"UpdateItems count mismatch: sent {len(packed_items)}, "
                f"server returned {len(resp.updated_items)}.",
            )
        failures = [
            r.status.error_message or f"code {r.status.code}"
            for r in resp.updated_items
            if r.status.code != ItemStatusCode.ISC_OK
        ]
        if failures:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"UpdateItems item failures: {'; '.join(failures)}",
            )
        return resp

    def delete_items_by_id(self, doc, ids: list):
        """Send DeleteItems and verify every id reports IDS_OK (Part 7)."""
        _, _, _, _, DeleteItems, DeleteItemsResponse = get_item_mutation_protos()
        cmd = DeleteItems()
        cmd.header.document.CopyFrom(doc)
        for value in ids:
            kiid = cmd.item_ids.add()
            kiid.value = value
        try:
            resp = self.client.send(cmd, DeleteItemsResponse)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"DeleteItems failed: {e}",
            ) from e
        if resp.status != ItemRequestStatus.IRS_OK:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"DeleteItems rejected (request status {resp.status}).",
            )
        by_id = {r.id.value: r for r in resp.deleted_items}
        failures = []
        for value in ids:
            result = by_id.get(value)
            if result is None:
                failures.append(f"{value}: no deletion record")
            elif result.status != ItemDeletionStatus.IDS_OK:
                failures.append(f"{value}: deletion status {result.status}")
        if failures:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"DeleteItems failures: {'; '.join(failures)}",
            )
        return resp

    def _resolve_symbol_id(self, doc, reference: str) -> str:
        """Map a reference designator to a live KIID via snapshot (Part 7)."""
        want = (reference or "").upper()
        for sym in self.get_schematic_snapshot(doc)["symbols"]:
            if str(sym.get("reference", "")).upper() == want:
                return sym["id"]
        raise AgentError(
            category=ErrorCategory.MISSING_OBJECT,
            message=f"Symbol '{reference}' not found in live schematic.",
        )

    # -- File operations: IPC works on LIVE open documents, never files.
    # (Part 8 honesty: these raised nothing before and did nothing.)
    def load_board(self, filepath: str) -> Dict[str, Any]:
        raise AgentError(
            category=ErrorCategory.INVALID_ACTION,
            message="IPCBackend manages the live open PCB, not files. Use "
            "PcbnewBackend/SexprBackend to load board files.",
        )

    def save_board(self, filepath: Optional[str] = None) -> bool:
        raise AgentError(
            category=ErrorCategory.INVALID_ACTION,
            message="IPCBackend cannot save files. Use PcbnewBackend/SexprBackend.",
        )

    def load_schematic(self, filepath: str) -> Dict[str, Any]:
        raise AgentError(
            category=ErrorCategory.INVALID_ACTION,
            message="IPCBackend manages the live open schematic, not files. Use "
            "SexprBackend to load schematic files.",
        )

    def save_schematic(self, filepath: Optional[str] = None) -> bool:
        raise AgentError(
            category=ErrorCategory.INVALID_ACTION,
            message="IPCBackend cannot save files. Use SexprBackend.",
        )

    def get_items(self, doc, kot_types=None):
        """List board/schematic items via GetItems (Part 5).

        kot_types must be explicit (empty filter errors on KiCad < 10.0.7).
        Raises AgentError unless the response status is IRS_OK.
        """
        GetItems, GetItemsResponse, _, _, _, _ = get_item_mutation_protos()
        cmd = GetItems()
        cmd.header.document.CopyFrom(doc)
        cmd.types.extend(list(kot_types) if kot_types else [])
        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"GetItems failed: {e}",
            ) from e
        if resp.status != ItemRequestStatus.IRS_OK:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"GetItems rejected (request status {resp.status}).",
            )
        return list(resp.items)

    def get_schematic_snapshot(self, doc) -> Dict[str, Any]:
        """Summarize live schematic symbols/wires/junctions/labels (Part 5)."""
        snapshot: Dict[str, Any] = {
            "symbols": [],
            "wires": [],
            "junctions": [],
            "labels": [],
            "unknown_items": [],
        }
        for any_msg in self.get_items(doc, SCHEMATIC_ITEM_TYPES):
            kind, summary = summarize_schematic_item(any_msg)
            if kind == "symbol":
                snapshot["symbols"].append(summary)
            elif kind == "wire":
                snapshot["wires"].append(summary)
            elif kind == "junction":
                snapshot["junctions"].append(summary)
            elif kind == "label":
                snapshot["labels"].append(summary)
            else:
                snapshot["unknown_items"].append(summary)
        return snapshot

    def get_schematic_hierarchy(self, doc) -> list:
        """Nested sheet tree via GetSchematicHierarchy (Part 5)."""
        GetHier, HierResp, _, _ = get_schematic_command_protos()

        def _sheet(node) -> Dict[str, Any]:
            # page_number is a string in KiCad's schema ("1", "2-1", ...).
            return {
                "name": getattr(node, "name", ""),
                "filename": getattr(node, "filename", ""),
                "page_number": str(getattr(node, "page_number", "") or ""),
                "children": [_sheet(c) for c in getattr(node, "children", [])],
            }

        cmd = GetHier()
        cmd.document.CopyFrom(doc)
        try:
            resp = self.client.send(cmd, HierResp)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"GetSchematicHierarchy failed: {e}",
            ) from e
        return [_sheet(s) for s in resp.top_level_sheets]

    def get_schematic_document_text(self, doc) -> str:
        """Fetch the live schematic model as S-expression text (cascade T1).

        Read-only: no commit, nothing to drop. Empty/whitespace content is
        an explicit error, never phantom text.
        """
        SaveDocumentToString, SavedDocumentResponse = get_document_text_protos()
        cmd = SaveDocumentToString()
        cmd.document.CopyFrom(doc)
        try:
            resp = self.client.send(cmd, SavedDocumentResponse)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"SaveDocumentToString failed: {e}",
            ) from e
        contents = getattr(resp, "contents", "") or ""
        if not contents.strip():
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message="Live schematic text came back empty.",
            )
        return contents

    def get_schematic_netlist(self, doc) -> list:
        """Net names via GetSchematicNetlist (Part 5)."""
        _, _, GetNetlist, NetlistResp = get_schematic_command_protos()
        cmd = GetNetlist()
        cmd.document.CopyFrom(doc)
        try:
            resp = self.client.send(cmd, NetlistResp)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"GetSchematicNetlist failed: {e}",
            ) from e
        return [
            {"name": getattr(n, "name", ""), "sheets": len(getattr(n, "sheets", []))}
            for n in resp.nets
        ]

    def get_state(self, domain: str = "pcb") -> Dict[str, Any]:
        # Raises AgentError (via _get_document) when no live document exists.
        doc_type = DocumentType.DOCTYPE_PCB if domain == "pcb" else DocumentType.DOCTYPE_SCHEMATIC
        doc = self._get_document(doc_type)
        state = {
            "board_filename": getattr(doc, "board_filename", ""),
            "project_name": getattr(doc.project, "name", "") if hasattr(doc, "project") else "",
        }
        if domain != "schematic":
            return state
        # Core read (required): failure raises, never phantom items.
        state.update(self.get_schematic_snapshot(doc))
        if self.fallback is not None and not state.get("components"):
            fallback_state = self.fallback.get_state("schematic")
            if fallback_state.get("components"):
                state.update(fallback_state)
        # Enrichment (best-effort): failures recorded explicitly per section.
        for section, reader in (
            ("sheets", self.get_schematic_hierarchy),
            ("nets", self.get_schematic_netlist),
        ):
            try:
                state[section] = reader(doc)
            except AgentError as e:
                state[section] = {"error": e.message}
        return state

    def _should_failover(self, action: Action, err: AgentError) -> bool:
        """Schematic-only failover gate (Part 6)."""
        return (
            self.fallback is not None
            and action.domain == ActionDomain.SCHEMATIC
            and err.category in self.FAILOVER_CATEGORIES
        )

    def _execute_fallback(self, action: Action, t0: float, ipc_error: AgentError) -> ActionResult:
        """Delegate explicitly to fallback and retain both outcomes."""
        assert self.fallback is not None
        try:
            result = self.fallback.execute(action)
        except Exception as e:
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=AgentError(
                    category=ErrorCategory.IPC_ERROR,
                    message=f"IPC failed ({ipc_error.message}) and fallback "
                    f"{self.fallback.name} raised: {e}",
                    context={
                        "ipc_error": ipc_error.to_dict(),
                        "fallback_backend": self.fallback.name,
                        "fallback_exception": str(e),
                    },
                ),
                data={
                    "fallback_used": True,
                    "ipc_error": ipc_error.message,
                    "fallback_success": False,
                    "fallback_error": str(e),
                },
                execution_time_ms=(time.time() - t0) * 1000,
                backend_used=f"ipc->{self.fallback.name}",
            )
        if not isinstance(result.data, dict):
            result.data = {"result": result.data}
        result.data["fallback_used"] = True
        result.data["ipc_error"] = ipc_error.message
        result.data["fallback_success"] = result.success
        if result.error is not None:
            result.data["fallback_error"] = result.error.to_dict()
        result.backend_used = f"ipc->{self.fallback.name}"
        return result

    def execute(self, action: Action) -> ActionResult:
        t0 = time.time()
        try:
            return self._execute_live(action, t0)
        except Exception as e:
            if isinstance(e, AgentError):
                err = e
                err.context.setdefault("connection", self.connection_status())
            else:
                err = AgentError(
                    category=ErrorCategory.IPC_ERROR,
                    message=str(e),
                    operation=action.action_type.value,
                    context={"connection": self.connection_status()},
                )
            if self._should_failover(action, err):
                return self._execute_fallback(action, t0, err)
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=err,
                execution_time_ms=(time.time() - t0) * 1000,
                backend_used=self.name,
            )

    def _execute_live(self, action: Action, t0: float) -> ActionResult:
        p = action.parameters

        if action.domain is not ActionDomain.SCHEMATIC:
            raise AgentError(
                category=ErrorCategory.INVALID_ACTION,
                message=(
                    "IPCBackend is schematic-only; action domain is "
                    f"{action.domain.value}. PCB actions belong to IPCPCBBackend."
                ),
                operation=action.action_type.value,
                recoverable=False,
            )

        try:
            if action.action_type == ActionType.ADD_JUNCTION:
                from proto.schematic.schematic_types_pb2 import Junction  # type: ignore[import]

                doc = self._get_document(DocumentType.DOCTYPE_SCHEMATIC)
                pos = p.get("position", (p.get("x", 0), p.get("y", 0)))

                junc = Junction()
                junc.id.value = str(uuid.uuid4())
                junc.position.x_nm = int(pos[0] * 1e6)
                junc.position.y_nm = int(pos[1] * 1e6)

                any_item = ProtoAny()
                any_item.Pack(junc)

                def _create():
                    resp = self.create_items(doc, [any_item])
                    created_id = self._created_id(resp, Junction)
                    if not created_id:
                        raise AgentError(
                            category=ErrorCategory.IPC_ERROR,
                            message="Server echoed junction without an id "
                            "(silent reject).",
                        )
                    return {"resp": resp, "created_id": created_id}

                # Commit lifecycle: a failed write must DROP, never linger.
                out = self._run_commit(doc, f"add junction {junc.id.value}", _create)
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"id": out["created_id"],
                          "items_created": len(out["resp"].created_items)},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.ADD_WIRE:
                classes = _schematic_type_classes()
                doc = self._get_document(DocumentType.DOCTYPE_SCHEMATIC)
                start = p.get("start", [p.get("x1", 0.0), p.get("y1", 0.0)])
                end = p.get("end", [p.get("x2", 0.0), p.get("y2", 0.0)])
                line_type = 2 if str(p.get("kind", "wire")).lower() == "bus" else 1

                line = classes["SchematicLine"]()
                line.id.value = str(uuid.uuid4())
                line.start.x_nm = int(float(start[0]) * 1e6)
                line.start.y_nm = int(float(start[1]) * 1e6)
                line.end.x_nm = int(float(end[0]) * 1e6)
                line.end.y_nm = int(float(end[1]) * 1e6)
                line.type = line_type

                any_item = ProtoAny()
                any_item.Pack(line)

                def _create_wire():
                    resp = self.create_items(doc, [any_item])
                    created_id = self._created_id(resp, classes["SchematicLine"])
                    if not created_id:
                        raise AgentError(
                            category=ErrorCategory.IPC_ERROR,
                            message="Server echoed wire without an id (silent reject).",
                        )
                    return {"resp": resp, "created_id": created_id}

                out = self._run_commit(doc, f"add wire {line.id.value}", _create_wire)
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"id": out["created_id"],
                          "items_created": len(out["resp"].created_items)},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.ADD_LABEL:
                classes = _schematic_type_classes()
                doc = self._get_document(DocumentType.DOCTYPE_SCHEMATIC)
                label_type = str(p.get("label_type", p.get("kind", "local"))).lower()
                cls_name = {
                    "local": "LocalLabel",
                    "global": "GlobalLabel",
                    "hierarchical": "HierarchicalLabel",
                    "hier": "HierarchicalLabel",
                }.get(label_type)
                if cls_name is None:
                    raise AgentError(
                        category=ErrorCategory.INVALID_ACTION,
                        message=f"Unsupported label_type '{label_type}' for IPC "
                        "(local/global/hierarchical).",
                    )
                pos = p.get("position", (p.get("x", 0.0), p.get("y", 0.0)))

                label = classes[cls_name]()
                label.id.value = str(uuid.uuid4())
                label.position.x_nm = int(float(pos[0]) * 1e6)
                label.position.y_nm = int(float(pos[1]) * 1e6)
                label.text.text = str(p.get("text", ""))

                any_item = ProtoAny()
                any_item.Pack(label)

                def _create_label():
                    resp = self.create_items(doc, [any_item])
                    created_id = self._created_id(resp, classes[cls_name])
                    if not created_id:
                        raise AgentError(
                            category=ErrorCategory.IPC_ERROR,
                            message="Server echoed label without an id (silent reject).",
                        )
                    return {"resp": resp, "created_id": created_id}

                out = self._run_commit(doc, f"add label {label.id.value}", _create_label)
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"id": out["created_id"],
                          "items_created": len(out["resp"].created_items)},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.MOVE_SYMBOL:
                classes = _schematic_type_classes()
                doc = self._get_document(DocumentType.DOCTYPE_SCHEMATIC)
                reference = p.get("reference", p.get("ref", ""))
                if not reference:
                    raise AgentError(
                        category=ErrorCategory.INVALID_ACTION,
                        message="MOVE_SYMBOL requires a reference.",
                    )
                try:
                    x_mm = float(p["x"])
                    y_mm = float(p["y"])
                except (KeyError, TypeError, ValueError) as e:
                    raise AgentError(
                        category=ErrorCategory.INVALID_ACTION,
                        message="MOVE_SYMBOL requires numeric x/y.",
                    ) from e

                symbol_id = self._resolve_symbol_id(doc, str(reference))

                def _move():
                    fetched = self.get_items_by_id(doc, [symbol_id])
                    if not fetched:
                        raise AgentError(
                            category=ErrorCategory.MISSING_OBJECT,
                            message=f"Symbol id '{symbol_id}' vanished before update.",
                        )
                    sym = classes["SchematicSymbolInstance"]()
                    if not fetched[0].Unpack(sym):
                        raise AgentError(
                            category=ErrorCategory.IPC_ERROR,
                            message="Fetched symbol did not unpack.",
                        )
                    sym.position.x_nm = int(x_mm * 1e6)
                    sym.position.y_nm = int(y_mm * 1e6)
                    packed = ProtoAny()
                    packed.Pack(sym)
                    resp = self.update_items(doc, [packed])
                    updated = classes["SchematicSymbolInstance"]()
                    if not (resp.updated_items
                            and resp.updated_items[0].item.Unpack(updated)):
                        raise AgentError(
                            category=ErrorCategory.IPC_ERROR,
                            message="Update response did not echo the symbol.",
                        )
                    if (getattr(updated.id, "value", "") or "") != symbol_id:
                        raise AgentError(
                            category=ErrorCategory.IPC_ERROR,
                            message="Update echoed a different symbol id.",
                        )
                    return {"id": symbol_id}

                out = self._run_commit(doc, f"move symbol {reference}", _move)
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"id": out["id"], "reference": reference,
                          "x": x_mm, "y": y_mm},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.DELETE_SYMBOL:
                doc = self._get_document(DocumentType.DOCTYPE_SCHEMATIC)
                symbol_id = str(p.get("id", "") or "")
                reference = str(p.get("reference", p.get("ref", "")) or "")
                if not symbol_id and not reference:
                    raise AgentError(
                        category=ErrorCategory.INVALID_ACTION,
                        message="DELETE_SYMBOL requires an id or reference.",
                    )
                if not symbol_id:
                    symbol_id = self._resolve_symbol_id(doc, reference)

                def _delete():
                    self.delete_items_by_id(doc, [symbol_id])
                    return {"id": symbol_id}

                out = self._run_commit(doc, f"delete symbol {symbol_id}", _delete)
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"id": out["id"], "reference": reference},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.GET_STATE:
                state = self.get_state(action.domain.value)
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data=state,
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            else:
                if action.domain == ActionDomain.PCB:
                    raise AgentError(
                        category=ErrorCategory.INVALID_ACTION,
                        message=f"IPCBackend is schematic-only; PCB action "
                        f"{action.action_type} belongs to PcbnewBackend.",
                    )
                raise AgentError(
                    category=ErrorCategory.INVALID_ACTION,
                    message=f"Live IPC command execution for {action.action_type} not yet mapped or requires fallback",
                )

        except Exception as e:
            # Re-raise for execute(): it converts to a failed result and,
            # for schematic actions, engages the fallback backend (Part 6).
            if isinstance(e, AgentError):
                raise
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=str(e),
                operation=action.action_type.value,
            ) from e
