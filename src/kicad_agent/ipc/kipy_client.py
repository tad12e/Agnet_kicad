"""Official kicad-python (kipy) transport wrapper (Part 2).

Transport-only layer over KiCad's official IPC client. It does NOT change
backend behavior yet (backends switch over in Parts 3-4).

Known upstream state (verified 2026-09-23 against kicad-python 0.7.1/0.8.0):
- `kipy.board`, `kipy.client.KiCadClient`, `kipy.proto.common.*` (envelope,
  editor commands incl. Begin/EndCommit, Get/Update/DeleteItems): WORK.
- `kipy.schematic` / `kipy.schematic_types`: BROKEN on import (0.8.0 wants
  `PageSettings` from common_types; 0.7.1/0.8.0 want `BusEntryType` from a
  `_pb2` that lacks it). Schematic messages therefore come from our vendored
  `proto/schematic/*` until upstream ships a consistent wheel.
- `kipy.proto.schematic.schematic_commands_pb2`: present but EMPTY
  (DESCRIPTOR only). Same fallback applies.
- `KiCad` session object has NO `get_schematic()` (board-only).
- kipy 0.8.0 metadata pins `protobuf<6`, but our vendored `_pb2` files are
  gencode 7.35.1, so this repo requires `protobuf>=7.35.1` (verified working
  with kipy's client at runtime 7.36.2).

PROCESS-ISOLATION CONSTRAINT: kipy's bundled `_pb2` files and our vendored
`proto/` files register the same proto filenames (e.g.
`common/types/enums.proto`) in protobuf's global descriptor pool. Importing
both sets in ONE process raises "duplicate file name". Therefore:
- The schematic lane (this repo's present + future backend path) uses the
  vendored `proto/` set EXCLUSIVELY (it is newer for schematics anyway).
- `KipySession`/`describe_kipy` are for board-side/diagnostic use. Do NOT
  mix them with vendored schematic messages in one process; the diagnostic
  probe runs the kipy check in a SUBPROCESS for exactly this reason.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def is_kipy_available() -> bool:
    """True if `kicad-python` is importable (any version)."""
    try:
        import kipy  # noqa: F401

        return True
    except ImportError:
        return False


def describe_kipy() -> Dict[str, Any]:
    """Report kipy version + per-lane wrapper health (never raises)."""
    info: Dict[str, Any] = {
        "installed": False,
        "version": None,
        "board_wrapper": False,
        "schematic_wrapper": False,
        "schematic_wrapper_error": None,
        "editor_commit_protos": False,
    }
    try:
        import importlib.metadata as _md

        info["version"] = _md.version("kicad-python")
    except Exception:
        pass
    try:
        import kipy  # noqa: F401

        info["installed"] = True
    except ImportError as e:
        info["schematic_wrapper_error"] = f"kipy not installed: {e}"
        return info

    try:
        import kipy.board  # noqa: F401

        info["board_wrapper"] = True
    except Exception:
        pass

    try:
        import kipy.schematic  # noqa: F401

        info["schematic_wrapper"] = True
    except Exception as e:
        info["schematic_wrapper_error"] = f"{type(e).__name__}: {e}"

    try:
        from kipy.proto.common.commands import editor_commands_pb2 as _ec

        info["editor_commit_protos"] = all(
            hasattr(_ec, n)
            for n in (
                "BeginCommit",
                "EndCommit",
                "CreateItems",
                "GetItems",
                "UpdateItems",
                "DeleteItems",
            )
        )
    except Exception:
        pass
    return info


def load_schematic_command_protos():
    """Schematic command protos: kipy-first, vendored `proto/` fallback.

    kipy's copy is currently empty, so the vendored copy wins today; the
    kipy-first order future-proofs us for a fixed upstream wheel.
    """
    for importer in (_kipy_schematic_commands, _vendored_schematic_commands):
        try:
            protos = importer()
            # Validate the message we actually need exists (kipy's copy is
            # an empty module, so this check is what selects the fallback).
            if getattr(getattr(protos[0], "DESCRIPTOR", None), "name", "") == (
                "GetSchematicHierarchy"
            ):
                return protos
        except Exception:
            continue
    raise ImportError(
        "Schematic command protos unavailable in kipy and vendored proto/. "
        "Ensure proto/schematic/ is on sys.path."
    )


def _kipy_schematic_commands():
    from kipy.proto.schematic.schematic_commands_pb2 import (
        GetSchematicHierarchy,
        SchematicHierarchyResponse,
        GetSchematicNetlist,
        SchematicNetlistResponse,
    )

    return (
        GetSchematicHierarchy,
        SchematicHierarchyResponse,
        GetSchematicNetlist,
        SchematicNetlistResponse,
    )


def _vendored_schematic_commands():
    from .messages import get_schematic_command_protos

    return get_schematic_command_protos()


class KipySession:
    """Thin session over `kipy.KiCad` (official transport).

    Resolves socket/token/timeout exactly like kipy does (env vars
    KICAD_API_SOCKET / KICAD_API_TOKEN), with explicit overrides.
    """

    def __init__(
        self,
        socket_path: Optional[str] = None,
        client_name: Optional[str] = None,
        kicad_token: Optional[str] = None,
        timeout_ms: int = 5000,
    ):
        self.socket_path = socket_path
        self.client_name = client_name or f"kicad-ai-agent-{os.getpid()}"
        self.kicad_token = kicad_token
        self.timeout_ms = timeout_ms
        self._session = None

    def _require_kipy(self):
        try:
            from kipy import KiCad
        except ImportError as e:
            raise ImportError(
                "kicad-python (kipy) is required for the official transport. "
                "Install with: pip install \"kicad-python==0.8.0\" "
                "and note this repo needs protobuf>=7.35.1."
            ) from e
        return KiCad

    def connect(self):
        """Create the kipy session (connects lazily on first request)."""
        KiCad = self._require_kipy()
        kwargs: Dict[str, Any] = {
            "client_name": self.client_name,
            "timeout_ms": self.timeout_ms,
        }
        # Only pass explicit values; otherwise kipy reads env/defaults itself.
        if self.socket_path is not None:
            kwargs["socket_path"] = self.socket_path
        if self.kicad_token is not None:
            kwargs["kicad_token"] = self.kicad_token
        self._session = KiCad(**kwargs)
        return self

    def close(self) -> None:
        self._session = None

    @property
    def is_connected(self) -> bool:
        if self._session is None:
            return False
        try:
            return bool(self._session.client.connected)
        except Exception:
            return False

    def _ensure(self):
        if self._session is None:
            self.connect()
        return self._session

    def ping(self) -> bool:
        """Lightweight liveness check (no board interaction)."""
        session = self._ensure()
        session.ping()
        return True

    def get_open_documents(self) -> List[Any]:
        """Raw DocumentSpecifier list (all types) via official client."""
        session = self._ensure()
        return list(session.get_open_documents())

    def get_version(self) -> str:
        session = self._ensure()
        try:
            v = session.get_version()
            full = getattr(v, "full_version", None)
            if full:
                return str(full)
            return f"{getattr(v, 'major', '?')}.{getattr(v, 'minor', '?')}.{getattr(v, 'patch', '?')}"
        except Exception:
            return "unknown"
