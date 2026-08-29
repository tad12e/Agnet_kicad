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
from ..ipc.messages import (
    DocumentType,
    ItemStatusCode,
    get_base_type_protos,
    get_editor_command_protos,
    get_schematic_command_protos,
    get_schematic_type_protos,
)
from .base import KiCadBackend


class IPCBackend(KiCadBackend):
    """Live KiCad IPC protocol backend."""

    def __init__(self, client: Optional[KiCadIPCClient] = None, socket_path: Optional[str] = None):
        self.client = client or KiCadIPCClient(socket_path=socket_path)
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

    def _get_document(self, doc_type: int = DocumentType.DOCTYPE_SCHEMATIC):
        if self._doc_proto is not None and getattr(self._doc_proto, "type", None) == doc_type:
            return self._doc_proto

        _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
        cmd = GetOpenDocuments()
        cmd.type = doc_type
        try:
            resp = self.client.send(cmd, GetOpenDocumentsResponse)
            if resp.documents:
                self._doc_proto = resp.documents[0]
                return self._doc_proto
        except Exception:
            pass

        # Fallback dummy DocumentSpecifier
        _, _, _, DocumentSpecifier, _ = get_base_type_protos()
        doc = DocumentSpecifier()
        doc.type = doc_type
        self._doc_proto = doc
        return self._doc_proto

    def load_board(self, filepath: str) -> Dict[str, Any]:
        return self.get_state("pcb")

    def save_board(self, filepath: Optional[str] = None) -> bool:
        return True

    def load_schematic(self, filepath: str) -> Dict[str, Any]:
        return self.get_state("schematic")

    def save_schematic(self, filepath: Optional[str] = None) -> bool:
        return True

    def get_state(self, domain: str = "pcb") -> Dict[str, Any]:
        doc_type = DocumentType.DOCTYPE_PCB if domain == "pcb" else DocumentType.DOCTYPE_SCHEMATIC
        doc = self._get_document(doc_type)
        return {
            "board_filename": getattr(doc, "board_filename", ""),
            "project_name": getattr(doc.project, "name", "") if hasattr(doc, "project") else "",
        }

    def execute(self, action: Action) -> ActionResult:
        t0 = time.time()
        p = action.parameters

        try:
            if action.action_type == ActionType.ADD_JUNCTION:
                from proto.schematic.schematic_types_pb2 import Junction  # type: ignore[import]
                CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()

                doc = self._get_document(DocumentType.DOCTYPE_SCHEMATIC)
                pos = p.get("position", (p.get("x", 0), p.get("y", 0)))

                junc = Junction()
                junc.id.value = str(uuid.uuid4())
                junc.position.x_nm = int(pos[0] * 1e6)
                junc.position.y_nm = int(pos[1] * 1e6)

                any_item = ProtoAny()
                any_item.Pack(junc)

                cmd = CreateItems()
                cmd.header.document.CopyFrom(doc)
                cmd.items.append(any_item)

                resp = self.client.send(cmd, CreateItemsResponse)
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"id": junc.id.value, "items_created": len(resp.created_items)},
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
                raise AgentError(
                    category=ErrorCategory.INVALID_ACTION,
                    message=f"Live IPC command execution for {action.action_type} not yet mapped or requires fallback",
                )

        except Exception as e:
            err = e if isinstance(e, AgentError) else AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=str(e),
                operation=action.action_type.value,
            )
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=err,
                execution_time_ms=(time.time() - t0) * 1000,
                backend_used=self.name,
            )
