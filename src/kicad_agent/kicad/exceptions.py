"""KiCad high-level domain exceptions."""

from __future__ import annotations

from ..ipc.exceptions import IPCError, IPCConnectionError, IPCRequestError, IPCTimeoutError


class KiCadError(Exception):
    """Base exception for all KiCad domain operations."""
    pass


class KiCadNotRunningError(KiCadError):
    """KiCad application is not running or socket is unreachable."""
    pass


class DocumentNotFoundError(KiCadError):
    """Requested schematic or PCB document was not found or open."""
    pass


class OperationFailedError(KiCadError):
    """KiCad rejected the requested operation."""
    pass


__all__ = [
    "DocumentNotFoundError",
    "IPCConnectionError",
    "IPCError",
    "IPCRequestError",
    "IPCTimeoutError",
    "KiCadError",
    "KiCadNotRunningError",
    "OperationFailedError",
]
