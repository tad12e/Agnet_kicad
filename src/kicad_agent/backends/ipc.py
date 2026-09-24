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

    def connect(self) -> None:
        self.client.connect()

    def disconnect(self) -> None:
        self.client.close()
