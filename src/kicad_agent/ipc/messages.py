"""KiCad IPC Protobuf Message Helpers.

Centralizes protobuf imports and provides enum constants matching
KiCad's official .proto definitions.
"""

from __future__ import annotations

import os
import sys

# Ensure local proto and .site-packages paths are accessible
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_PROTO_DIR = os.path.join(_ROOT_DIR, "proto")
_SITE_PACKAGES_DIR = os.path.join(_ROOT_DIR, ".site-packages")

if os.path.exists(_SITE_PACKAGES_DIR) and _SITE_PACKAGES_DIR not in sys.path:
    sys.path.insert(0, _SITE_PACKAGES_DIR)

if os.path.exists(_PROTO_DIR) and _PROTO_DIR not in sys.path:
    sys.path.insert(0, _PROTO_DIR)


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


class ItemRequestStatus:
    """Matches kiapi.common.types.ItemRequestStatus in base_types.proto."""
    IRS_UNKNOWN = 0
    IRS_OK = 1
    IRS_DOCUMENT_NOT_FOUND = 2
    IRS_FIELD_MASK_INVALID = 3


class CommitAction:
    """Matches kiapi.common.commands.CommitAction in editor_commands.proto."""
    CMA_UNKNOWN = 0
    CMA_COMMIT = 1
    CMA_DROP = 2


class ItemDeletionStatus:
    """Matches kiapi.common.commands.ItemDeletionStatus in editor_commands.proto."""
    IDS_UNKNOWN = 0
    IDS_OK = 1
    IDS_NONEXISTENT = 2
    IDS_IMMUTABLE = 3


class KiCadObjectType:
    """Subset of kiapi.common.types.KiCadObjectType (enums.proto) used here."""
    KOT_UNKNOWN = 0
    KOT_SCH_MARKER = 18
    KOT_SCH_JUNCTION = 19
    KOT_SCH_NO_CONNECT = 20
    KOT_SCH_BUS_WIRE_ENTRY = 21
    KOT_SCH_BUS_BUS_ENTRY = 22
    KOT_SCH_LINE = 23
    KOT_SCH_LABEL = 30
    KOT_SCH_GLOBAL_LABEL = 31
    KOT_SCH_HIER_LABEL = 32
    KOT_SCH_DIRECTIVE_LABEL = 33
    KOT_SCH_SYMBOL = 35
    KOT_SCH_SHEET = 37
    KOT_SCH_PIN = 38
    KOT_SCH_GROUP = 51


# Schematic item types listed by a single GetItems read. NOTE: pass explicit
# types always — an empty filter is an error on KiCad < 10.0.7.
SCHEMATIC_ITEM_TYPES = (
    KiCadObjectType.KOT_SCH_SYMBOL,
    KiCadObjectType.KOT_SCH_LINE,
    KiCadObjectType.KOT_SCH_JUNCTION,
    KiCadObjectType.KOT_SCH_LABEL,
    KiCadObjectType.KOT_SCH_GLOBAL_LABEL,
    KiCadObjectType.KOT_SCH_HIER_LABEL,
    KiCadObjectType.KOT_SCH_DIRECTIVE_LABEL,
)


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
                "KiCad protobuf bindings not found. Ensure proto/ directory or kipy is installed."
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
                "KiCad protobuf bindings not found. Ensure proto/ directory or kipy is installed."
            ) from e


def get_base_type_protos():
    """Import and return the base type protobuf classes."""
    try:
        from common.types.base_types_pb2 import (
            KIID,
            Vector2,
            LibraryIdentifier,
            DocumentSpecifier,
            SheetPath,
        )
        return KIID, Vector2, LibraryIdentifier, DocumentSpecifier, SheetPath
    except ImportError:
        try:
            from kipy.proto.common.types.base_types_pb2 import (
                KIID,
                Vector2,
                LibraryIdentifier,
                DocumentSpecifier,
                SheetPath,
            )
            return KIID, Vector2, LibraryIdentifier, DocumentSpecifier, SheetPath
        except ImportError:
            from common.types.base_types_pb2 import (
                KIID,
                Vector2,
                LibraryIdentifier,
                DocumentSpecifier,
            )
            return KIID, Vector2, LibraryIdentifier, DocumentSpecifier, None


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
                "KiCad protobuf bindings not found. Ensure proto/ directory or kipy is installed."
            ) from e


def get_schematic_command_protos():
    """Import and return schematic command protobuf classes."""
    try:
        from schematic.schematic_commands_pb2 import (
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
    except ImportError:
        try:
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
        except ImportError as e:
            raise ImportError(
                "KiCad protobuf bindings not found. Ensure proto/ directory or kipy is installed."
            ) from e
