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
    SCHEMATIC_ITEM_TYPES,
    ApiStatusCode,
    CommitAction,
    DocumentType,
    ItemDeletionStatus,
    ItemRequestStatus,
    ItemStatusCode,
    KiCadObjectType,
    get_base_type_protos,
    get_commit_protos,
    get_document_text_protos,
    get_item_by_id_protos,
    get_editor_command_protos,
    get_envelope_protos,
    get_item_mutation_protos,
    get_schematic_command_protos,
    get_schematic_type_protos,
)
from .protocol import ProtocolHelper
from .kipy_client import (
    KipySession,
    describe_kipy,
    is_kipy_available,
    load_schematic_command_protos,
)

__all__ = [
    "ApiStatusCode",
    "CommitAction",
    "DocumentType",
    "ItemDeletionStatus",
    "ItemRequestStatus",
    "IPCConnectionError",
    "IPCError",
    "IPCRequestError",
    "IPCTimeoutError",
    "IPCUnpackError",
    "ItemStatusCode",
    "KiCadIPCClient",
    "KiCadObjectType",
    "KipySession",
    "ProtocolHelper",
    "describe_kipy",
    "is_kipy_available",
    "load_schematic_command_protos",
    "default_socket_path",
    "generate_client_name",
    "SCHEMATIC_ITEM_TYPES",
    "get_base_type_protos",
    "get_commit_protos",
    "get_document_text_protos",
    "get_editor_command_protos",
    "get_item_by_id_protos",
    "get_item_mutation_protos",
    "get_envelope_protos",
    "get_schematic_command_protos",
    "get_schematic_type_protos",
]
