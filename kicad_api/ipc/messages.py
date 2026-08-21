"""KiCad IPC Protobuf Message Helpers.

Centralizes protobuf imports and provides enum constants that match
KiCad's official .proto definitions:

- api/proto/common/envelope.proto         → ApiStatusCode
- api/proto/common/types/base_types.proto → DocumentType
- api/proto/common/commands/editor_commands.proto → ItemStatusCode

The protobuf generated classes are loaded from:
1. `proto/` (local compiled bindings from official KiCad proto files)
2. `kipy` (if installed)
"""

import os
import sys

# Ensure local proto and .site-packages paths are available
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_PROTO_DIR = os.path.join(_ROOT_DIR, "proto")
_SITE_PACKAGES_DIR = os.path.join(_ROOT_DIR, ".site-packages")

if os.path.exists(_SITE_PACKAGES_DIR) and _SITE_PACKAGES_DIR not in sys.path:
    sys.path.insert(0, _SITE_PACKAGES_DIR)

if _PROTO_DIR not in sys.path:
    sys.path.insert(0, _PROTO_DIR)


# ---------------------------------------------------------------------------
# Enum constants matching KiCad's protobuf enums.
# ---------------------------------------------------------------------------

class ApiStatusCode:
    """Matches kiapi.common.ApiStatusCode in envelope.proto."""
    AS_UNKNOWN = 0
    AS_OK = 1
    AS_TIMEOUT = 2
    AS_BAD_REQUEST = 3
    AS_NOT_READY = 4
    AS_UNHANDLED = 5
    AS_TOKEN_MISMATCH = 6
    AS_BUSY = 7
    AS_UNIMPLEMENTED = 8


class DocumentType:
    """Matches kiapi.common.types.DocumentType in base_types.proto."""
    DOCTYPE_UNKNOWN = 0
    DOCTYPE_SCHEMATIC = 1
    DOCTYPE_SYMBOL = 2
    DOCTYPE_PCB = 3
    DOCTYPE_FOOTPRINT = 4
    DOCTYPE_DRAWING_SHEET = 5
    DOCTYPE_PROJECT = 6


class ItemStatusCode:
    """Matches kiapi.common.commands.ItemStatusCode in editor_commands.proto."""
    ISC_UNKNOWN = 0
    ISC_OK = 1
    ISC_INVALID_TYPE = 2
    ISC_EXISTING = 3
    ISC_NONEXISTENT = 4
    ISC_IMMUTABLE = 5
    ISC_INVALID_DATA = 7


# ---------------------------------------------------------------------------
# Protobuf message loader functions.
# ---------------------------------------------------------------------------

def get_envelope_protos():
    """Import and return the ApiRequest/ApiResponse envelope classes."""
    try:
        from common.envelope_pb2 import ApiRequest, ApiResponse
        return ApiRequest, ApiResponse
    except ImportError:
        try:
            from kipy.proto.common.envelope_pb2 import ApiRequest, ApiResponse
            return ApiRequest, ApiResponse
        except ImportError as e:
            raise ImportError(
                "KiCad protobuf bindings not found. Run protoc compilation or install kipy."
            ) from e


def get_editor_command_protos():
    """Import and return the editor command protobuf classes."""
    try:
        from common.commands.editor_commands_pb2 import (
            CreateItems,
            CreateItemsResponse,
            GetOpenDocuments,
            GetOpenDocumentsResponse,
        )
        return CreateItems, CreateItemsResponse, GetOpenDocuments, GetOpenDocumentsResponse
    except ImportError:
        try:
            from kipy.proto.common.commands.editor_commands_pb2 import (
                CreateItems,
                CreateItemsResponse,
                GetOpenDocuments,
                GetOpenDocumentsResponse,
            )
            return CreateItems, CreateItemsResponse, GetOpenDocuments, GetOpenDocumentsResponse
        except ImportError as e:
            raise ImportError(
                "KiCad protobuf bindings not found. Run protoc compilation or install kipy."
            ) from e


def get_base_type_protos():
    """Import and return the base type protobuf classes."""
    try:
        from common.types.base_types_pb2 import (
            KIID,
            Vector2,
            LibraryIdentifier,
            DocumentSpecifier,
        )
        return KIID, Vector2, LibraryIdentifier, DocumentSpecifier
    except ImportError:
        try:
            from kipy.proto.common.types.base_types_pb2 import (
                KIID,
                Vector2,
                LibraryIdentifier,
                DocumentSpecifier,
            )
            return KIID, Vector2, LibraryIdentifier, DocumentSpecifier
        except ImportError as e:
            raise ImportError(
                "KiCad protobuf bindings not found. Run protoc compilation or install kipy."
            ) from e


def get_schematic_type_protos():
    """Import and return the schematic type protobuf classes."""
    try:
        from schematic.schematic_types_pb2 import SchematicSymbolInstance
        return (SchematicSymbolInstance,)
    except ImportError:
        try:
            from kipy.proto.schematic.schematic_types_pb2 import SchematicSymbolInstance
            return (SchematicSymbolInstance,)
        except ImportError as e:
            raise ImportError(
                "KiCad protobuf bindings not found. Run protoc compilation or install kipy."
            ) from e
