"""Read-only PCB debugging helpers for KiCad IPC (10.0.x only).

Safe inspection tools for the LLM to find bugs WITHOUT mutating the board:
- No BeginCommit / EndCommit / Create / Update / Delete here.
- Every function is a single IPC read; failures raise PCBDebugError with
  the KiCad status string preserved.
"""

from __future__ import annotations

from typing import Any

from .messages_pcb import (
    get_base_type,
    get_board_command,
    get_board_type,
    get_editor_command,
)
from ..client import KiCadIPCClient
from ..messages import ItemRequestStatus


def _direct_proto(module_path: str, name: str) -> Any:
    """Import a proto class/enum straight from generated pb2 modules."""
    import importlib
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, name)
    except (ImportError, AttributeError) as e:
        raise PCBDebugError(
            f"{name} is not available in the local 10.0.x protos: {e}"
        ) from e


def _editor_proto(name: str) -> Any:
    return _direct_proto("common.commands.editor_commands_pb2", name)


def _board_proto(name: str) -> Any:
    return _direct_proto("board.board_commands_pb2", name)


def _base_proto(name: str) -> Any:
    return _direct_proto("common.types.base_types_pb2", name)


class PCBDebugError(Exception):
    """A read-only PCB debug probe failed."""


_NM_PER_MM = 1_000_000


def _wrap(op: str, fn):
    try:
        return fn()
    except PCBDebugError:
        raise
    except Exception as e:
        raise PCBDebugError(f"{op} failed: {e}") from e


def _header_for(doc) -> Any:
    ItemHeader = get_base_type("ItemHeader")
    header = ItemHeader()
    header.document.CopyFrom(doc)
    return header


def _require_proto(getter, name: str) -> Any:
    try:
        return getter(name)
    except (ImportError, KeyError, AttributeError) as e:
        raise PCBDebugError(
            f"{name} is not available in the local 10.0.x protos: {e}"
        ) from e


def _check_items_status(resp: Any, op: str) -> None:
    status = getattr(resp, "status", ItemRequestStatus.IRS_OK)
    if status != ItemRequestStatus.IRS_OK:
        raise PCBDebugError(f"{op} rejected: status={status}")
