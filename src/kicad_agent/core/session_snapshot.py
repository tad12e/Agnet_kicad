"""Versioned, checksummed persistence for resumable MCP sessions."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .contracts import SessionStatus


SNAPSHOT_KIND = "kicad-agent-session"
SNAPSHOT_VERSION = 1
RESUMABLE_STATUSES = frozenset({
    SessionStatus.PENDING.value,
    SessionStatus.RUNNING.value,
    SessionStatus.WAITING_APPROVAL.value,
    SessionStatus.WAITING_USER.value,
})


class SnapshotError(ValueError):
    """Raised when a snapshot is missing, unsupported, or corrupted."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical_json(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _digest(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


@dataclass
class SessionSnapshot:
    """MCP-facing snapshot envelope.

    The checksum covers the complete payload, excluding the checksum itself.
    This makes truncated or hand-edited snapshots fail closed instead of being
    silently accepted as a different session.
    """

    session_id: str
    status: str
    mode: str
    backend: str
    schematic: Optional[str] = None
    pcb: Optional[str] = None
    pending_approvals: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def payload(self) -> Dict[str, Any]:
        return {
            "kind": SNAPSHOT_KIND,
            "version": SNAPSHOT_VERSION,
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "status": self.status,
            "mode": self.mode,
            "backend": self.backend,
            "schematic": self.schematic,
            "pcb": self.pcb,
            "pending_approvals": self.pending_approvals,
            "metadata": self.metadata,
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = self.payload()
        return {**payload, "checksum": _digest(payload)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionSnapshot":
        if not isinstance(data, dict):
            raise SnapshotError("INVALID_SNAPSHOT", "Snapshot must be a JSON object.")
        if data.get("kind") != SNAPSHOT_KIND:
            raise SnapshotError("INVALID_SNAPSHOT_KIND", "Unsupported snapshot kind.")
        if data.get("version") != SNAPSHOT_VERSION:
            raise SnapshotError(
                "UNSUPPORTED_SNAPSHOT_VERSION",
                f"Expected snapshot version {SNAPSHOT_VERSION}.",
            )
        checksum = data.get("checksum")
        payload = {key: value for key, value in data.items() if key != "checksum"}
        if not isinstance(checksum, str) or checksum != _digest(payload):
            raise SnapshotError("SNAPSHOT_CORRUPT", "Snapshot checksum does not match.")
        required = ("session_id", "status", "mode", "backend")
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise SnapshotError(
                "INVALID_SNAPSHOT", f"Snapshot is missing required fields: {', '.join(missing)}."
            )
        status = str(data["status"])
        if status not in {item.value for item in SessionStatus}:
            raise SnapshotError("INVALID_SESSION_STATUS", f"Unknown session status: {status}.")
        if not isinstance(data.get("pending_approvals", {}), dict):
            raise SnapshotError("INVALID_SNAPSHOT", "pending_approvals must be an object.")
        return cls(
            snapshot_id=str(data.get("snapshot_id", "")),
            session_id=str(data["session_id"]),
            status=status,
            mode=str(data["mode"]),
            backend=str(data["backend"]),
            schematic=data.get("schematic"),
            pcb=data.get("pcb"),
            pending_approvals=dict(data.get("pending_approvals", {})),
            metadata=dict(data.get("metadata", {})),
        )


class SessionSnapshotStore:
    """Read and write snapshots with atomic replacement and strict validation."""

    @staticmethod
    def save(path: str, snapshot: SessionSnapshot) -> Dict[str, Any]:
        resolved = os.path.abspath(os.path.expanduser(path))
        parent = os.path.dirname(resolved) or os.curdir
        os.makedirs(parent, exist_ok=True)
        temporary = f"{resolved}.{uuid.uuid4().hex}.tmp"
        encoded = json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, resolved)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"path": resolved, "snapshot_id": snapshot.snapshot_id}

    @staticmethod
    def load(path: str) -> SessionSnapshot:
        resolved = os.path.abspath(os.path.expanduser(path))
        try:
            with open(resolved, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError as exc:
            raise SnapshotError("SNAPSHOT_NOT_FOUND", f"Snapshot not found: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotError("SNAPSHOT_UNREADABLE", f"Could not read snapshot: {exc}") from exc
        return SessionSnapshot.from_dict(data)
