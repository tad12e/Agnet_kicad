"""KiCad communication and environment package."""

from .capabilities import KiCadCapabilities
from .client import KiCadClient
from .connection import default_socket_path, generate_client_name
from .exceptions import (
    DocumentNotFoundError,
    IPCConnectionError,
    IPCError,
    IPCRequestError,
    IPCTimeoutError,
    KiCadError,
    KiCadNotRunningError,
    OperationFailedError,
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
from .version import detect_kicad_version, is_kicad_running

__all__ = [
    "ApiStatusCode",
    "DocumentNotFoundError",
    "DocumentType",
    "IPCConnectionError",
    "IPCError",
    "IPCRequestError",
    "IPCTimeoutError",
    "ItemStatusCode",
    "KiCadCapabilities",
    "KiCadClient",
    "KiCadError",
    "KiCadNotRunningError",
    "OperationFailedError",
    "default_socket_path",
    "detect_kicad_version",
    "generate_client_name",
    "get_base_type_protos",
    "get_editor_command_protos",
    "get_envelope_protos",
    "get_schematic_command_protos",
    "get_schematic_type_protos",
    "is_kicad_running",
]
