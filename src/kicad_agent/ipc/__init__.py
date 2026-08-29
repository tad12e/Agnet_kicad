"""KiCad IPC Transport Layer.

Handles socket connection management, message serialization, and status codes.
"""

from .client import KiCadIPCClient
from .connection import default_socket_path, generate_client_name
from .exceptions import (
    IPCConnectionError,
    IPCError,
    IPCRequestError,
    IPCTimeoutError,
    IPCUnpackError,
)
from .messages import (
    ApiStatusCode,
    DocumentType,
    ItemStatusCode,
    get_base_type_protos,
    get_editor_command_protos,
    get_envelope_protos,
    get_schematic_command_protos,
    get_schematic_type_protos,
)
from .protocol import ProtocolHelper

__all__ = [
    "ApiStatusCode",
    "DocumentType",
    "IPCConnectionError",
    "IPCError",
    "IPCRequestError",
    "IPCTimeoutError",
    "IPCUnpackError",
    "ItemStatusCode",
    "KiCadIPCClient",
    "ProtocolHelper",
    "default_socket_path",
    "generate_client_name",
    "get_base_type_protos",
    "get_editor_command_protos",
    "get_envelope_protos",
    "get_schematic_command_protos",
    "get_schematic_type_protos",
]
