"""KiCad IPC PCB Protobuf Message Helpers (10.0.x only).

Centralizes PCB-specific protobuf imports and provides enum constants
matching KiCad's official board API .proto definitions.

Resolution rules (Part 5):
- Only the local ``proto/`` directory is used; there is deliberately NO kipy
  fallback, because both packages define ``common/types/enums.proto`` and
  mixing them poisons protobuf's descriptor pool.
- Protos are looked up BY NAME.  The positional tuples are kept only for
  backward compatibility.  Indexing them is what previously made
  ``update_item`` target ``DeleteItems``, ``delete_items`` target ``GetItems``
  and ``refill_zones`` target ``SetBoardOrigin`` without raising anything.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Dict

# Ensure local proto and .site-packages paths are accessible
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_PROTO_DIR = os.path.join(_ROOT_DIR, "proto")
_SITE_PACKAGES_DIR = os.path.join(_ROOT_DIR, ".site-packages")

if os.path.exists(_SITE_PACKAGES_DIR) and _SITE_PACKAGES_DIR not in sys.path:
    sys.path.insert(0, _SITE_PACKAGES_DIR)

if os.path.exists(_PROTO_DIR) and _PROTO_DIR not in sys.path:
    sys.path.insert(0, _PROTO_DIR)


class KiCadObjectTypePCB:
    """Subset of kiapi.common.types.KiCadObjectType for PCB items (10.0 branch).

    Matches: https://gitlab.com/kicad/code/kicad/-/blob/10.0/api/proto/common/types/enums.proto
    """
    KOT_UNKNOWN = 0

    KOT_PCB_FOOTPRINT = 1
    KOT_PCB_PAD = 2
    KOT_PCB_SHAPE = 3
    KOT_PCB_REFERENCE_IMAGE = 4
    KOT_PCB_FIELD = 5
    KOT_PCB_GENERATOR = 6
    KOT_PCB_TEXT = 7
    KOT_PCB_TEXTBOX = 8
    KOT_PCB_TABLE = 9
    KOT_PCB_TABLECELL = 10
    KOT_PCB_TRACE = 11
    KOT_PCB_VIA = 12
    KOT_PCB_ARC = 13
    KOT_PCB_MARKER = 14
    KOT_PCB_DIMENSION = 15
    KOT_PCB_ZONE = 16
    KOT_PCB_GROUP = 17

    # Schematic types (for reference, not used in PCB domain)
    KOT_SCH_MARKER = 18
    KOT_SCH_JUNCTION = 19
    KOT_SCH_NO_CONNECT = 20
    KOT_SCH_BUS_WIRE_ENTRY = 21
    KOT_SCH_BUS_BUS_ENTRY = 22
    KOT_SCH_LINE = 23
    KOT_SCH_SHAPE = 24
    KOT_SCH_BITMAP = 25
    KOT_SCH_TEXTBOX = 26
    KOT_SCH_TEXT = 27
    KOT_SCH_TABLE = 28
    KOT_SCH_TABLECELL = 29
    KOT_SCH_LABEL = 30
    KOT_SCH_GLOBAL_LABEL = 31
    KOT_SCH_HIER_LABEL = 32
    KOT_SCH_DIRECTIVE_LABEL = 33
    KOT_SCH_FIELD = 34
    KOT_SCH_SYMBOL = 35
    KOT_SCH_SHEET_PIN = 36
    KOT_SCH_SHEET = 37
    KOT_SCH_PIN = 38

    KOT_LIB_SYMBOL = 39

    KOT_WSG_LINE = 45
    KOT_WSG_RECT = 46
    KOT_WSG_POLY = 47
    KOT_WSG_TEXT = 48
    KOT_WSG_BITMAP = 49
    KOT_WSG_PAGE = 50

    KOT_SCH_GROUP = 51
    KOT_PCB_BARCODE = 52

    # 10.0 branch: reserved 53, 54, 55
    # 10.0 branch: KOT_PCB_POINT = 56


# PCB item types for GetItems read. Pass explicit types always —
# empty filter errors on KiCad < 10.0.7.
PCB_ITEM_TYPES = (
    KiCadObjectTypePCB.KOT_PCB_FOOTPRINT,
    KiCadObjectTypePCB.KOT_PCB_PAD,
    KiCadObjectTypePCB.KOT_PCB_TRACE,
    KiCadObjectTypePCB.KOT_PCB_ARC,
    KiCadObjectTypePCB.KOT_PCB_VIA,
    KiCadObjectTypePCB.KOT_PCB_ZONE,
    KiCadObjectTypePCB.KOT_PCB_SHAPE,
    KiCadObjectTypePCB.KOT_PCB_TEXT,
    KiCadObjectTypePCB.KOT_PCB_TEXTBOX,
    KiCadObjectTypePCB.KOT_PCB_TABLE,
    KiCadObjectTypePCB.KOT_PCB_TABLECELL,
    KiCadObjectTypePCB.KOT_PCB_BARCODE,
    KiCadObjectTypePCB.KOT_PCB_REFERENCE_IMAGE,
    KiCadObjectTypePCB.KOT_PCB_DIMENSION,
    KiCadObjectTypePCB.KOT_PCB_GROUP,
    KiCadObjectTypePCB.KOT_PCB_MARKER,
)

# Minimal set for copper-only queries (tracks, vias, zones, pads)
PCB_COPPER_ITEM_TYPES = (
    KiCadObjectTypePCB.KOT_PCB_TRACE,
    KiCadObjectTypePCB.KOT_PCB_ARC,
    KiCadObjectTypePCB.KOT_PCB_VIA,
    KiCadObjectTypePCB.KOT_PCB_ZONE,
    KiCadObjectTypePCB.KOT_PCB_PAD,
)


# =============================================================================
# Name-based proto lookup (Part 5 hardening)
# =============================================================================

def _named_map(classes, label: str) -> Dict[str, object]:
    """Build a ``proto message name -> class`` map from an ordered class tuple.

    Raises ImportError when an entry has no descriptor or when two entries
    share a name, so proto drift fails loudly instead of silently selecting
    the wrong message.
    """
    mapping: Dict[str, object] = {}
    for cls in classes:
        if cls is None:
            continue
        name = getattr(getattr(cls, "DESCRIPTOR", None), "name", None)
        if not name:
            raise ImportError(f"KiCad {label} proto entry has no descriptor: {cls!r}")
        if name in mapping:
            raise ImportError(
                f"Duplicate KiCad {label} proto name '{name}'; "
                "the generated protos are inconsistent."
            )
        mapping[name] = cls
    return mapping


def _lookup(mapping: Dict[str, object], name: str, label: str):
    """Fetch ``name`` from a name map, raising a helpful ImportError if absent."""
    try:
        return mapping[name]
    except KeyError:
        known = ", ".join(sorted(mapping))
        raise ImportError(f"Unknown KiCad {label} '{name}'. Known {label}s: {known}") from None


def _require(mapping: Dict[str, object], required, label: str) -> None:
    """Raise ImportError naming every required proto missing from ``mapping``."""
    missing = [name for name in required if name not in mapping]
    if missing:
        raise ImportError(
            f"KiCad PCB {label} protos missing required entries: {missing}. "
            "Ensure proto/ carries the 10.0.x version and is regenerated with "
            "grpc_tools.protoc."
        )


@lru_cache(maxsize=None)
def _board_command_classes():
    """Import and return board command protobuf classes (cached, ordered).

    Order is frozen for positional callers such as snapshot.py; new code must
    use :func:`get_board_command`.
    """
    import board.board_commands_pb2 as board_cmd

    # Core commands available in local 10.0.x protos
    GetNets = getattr(board_cmd, "GetNets", None)
    NetsResponse = getattr(board_cmd, "NetsResponse", None)
    GetItemsByNet = getattr(board_cmd, "GetItemsByNet", None)
    GetItemsByNetClass = getattr(board_cmd, "GetItemsByNetClass", None)
    GetConnectedItems = getattr(board_cmd, "GetConnectedItems", None)
    GetNetClassForNets = getattr(board_cmd, "GetNetClassForNets", None)
    NetClassForNetsResponse = getattr(board_cmd, "NetClassForNetsResponse", None)
    GetBoardStackup = getattr(board_cmd, "GetBoardStackup", None)
    BoardStackupResponse = getattr(board_cmd, "BoardStackupResponse", None)
    GetBoardEnabledLayers = getattr(board_cmd, "GetBoardEnabledLayers", None)
    BoardEnabledLayersResponse = getattr(board_cmd, "BoardEnabledLayersResponse", None)
    SetBoardEnabledLayers = getattr(board_cmd, "SetBoardEnabledLayers", None)
    GetGraphicsDefaults = getattr(board_cmd, "GetGraphicsDefaults", None)
    GraphicsDefaultsResponse = getattr(board_cmd, "GraphicsDefaultsResponse", None)
    GetBoardOrigin = getattr(board_cmd, "GetBoardOrigin", None)
    SetBoardOrigin = getattr(board_cmd, "SetBoardOrigin", None)
    GetBoardLayerName = getattr(board_cmd, "GetBoardLayerName", None)
    BoardLayerNameResponse = getattr(board_cmd, "BoardLayerNameResponse", None)
    RefillZones = getattr(board_cmd, "RefillZones", None)
    GetPadShapeAsPolygon = getattr(board_cmd, "GetPadShapeAsPolygon", None)
    PadShapeAsPolygonResponse = getattr(board_cmd, "PadShapeAsPolygonResponse", None)
    CheckPadstackPresenceOnLayers = getattr(board_cmd, "CheckPadstackPresenceOnLayers", None)
    PadstackPresenceResponse = getattr(board_cmd, "PadstackPresenceResponse", None)
    InjectDrcError = getattr(board_cmd, "InjectDrcError", None)
    InjectDrcErrorResponse = getattr(board_cmd, "InjectDrcErrorResponse", None)
    GetVisibleLayers = getattr(board_cmd, "GetVisibleLayers", None)
    BoardLayers = getattr(board_cmd, "BoardLayers", None)
    SetVisibleLayers = getattr(board_cmd, "SetVisibleLayers", None)
    GetActiveLayer = getattr(board_cmd, "GetActiveLayer", None)
    SetActiveLayer = getattr(board_cmd, "SetActiveLayer", None)
    BoardLayerResponse = getattr(board_cmd, "BoardLayerResponse", None)
    BoardOriginType = getattr(board_cmd, "BoardOriginType", None)
    GetBoardEditorAppearanceSettings = getattr(board_cmd, "GetBoardEditorAppearanceSettings", None)
    BoardEditorAppearanceSettings = getattr(board_cmd, "BoardEditorAppearanceSettings", None)
    SetBoardEditorAppearanceSettings = getattr(board_cmd, "SetBoardEditorAppearanceSettings", None)

    # Commands that may not exist in older 10.0.x protos
    FlipItems = getattr(board_cmd, "FlipItems", None)
    FlipItemsResponse = getattr(board_cmd, "FlipItemsResponse", None)
    InteractiveMoveItems = getattr(board_cmd, "InteractiveMoveItems", None)

    return (
        GetNets,
        NetsResponse,
        GetItemsByNet,
        GetItemsByNetClass,
        GetConnectedItems,
        GetNetClassForNets,
        NetClassForNetsResponse,
        GetBoardStackup,
        BoardStackupResponse,
        GetBoardEnabledLayers,
        BoardEnabledLayersResponse,
        SetBoardEnabledLayers,
        GetGraphicsDefaults,
        GraphicsDefaultsResponse,
        GetBoardOrigin,
        SetBoardOrigin,
        GetBoardLayerName,
        BoardLayerNameResponse,
        RefillZones,
        GetPadShapeAsPolygon,
        PadShapeAsPolygonResponse,
        CheckPadstackPresenceOnLayers,
        PadstackPresenceResponse,
        InjectDrcError,
        InjectDrcErrorResponse,
        GetVisibleLayers,
        BoardLayers,
        SetVisibleLayers,
        GetActiveLayer,
        SetActiveLayer,
        BoardLayerResponse,
        BoardOriginType,
        GetBoardEditorAppearanceSettings,
        BoardEditorAppearanceSettings,
        SetBoardEditorAppearanceSettings,
        FlipItems,
        FlipItemsResponse,
        InteractiveMoveItems,
    )


_REQUIRED_BOARD_COMMANDS = (
    "GetNets",
    "NetsResponse",
    "GetBoardStackup",
    "BoardStackupResponse",
    "GetBoardEnabledLayers",
    "BoardEnabledLayersResponse",
    "GetBoardOrigin",
    "GetBoardLayerName",
    "GetVisibleLayers",
    "BoardLayers",
    "SetVisibleLayers",
    "GetActiveLayer",
    "SetActiveLayer",
    "BoardLayerResponse",
    "BoardOriginType",
    "GetItemsByNet",
    "GetConnectedItems",
    "RefillZones",
    "InjectDrcError",
)


@lru_cache(maxsize=None)
def _board_command_map() -> Dict[str, object]:
    """Cached ``name -> board command class`` map (validated)."""
    mapping = _named_map(_board_command_classes(), "board command")
    _require(mapping, _REQUIRED_BOARD_COMMANDS, "command")
    return mapping


def get_board_command_protos():
    """Board command classes in their stable positional order (validated).

    Prefer :func:`get_board_command` in new code.
    """
    _board_command_map()
    return _board_command_classes()


def get_board_command(name: str):
    """Board command class by proto name, e.g. ``get_board_command("RefillZones")``."""
    return _lookup(_board_command_map(), name, "board command")


@lru_cache(maxsize=None)
def _board_type_classes():
    """Import and return board type protobuf classes (cached, ordered).

    Order is frozen for positional callers such as snapshot.py; new code must
    use :func:`get_board_type`.
    """
    import board.board_types_pb2 as board_types

    # Core types available in local 10.0.x protos
    Track = getattr(board_types, "Track", None)
    Arc = getattr(board_types, "Arc", None)
    Via = getattr(board_types, "Via", None)
    Pad = getattr(board_types, "Pad", None)
    Zone = getattr(board_types, "Zone", None)
    Footprint = getattr(board_types, "Footprint", None)
    FootprintInstance = getattr(board_types, "FootprintInstance", None)
    Net = getattr(board_types, "Net", None)
    NetCode = getattr(board_types, "NetCode", None)
    PadStack = getattr(board_types, "PadStack", None)
    PadStackLayer = getattr(board_types, "PadStackLayer", None)
    DrillProperties = getattr(board_types, "DrillProperties", None)
    PostMachiningProperties = getattr(board_types, "PostMachiningProperties", None)
    BoardLayer = getattr(board_types, "BoardLayer", None)
    ViaType = getattr(board_types, "ViaType", None)
    ZoneType = getattr(board_types, "ZoneType", None)
    ZoneConnectionStyle = getattr(board_types, "ZoneConnectionStyle", None)
    SolderMaskOverrides = getattr(board_types, "SolderMaskOverrides", None)
    SolderPasteOverrides = getattr(board_types, "SolderPasteOverrides", None)
    PadStackType = getattr(board_types, "PadStackType", None)
    UnconnectedLayerRemoval = getattr(board_types, "UnconnectedLayerRemoval", None)
    PadStackShape = getattr(board_types, "PadStackShape", None)
    PadType = getattr(board_types, "PadType", None)
    PadFabricationProperty = getattr(board_types, "PadFabricationProperty", None)
    ThermalSpokeSettings = getattr(board_types, "ThermalSpokeSettings", None)
    SymbolPinInfo = getattr(board_types, "SymbolPinInfo", None)
    ZoneFillMode = getattr(board_types, "ZoneFillMode", None)
    HatchFillSettings = getattr(board_types, "HatchFillSettings", None)
    TeardropSettings = getattr(board_types, "TeardropSettings", None)
    CopperZoneSettings = getattr(board_types, "CopperZoneSettings", None)
    RuleAreaSettings = getattr(board_types, "RuleAreaSettings", None)
    ZoneBorderStyle = getattr(board_types, "ZoneBorderStyle", None)
    ZoneBorderSettings = getattr(board_types, "ZoneBorderSettings", None)
    ZoneFilledPolygons = getattr(board_types, "ZoneFilledPolygons", None)
    ZoneLayerProperties = getattr(board_types, "ZoneLayerProperties", None)
    ZoneTeardropSettings = getattr(board_types, "ZoneTeardropSettings", None)
    PadTeardropSettings = getattr(board_types, "PadTeardropSettings", None)
    PadTeardropMode = getattr(board_types, "PadTeardropMode", None)
    BoardGraphicShape = getattr(board_types, "BoardGraphicShape", None)
    BoardText = getattr(board_types, "BoardText", None)
    BoardTextBox = getattr(board_types, "BoardTextBox", None)
    Barcode = getattr(board_types, "Barcode", None)
    BarcodeKind = getattr(board_types, "BarcodeKind", None)
    BarcodeErrorCorrection = getattr(board_types, "BarcodeErrorCorrection", None)
    Dimension = getattr(board_types, "Dimension", None)
    AlignedDimensionAttributes = getattr(board_types, "AlignedDimensionAttributes", None)
    OrthogonalDimensionAttributes = getattr(board_types, "OrthogonalDimensionAttributes", None)
    RadialDimensionAttributes = getattr(board_types, "RadialDimensionAttributes", None)
    LeaderDimensionAttributes = getattr(board_types, "LeaderDimensionAttributes", None)
    CenterDimensionAttributes = getattr(board_types, "CenterDimensionAttributes", None)
    ReferenceImage = getattr(board_types, "ReferenceImage", None)
    Group = getattr(board_types, "Group", None)
    FieldId = getattr(board_types, "FieldId", None)
    Field = getattr(board_types, "Field", None)
    FootprintAttributes = getattr(board_types, "FootprintAttributes", None)
    FootprintVariant = getattr(board_types, "FootprintVariant", None)
    NetTieDefinition = getattr(board_types, "NetTieDefinition", None)
    FootprintDesignRuleOverrides = getattr(board_types, "FootprintDesignRuleOverrides", None)
    Footprint3DModel = getattr(board_types, "Footprint3DModel", None)
    JumperGroup = getattr(board_types, "JumperGroup", None)
    JumperSettings = getattr(board_types, "JumperSettings", None)
    ChamferedRectCorners = getattr(board_types, "ChamferedRectCorners", None)
    PadStackOuterLayer = getattr(board_types, "PadStackOuterLayer", None)
    ViaCoveringMode = getattr(board_types, "ViaCoveringMode", None)
    ViaPluggingMode = getattr(board_types, "ViaPluggingMode", None)
    ViaDrillCappingMode = getattr(board_types, "ViaDrillCappingMode", None)
    ViaDrillFillingMode = getattr(board_types, "ViaDrillFillingMode", None)
    ViaDrillPostMachiningMode = getattr(board_types, "ViaDrillPostMachiningMode", None)
    SolderMaskMode = getattr(board_types, "SolderMaskMode", None)
    SolderPasteMode = getattr(board_types, "SolderPasteMode", None)
    DrillShape = getattr(board_types, "DrillShape", None)
    ZoneHatchSmoothing = getattr(board_types, "ZoneHatchSmoothing", None)
    ZoneHatchFillBorderMode = getattr(board_types, "ZoneHatchFillBorderMode", None)
    ZoneCornerSmoothingMode = getattr(board_types, "ZoneCornerSmoothingMode", None)
    PlacementRuleSourceType = getattr(board_types, "PlacementRuleSourceType", None)
    ZoneTeardropType = getattr(board_types, "ZoneTeardropType", None)
    ZoneLayerOverride = getattr(board_types, "ZoneLayerOverride", None)
    ZoneLayerOverrideEntry = getattr(board_types, "ZoneLayerOverrideEntry", None)
    Table = getattr(board_types, "Table", None)
    TableCell = getattr(board_types, "TableCell", None)
    TableStrokeMode = getattr(board_types, "TableStrokeMode", None)
    ReferencePoint = getattr(board_types, "ReferencePoint", None)

    # Names the original list omitted; appended last so every existing index
    # keeps its meaning.
    ZoneConnectionSettings = getattr(board_types, "ZoneConnectionSettings", None)
    IslandRemovalMode = getattr(board_types, "IslandRemovalMode", None)

    return (
        Track,
        Arc,
        Via,
        Pad,
        Zone,
        Footprint,
        FootprintInstance,
        Net,
        NetCode,
        PadStack,
        PadStackLayer,
        DrillProperties,
        PostMachiningProperties,
        BoardLayer,
        ViaType,
        ZoneType,
        ZoneConnectionStyle,
        SolderMaskOverrides,
        SolderPasteOverrides,
        PadStackType,
        UnconnectedLayerRemoval,
        PadStackShape,
        PadType,
        PadFabricationProperty,
        ThermalSpokeSettings,
        SymbolPinInfo,
        ZoneFillMode,
        HatchFillSettings,
        TeardropSettings,
        CopperZoneSettings,
        RuleAreaSettings,
        ZoneBorderStyle,
        ZoneBorderSettings,
        ZoneFilledPolygons,
        ZoneLayerProperties,
        ZoneTeardropSettings,
        PadTeardropSettings,
        PadTeardropMode,
        BoardGraphicShape,
        BoardText,
        BoardTextBox,
        Barcode,
        BarcodeKind,
        BarcodeErrorCorrection,
        Dimension,
        AlignedDimensionAttributes,
        OrthogonalDimensionAttributes,
        RadialDimensionAttributes,
        LeaderDimensionAttributes,
        CenterDimensionAttributes,
        ReferenceImage,
        Group,
        FieldId,
        Field,
        FootprintAttributes,
        FootprintVariant,
        NetTieDefinition,
        FootprintDesignRuleOverrides,
        Footprint3DModel,
        JumperGroup,
        JumperSettings,
        ChamferedRectCorners,
        PadStackOuterLayer,
        ViaCoveringMode,
        ViaPluggingMode,
        ViaDrillCappingMode,
        ViaDrillFillingMode,
        ViaDrillPostMachiningMode,
        SolderMaskMode,
        SolderPasteMode,
        DrillShape,
        ZoneHatchSmoothing,
        ZoneHatchFillBorderMode,
        ZoneCornerSmoothingMode,
        PlacementRuleSourceType,
        ZoneTeardropType,
        ZoneLayerOverride,
        ZoneLayerOverrideEntry,
        Table,
        TableCell,
        TableStrokeMode,
        ReferencePoint,
        ZoneConnectionSettings,
        IslandRemovalMode,
    )


_REQUIRED_BOARD_TYPES = (
    "Track",
    "Arc",
    "Via",
    "Pad",
    "Zone",
    "FootprintInstance",
    "Net",
    "BoardLayer",
    "ZoneConnectionSettings",
    "IslandRemovalMode",
)


@lru_cache(maxsize=None)
def _board_type_map() -> Dict[str, object]:
    """Cached ``name -> board type class`` map (validated)."""
    mapping = _named_map(_board_type_classes(), "board type")
    _require(mapping, _REQUIRED_BOARD_TYPES, "type")
    return mapping


def get_board_type_protos():
    """Board type classes in their stable positional order (validated).

    Prefer :func:`get_board_type` in new code.
    """
    _board_type_map()
    return _board_type_classes()


def get_board_type(name: str):
    """Board type class by proto name, e.g. ``get_board_type("FootprintInstance")``.

    A footprint placed on a board is ``FootprintInstance``; ``Footprint`` is the
    library definition.  Looking up by name removes the off-by-one that used to
    send a definition where an instance was required.
    """
    return _lookup(_board_type_map(), name, "board type")


@lru_cache(maxsize=None)
def _editor_command_classes():
    """Import and return shared editor command protos (cached, ordered).

    Local proto/ only: no kipy fallback, because both packages define
    common/types/enums.proto and mixing them poisons the descriptor pool.
    Order is frozen for positional callers such as snapshot.py; new code must
    use :func:`get_editor_command`.
    """
    import common.commands.editor_commands_pb2 as editor_pb2

    # Core commands available in local 10.0.x protos
    CreateItems = getattr(editor_pb2, "CreateItems", None)
    CreateItemsResponse = getattr(editor_pb2, "CreateItemsResponse", None)
    GetOpenDocuments = getattr(editor_pb2, "GetOpenDocuments", None)
    GetOpenDocumentsResponse = getattr(editor_pb2, "GetOpenDocumentsResponse", None)
    GetItems = getattr(editor_pb2, "GetItems", None)
    GetItemsResponse = getattr(editor_pb2, "GetItemsResponse", None)
    UpdateItems = getattr(editor_pb2, "UpdateItems", None)
    UpdateItemsResponse = getattr(editor_pb2, "UpdateItemsResponse", None)
    DeleteItems = getattr(editor_pb2, "DeleteItems", None)
    DeleteItemsResponse = getattr(editor_pb2, "DeleteItemsResponse", None)
    GetItemsById = getattr(editor_pb2, "GetItemsById", None)
    GetSelection = getattr(editor_pb2, "GetSelection", None)
    SelectionResponse = getattr(editor_pb2, "SelectionResponse", None)
    ClearSelection = getattr(editor_pb2, "ClearSelection", None)
    AddToSelection = getattr(editor_pb2, "AddToSelection", None)
    RemoveFromSelection = getattr(editor_pb2, "RemoveFromSelection", None)
    BeginCommit = getattr(editor_pb2, "BeginCommit", None)
    BeginCommitResponse = getattr(editor_pb2, "BeginCommitResponse", None)
    EndCommit = getattr(editor_pb2, "EndCommit", None)
    EndCommitResponse = getattr(editor_pb2, "EndCommitResponse", None)
    SaveDocumentToString = getattr(editor_pb2, "SaveDocumentToString", None)
    SavedDocumentResponse = getattr(editor_pb2, "SavedDocumentResponse", None)
    SaveSelectionToString = getattr(editor_pb2, "SaveSelectionToString", None)
    SavedSelectionResponse = getattr(editor_pb2, "SavedSelectionResponse", None)
    ParseAndCreateItemsFromString = getattr(editor_pb2, "ParseAndCreateItemsFromString", None)
    HitTest = getattr(editor_pb2, "HitTest", None)
    HitTestResponse = getattr(editor_pb2, "HitTestResponse", None)
    GetBoundingBox = getattr(editor_pb2, "GetBoundingBox", None)
    GetBoundingBoxResponse = getattr(editor_pb2, "GetBoundingBoxResponse", None)
    SaveDocument = getattr(editor_pb2, "SaveDocument", None)
    SaveCopyOfDocument = getattr(editor_pb2, "SaveCopyOfDocument", None)
    RevertDocument = getattr(editor_pb2, "RevertDocument", None)

    # Commands that may not exist in older 10.0.x protos
    ExpandTextVariables = getattr(editor_pb2, "ExpandTextVariables", None)
    ExpandTextVariablesResponse = getattr(editor_pb2, "ExpandTextVariablesResponse", None)

    return (
        CreateItems,
        CreateItemsResponse,
        GetOpenDocuments,
        GetOpenDocumentsResponse,
        GetItems,
        GetItemsResponse,
        UpdateItems,
        UpdateItemsResponse,
        DeleteItems,
        DeleteItemsResponse,
        GetItemsById,
        GetSelection,
        SelectionResponse,
        ClearSelection,
        AddToSelection,
        RemoveFromSelection,
        BeginCommit,
        BeginCommitResponse,
        EndCommit,
        EndCommitResponse,
        SaveDocumentToString,
        SavedDocumentResponse,
        SaveSelectionToString,
        SavedSelectionResponse,
        ParseAndCreateItemsFromString,
        HitTest,
        HitTestResponse,
        ExpandTextVariables,
        ExpandTextVariablesResponse,
        GetBoundingBox,
        GetBoundingBoxResponse,
        SaveDocument,
        SaveCopyOfDocument,
        RevertDocument,
    )


_REQUIRED_EDITOR_COMMANDS = (
    "GetOpenDocuments",
    "GetOpenDocumentsResponse",
    "GetItems",
    "GetItemsResponse",
    "CreateItems",
    "CreateItemsResponse",
    "UpdateItems",
    "UpdateItemsResponse",
    "DeleteItems",
    "DeleteItemsResponse",
    "BeginCommit",
    "BeginCommitResponse",
    "EndCommit",
    "EndCommitResponse",
    "SaveDocumentToString",
    "SavedDocumentResponse",
    "GetItemsById",
)


@lru_cache(maxsize=None)
def _editor_command_map() -> Dict[str, object]:
    """Cached ``name -> editor command class`` map (validated)."""
    mapping = _named_map(_editor_command_classes(), "editor command")
    _require(mapping, _REQUIRED_EDITOR_COMMANDS, "command")
    return mapping


def get_editor_command_protos():
    """Editor command classes in their stable positional order (validated).

    Prefer :func:`get_editor_command` in new code.
    """
    _editor_command_map()
    return _editor_command_classes()


def get_editor_command(name: str):
    """Editor command class by proto name, e.g. ``get_editor_command("CreateItems")``."""
    return _lookup(_editor_command_map(), name, "editor command")


_ITEM_MUTATION_NAMES = (
    "GetItems",
    "GetItemsResponse",
    "UpdateItems",
    "UpdateItemsResponse",
    "DeleteItems",
    "DeleteItemsResponse",
)


def get_item_mutation_protos():
    """Return the (GetItems, UpdateItems, DeleteItems) command/response pairs.

    Mirrors ``ipc.messages.get_item_mutation_protos`` but resolves against the
    local 10.0.x protos only.  Looked up by name so a shifted index can never
    turn an UpdateItems into a GetOpenDocuments.
    """
    return tuple(get_editor_command(name) for name in _ITEM_MUTATION_NAMES)


def get_item_mutation(name: str):
    """One class from the GetItems/UpdateItems/DeleteItems family, by name."""
    if name not in _ITEM_MUTATION_NAMES:
        raise ImportError(
            f"'{name}' is not an item mutation proto. Known: {sorted(_ITEM_MUTATION_NAMES)}"
        )
    return get_editor_command(name)


@lru_cache(maxsize=None)
def _base_type_classes():
    """Import base type protos (cached, ordered).

    Uses ONLY the local proto/ directory.  Order is frozen for positional
    callers such as snapshot.py; new code must use :func:`get_base_type`.
    """
    import common.types.base_types_pb2 as base_pb2

    # Core types available in local 10.0.x protos
    KIID = getattr(base_pb2, "KIID", None)
    Vector2 = getattr(base_pb2, "Vector2", None)
    Vector3D = getattr(base_pb2, "Vector3D", None)
    Distance = getattr(base_pb2, "Distance", None)
    Angle = getattr(base_pb2, "Angle", None)
    Ratio = getattr(base_pb2, "Ratio", None)
    LockedState = getattr(base_pb2, "LockedState", None)
    Color = getattr(base_pb2, "Color", None)
    Text = getattr(base_pb2, "Text", None)
    TextAttributes = getattr(base_pb2, "TextAttributes", None)
    TextBox = getattr(base_pb2, "TextBox", None)
    GraphicShape = getattr(base_pb2, "GraphicShape", None)
    PolygonWithHoles = getattr(base_pb2, "PolygonWithHoles", None)
    PolySet = getattr(base_pb2, "PolySet", None)
    SheetPath = getattr(base_pb2, "SheetPath", None)
    LibraryIdentifier = getattr(base_pb2, "LibraryIdentifier", None)
    DocumentSpecifier = getattr(base_pb2, "DocumentSpecifier", None)
    EmbeddedFiles = getattr(base_pb2, "EmbeddedFiles", None)
    RunJobSettings = getattr(base_pb2, "RunJobSettings", None)
    TitleBlockInfo = getattr(base_pb2, "TitleBlockInfo", None)
    ElectricalPinType = getattr(base_pb2, "ElectricalPinType", None)
    Time = getattr(base_pb2, "Time", None)
    AxisAlignment = getattr(base_pb2, "AxisAlignment", None)
    Units = getattr(base_pb2, "Units", None)
    StrokeAttributes = getattr(base_pb2, "StrokeAttributes", None)
    ItemHeader = getattr(base_pb2, "ItemHeader", None)

    return (
        KIID,
        Vector2,
        Vector3D,
        Distance,
        Angle,
        Ratio,
        LockedState,
        Color,
        Text,
        TextAttributes,
        TextBox,
        GraphicShape,
        PolygonWithHoles,
        PolySet,
        SheetPath,
        LibraryIdentifier,
        DocumentSpecifier,
        EmbeddedFiles,
        RunJobSettings,
        TitleBlockInfo,
        ElectricalPinType,
        Time,
        AxisAlignment,
        Units,
        StrokeAttributes,
        ItemHeader,
    )


_REQUIRED_BASE_TYPES = (
    "KIID",
    "Vector2",
    "Distance",
    "Angle",
    "LockedState",
    "DocumentSpecifier",
    "ItemHeader",
)


@lru_cache(maxsize=None)
def _base_type_map() -> Dict[str, object]:
    """Cached ``name -> base type class`` map (validated)."""
    mapping = _named_map(_base_type_classes(), "base type")
    _require(mapping, _REQUIRED_BASE_TYPES, "type")
    return mapping


def get_base_type_protos():
    """Base type classes in their stable positional order (validated).

    Prefer :func:`get_base_type` in new code.
    """
    _base_type_map()
    return _base_type_classes()


def get_base_type(name: str):
    """Base/common type class by proto name, e.g. ``get_base_type("Vector2")``.

    Also resolves enums such as ``LockedState``: enum fields take the value
    directly (``track.locked = LockedState.LS_LOCKED``), never CopyFrom.
    """
    return _lookup(_base_type_map(), name, "base type")


def get_envelope_protos():
    """Import envelope protos (ApiRequest, ApiResponse)."""
    try:
        from common.envelope_pb2 import ApiRequest, ApiResponse
        return ApiRequest, ApiResponse
    except ImportError:
        try:
            from kipy.proto.common.envelope_pb2 import ApiRequest, ApiResponse
            return ApiRequest, ApiResponse
        except ImportError as e:
            raise ImportError(
                "KiCad envelope protos not found. Ensure proto/common/envelope.proto is generated."
            ) from e


def get_commit_protos():
    """Return (BeginCommit, BeginCommitResponse, EndCommit, EndCommitResponse).

    Resolved from the local 10.0.x protos only.

    IMPORTANT: in KiCad 10.0 ``BeginCommit`` and ``EndCommit`` carry NO
    ItemHeader / document field (kipy's ``Board.begin_commit`` sends a bare
    ``BeginCommit()``), so setting ``cmd.header`` raises AttributeError.
    Callers must not try to attach a document to a commit.
    """
    return (
        get_editor_command("BeginCommit"),
        get_editor_command("BeginCommitResponse"),
        get_editor_command("EndCommit"),
        get_editor_command("EndCommitResponse"),
    )


# Re-export status codes from shared module to avoid duplication
try:
    from ...messages import ApiStatusCode, DocumentType, ItemStatusCode, ItemRequestStatus, CommitAction, ItemDeletionStatus
except ImportError:
    pass


