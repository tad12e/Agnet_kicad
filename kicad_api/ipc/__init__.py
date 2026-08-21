"""KiCad IPC Transport Layer.

This package handles all communication with KiCad's API server:
- Socket connection management (NNG Req0)
- Protobuf envelope serialization/deserialization
- Domain-specific exceptions
- Protobuf message import helpers

Nothing else in the project should contain raw IPC/socket logic.
"""

from .client import KiCadIPCClient
from .exceptions import (
    IPCError,
    IPCConnectionError,
    IPCTimeoutError,
    IPCRequestError,
    IPCUnpackError,
)

__all__ = [
    "KiCadIPCClient",
    "IPCError",
    "IPCConnectionError",
    "IPCTimeoutError",
    "IPCRequestError",
    "IPCUnpackError",
]
