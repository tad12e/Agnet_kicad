"""High-level KiCad client interface.

Coordinates connection, capability detection, and backend selection.
"""

from __future__ import annotations

from typing import Optional

from ..ipc.client import KiCadIPCClient
from .capabilities import KiCadCapabilities
from .version import detect_kicad_version, is_kicad_running


class KiCadClient:
    """High-level client for communicating with and managing KiCad instances."""

    def __init__(
        self,
        ipc_client: Optional[KiCadIPCClient] = None,
        socket_path: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ):
        self.ipc = ipc_client or KiCadIPCClient(socket_path=socket_path, timeout_ms=timeout_ms)
        self.capabilities = KiCadCapabilities.detect()
        self.version = self.capabilities.version

    def is_running(self) -> bool:
        """Check if KiCad is running."""
        return is_kicad_running()

    def connect(self) -> None:
        """Connect to the KiCad IPC server."""
        self.ipc.connect()

    def close(self) -> None:
        """Disconnect from KiCad."""
        self.ipc.close()

    @property
    def is_connected(self) -> bool:
        """Check if socket connection is currently established."""
        return self.ipc.is_connected
