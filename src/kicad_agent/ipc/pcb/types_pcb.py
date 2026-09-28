"""PCB item builders for KiCad IPC (10.0.x only).

Converts mm coordinates/parameters to KiCad internal nanometers (nm) and
constructs protobuf messages for CreateItems/UpdateItems.

Every proto is resolved BY NAME through :mod:`messages_pcb`
(``get_board_type`` / ``get_base_type``).  The old positional lookups returned
``Ratio`` where ``LockedState`` was meant, ``TextBox`` where
``PolygonWithHoles`` was meant and 22 values where 20 names were expected, so
these builders either raised ValueError deep in unpacking or silently built the
wrong message.

Three 10.0 facts encoded here:
- ``LockedState`` is an ENUM: assign its value (``track.locked = LS_LOCKED``).
  ``CopyFrom`` on an enum field raises AttributeError.
- ``Zone.outline`` is a ``PolySet`` holding ``PolygonWithHoles`` polygons.
- ``CopperZoneSettings.teardrop`` is a plain ``TeardropSettings``; the 10.0
  protos contain no ``ZoneTeardropSettings`` / ``ZoneCornerSmoothingMode``.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .messages_pcb import get_base_type, get_board_type


# =============================================================================
# Unit conversions
# =============================================================================

NM_PER_MM = 1_000_000

# FootprintMountingStyle.FMS_SMD (1 = through-hole, 2 = SMD).  The enum is not
# part of the name map, so the value is spelled out with a comment.
MOUNTING_STYLE_SMD = 2


def mm_to_nm(mm: float) -> int:
    """Convert millimeters to nanometers (KiCad internal units)."""
    return int(round(mm * NM_PER_MM))


def nm_to_mm(nm: int) -> float:
    """Convert nanometers to millimeters."""
    return nm / NM_PER_MM


def mm_pair_to_nm(pos: Tuple[float, float]) -> Tuple[int, int]:
    """Convert (X, Y) mm tuple to (X, Y) nm tuple."""
    return mm_to_nm(pos[0]), mm_to_nm(pos[1])


def nm_pair_to_mm(pos: Tuple[int, int]) -> Tuple[float, float]:
    """Convert (X, Y) nm tuple to (X, Y) mm tuple."""
    return nm_to_mm(pos[0]), nm_to_mm(pos[1])


# =============================================================================
# Scalar / geometry builders
# =============================================================================

def build_vector2(x_mm: float, y_mm: float):
    """Create a kiapi.common.types.Vector2 from mm coordinates."""
    Vector2 = get_base_type("Vector2")
    vec = Vector2()
    vec.x_nm = mm_to_nm(x_mm)
    vec.y_nm = mm_to_nm(y_mm)
    return vec


def build_distance(val_mm: float):
    """Create a kiapi.common.types.Distance from mm."""
    Distance = get_base_type("Distance")
    d = Distance()
    d.value_nm = mm_to_nm(val_mm)
    return d


def build_angle(val_deg: float):
    """Create a kiapi.common.types.Angle from degrees.

    The proto field is ``value_degrees`` (kipy's wrapper exposes it as
    ``degrees``; the raw message does not).
    """
    Angle = get_base_type("Angle")
    a = Angle()
    a.value_degrees = val_deg
    return a


def build_locked_state(locked: bool = False) -> int:
    """Return the ``LockedState`` enum VALUE for a locked flag.

    ``locked`` is a protobuf enum field in KiCad 10.0, so the value is assigned
    directly: ``track.locked = build_locked_state(True)``.
    """
    LockedState = get_base_type("LockedState")
    return LockedState.LS_LOCKED if locked else LockedState.LS_UNLOCKED


def is_locked(value) -> bool:
    """True when a ``LockedState`` enum field reads LS_LOCKED."""
    return value == build_locked_state(True)


def build_net(net_name: str, net_code: int = 0):
    """Create a kiapi.board.types.Net (name + NetCode)."""
    Net = get_board_type("Net")
    NetCode = get_board_type("NetCode")
    nc = NetCode()
    nc.value = net_code
    net = Net()
    net.code.CopyFrom(nc)
    net.name = net_name
    return net


def build_text(text_str: str, size_mm: float = 1.0, thickness_mm: float = 0.15):
    """Create a kiapi.common.types.Text."""
    Text = get_base_type("Text")
    TextAttributes = get_base_type("TextAttributes")
    t = Text()
    t.text = text_str
    attrs = TextAttributes()
    attrs.size.x_nm = mm_to_nm(size_mm)
    attrs.size.y_nm = mm_to_nm(size_mm)
    attrs.stroke_width.CopyFrom(build_distance(thickness_mm))
    attrs.italic = False
    attrs.keep_upright = True
    t.attributes.CopyFrom(attrs)
    return t


# =============================================================================
# PCB item builders
# =============================================================================

def build_track(
    start: Tuple[float, float],
    end: Tuple[float, float],
    width_mm: float = 0.25,
    layer: int = 3,  # BL_F_Cu
    net_name: str = "",
    net_code: int = 0,
    locked: bool = False,
):
    """Create a kiapi.board.types.Track (straight segment)."""
    Track = get_board_type("Track")
    track = Track()
    track.start.CopyFrom(build_vector2(start[0], start[1]))
    track.end.CopyFrom(build_vector2(end[0], end[1]))
    track.width.CopyFrom(build_distance(width_mm))
    track.layer = layer
    track.net.CopyFrom(build_net(net_name, net_code))
    track.locked = build_locked_state(locked)
    return track


def build_arc(
    start: Tuple[float, float],
    mid: Tuple[float, float],
    end: Tuple[float, float],
    width_mm: float = 0.25,
    layer: int = 3,  # BL_F_Cu
    net_name: str = "",
    net_code: int = 0,
    locked: bool = False,
):
    """Create a kiapi.board.types.Arc (arc track)."""
    Arc = get_board_type("Arc")
    arc = Arc()
    arc.start.CopyFrom(build_vector2(start[0], start[1]))
    arc.mid.CopyFrom(build_vector2(mid[0], mid[1]))
    arc.end.CopyFrom(build_vector2(end[0], end[1]))
    arc.width.CopyFrom(build_distance(width_mm))
    arc.layer = layer
    arc.net.CopyFrom(build_net(net_name, net_code))
    arc.locked = build_locked_state(locked)
    return arc


def build_simple_padstack(
    size_mm: Tuple[float, float],
    drill_mm: float = 0.0,
    shape: int = 1,  # PadStackShape.PSS_CIRCLE
    layers: Optional[List[int]] = None,
    start_layer: int = 3,  # BL_F_Cu
    end_layer: int = 34,   # BL_B_Cu
):
    """Create a simple kiapi.board.types.PadStack for a through-hole or SMD via.

    Args:
        size_mm: (x, y) pad size in mm on each copper layer
        drill_mm: hole diameter in mm (0 = no hole / SMD)
        shape: PadStackShape enum (1=CIRCLE, 2=RECTANGLE, 3=OVAL, 5=ROUNDRECT)
        layers: list of BoardLayer enum values (default: F.Cu + B.Cu)
        start_layer: drill start layer (default F.Cu)
        end_layer: drill end layer (default B.Cu)
    """
    PadStack = get_board_type("PadStack")
    PadStackLayer = get_board_type("PadStackLayer")
    DrillProperties = get_board_type("DrillProperties")
    PadStackType = get_board_type("PadStackType")
    UnconnectedLayerRemoval = get_board_type("UnconnectedLayerRemoval")
    BoardLayer = get_board_type("BoardLayer")
    SolderMaskMode = get_board_type("SolderMaskMode")
    SolderPasteMode = get_board_type("SolderPasteMode")
    ViaCoveringMode = get_board_type("ViaCoveringMode")
    ViaPluggingMode = get_board_type("ViaPluggingMode")
    ViaDrillCappingMode = get_board_type("ViaDrillCappingMode")
    ViaDrillFillingMode = get_board_type("ViaDrillFillingMode")
    DrillShape = get_board_type("DrillShape")
    ZoneConnectionSettings = get_board_type("ZoneConnectionSettings")
    ZoneConnectionStyle = get_board_type("ZoneConnectionStyle")

    if layers is None:
        layers = [BoardLayer.BL_F_Cu, BoardLayer.BL_B_Cu]

    ps = PadStack()
    ps.type = PadStackType.PST_NORMAL  # same shape all layers
    ps.layers.extend(layers)

    # Drill properties
    if drill_mm > 0:
        drill = DrillProperties()
        drill.start_layer = start_layer
        drill.end_layer = end_layer
        drill.diameter.CopyFrom(build_vector2(drill_mm, drill_mm))
        drill.shape = DrillShape.DS_CIRCLE
        drill.capped = ViaDrillCappingMode.VDCM_FROM_DESIGN_RULES
        drill.filled = ViaDrillFillingMode.VDFM_FROM_DESIGN_RULES
        ps.drill.CopyFrom(drill)

    # Unconnected layer removal
    ps.unconnected_layer_removal = UnconnectedLayerRemoval.ULR_REMOVE_EXCEPT_START_AND_END

    # Copper layers
    for layer_val in layers:
        pl = PadStackLayer()
        pl.layer = layer_val
        pl.shape = shape
        pl.size.CopyFrom(build_vector2(size_mm[0], size_mm[1]))
        pl.corner_rounding_ratio = 0.0
        pl.chamfer_ratio = 0.0
        ps.copper_layers.append(pl)

    # Rotation
    ps.angle.CopyFrom(build_angle(0.0))

    # Outer layer settings (solder mask / paste)
    outer = ps.front_outer_layers
    outer.solder_mask_mode = SolderMaskMode.SMM_FROM_DESIGN_RULES
    outer.solder_paste_mode = SolderPasteMode.SPM_FROM_DESIGN_RULES
    outer.plugging_mode = ViaPluggingMode.VPM_FROM_DESIGN_RULES
    outer.covering_mode = ViaCoveringMode.VCM_FROM_DESIGN_RULES

    outer = ps.back_outer_layers
    outer.solder_mask_mode = SolderMaskMode.SMM_FROM_DESIGN_RULES
    outer.solder_paste_mode = SolderPasteMode.SPM_FROM_DESIGN_RULES
    outer.plugging_mode = ViaPluggingMode.VPM_FROM_DESIGN_RULES
    outer.covering_mode = ViaCoveringMode.VCM_FROM_DESIGN_RULES

    # Zone connection
    zc = ZoneConnectionSettings()
    zc.zone_connection = ZoneConnectionStyle.ZCS_INHERITED
    ps.zone_settings.CopyFrom(zc)

    return ps


def build_via(
    position: Tuple[float, float],
    size_mm: float = 0.8,
    drill_mm: float = 0.4,
    net_name: str = "",
    net_code: int = 0,
    via_type: int = 1,  # ViaType.VT_THROUGH
    layers: Tuple[int, int] = (3, 34),  # F.Cu, B.Cu
    locked: bool = False,
):
    """Create a kiapi.board.types.Via."""
    Via = get_board_type("Via")
    via = Via()
    via.position.CopyFrom(build_vector2(position[0], position[1]))

    padstack = build_simple_padstack(
        size_mm=(size_mm, size_mm),
        drill_mm=drill_mm,
        shape=1,  # PadStackShape.PSS_CIRCLE
        layers=list(layers),
    )
    via.pad_stack.CopyFrom(padstack)
    via.locked = build_locked_state(locked)
    via.net.CopyFrom(build_net(net_name, net_code))
    via.type = via_type
    return via


def build_copper_zone(
    polygon: List[Tuple[float, float]],
    layer: int = 3,  # BL_F_Cu
    net_name: str = "GND",
    net_code: int = 0,
    clearance_mm: float = 0.5,
    min_thickness_mm: float = 0.25,
    fill_mode: int = 1,  # ZoneFillMode.ZFM_SOLID
    hatch_gap_mm: float = 0.5,
    hatch_thickness_mm: float = 0.5,
    hatch_orientation_deg: float = 0.0,
    priority: int = 0,
    locked: bool = False,
):
    """Create a kiapi.board.types.Zone (copper pour).

    The zone is created unfilled (``filled = False``); call
    ``mutations_pcb.refill_zones`` afterwards to actually pour copper.
    """
    Zone = get_board_type("Zone")
    ZoneType = get_board_type("ZoneType")
    CopperZoneSettings = get_board_type("CopperZoneSettings")
    ZoneConnectionSettings = get_board_type("ZoneConnectionSettings")
    ZoneConnectionStyle = get_board_type("ZoneConnectionStyle")
    HatchFillSettings = get_board_type("HatchFillSettings")
    ZoneHatchFillBorderMode = get_board_type("ZoneHatchFillBorderMode")
    ZoneBorderSettings = get_board_type("ZoneBorderSettings")
    ZoneBorderStyle = get_board_type("ZoneBorderStyle")
    IslandRemovalMode = get_board_type("IslandRemovalMode")
    ThermalSpokeSettings = get_board_type("ThermalSpokeSettings")
    PolygonWithHoles = get_base_type("PolygonWithHoles")
    PolySet = get_base_type("PolySet")

    zone = Zone()
    zone.type = ZoneType.ZT_COPPER
    zone.layers.append(layer)
    zone.priority = priority
    zone.filled = False  # must call refill_zones after create
    zone.locked = build_locked_state(locked)
    zone.name = net_name

    # Outline: Zone.outline is a PolySet of PolygonWithHoles, whose outline is
    # a PolyLine of PolyLineNode (each node holding a point or an arc).
    poly = PolygonWithHoles()
    line = poly.outline
    line.closed = True  # zone outlines must be closed
    for pt in polygon:
        node = line.nodes.add()
        node.point.x_nm = mm_to_nm(pt[0])
        node.point.y_nm = mm_to_nm(pt[1])
    poly_set = PolySet()
    poly_set.polygons.append(poly)
    zone.outline.CopyFrom(poly_set)

    # Copper zone settings
    settings = CopperZoneSettings()
    conn = ZoneConnectionSettings()
    conn.zone_connection = ZoneConnectionStyle.ZCS_THERMAL
    spoke = ThermalSpokeSettings()
    spoke.width.CopyFrom(build_distance(0.5))
    spoke.gap.CopyFrom(build_distance(0.5))
    spoke.angle.CopyFrom(build_angle(45.0))
    conn.thermal_spokes.CopyFrom(spoke)
    settings.connection.CopyFrom(conn)
    settings.clearance.CopyFrom(build_distance(clearance_mm))
    settings.min_thickness.CopyFrom(build_distance(min_thickness_mm))
    settings.island_mode = IslandRemovalMode.IRM_AREA
    settings.min_island_area = 0
    settings.fill_mode = fill_mode
    hatch = HatchFillSettings()
    hatch.thickness.CopyFrom(build_distance(hatch_thickness_mm))
    hatch.gap.CopyFrom(build_distance(hatch_gap_mm))
    hatch.orientation.CopyFrom(build_angle(hatch_orientation_deg))
    hatch.hatch_smoothing_ratio = 0.0
    hatch.hatch_hole_min_area_ratio = 0.0
    hatch.border_mode = ZoneHatchFillBorderMode.ZHFBM_USE_MIN_ZONE_THICKNESS
    settings.hatch_settings.CopyFrom(hatch)
    settings.net.CopyFrom(build_net(net_name, net_code))
    # CopperZoneSettings.teardrop is a plain TeardropSettings in 10.0; its
    # default (type 0) means "no teardrop", so it is left untouched.
    zone.copper_settings.CopyFrom(settings)

    # Border
    border = ZoneBorderSettings()
    border.style = ZoneBorderStyle.ZBS_SOLID
    border.pitch.CopyFrom(build_distance(1.0))
    zone.border.CopyFrom(border)

    return zone


def build_footprint_instance(
    reference: str,
    value: str,
    position: Tuple[float, float],
    orientation_deg: float = 0.0,
    layer: int = 3,  # BL_F_Cu
    locked: bool = False,
    library_id: str = "",
    footprint_name: str = "",
):
    """Create a kiapi.board.types.FootprintInstance (minimal placeholder).

    Note: the footprint definition is minimal.  Real usage should either have
    the footprint already loaded from a KiCad library, or bring the definition
    in via ParseAndCreateItemsFromString.  The instance KIID is left empty on
    purpose: KiCad assigns it on create (kipy behaves the same).
    """
    FootprintInstance = get_board_type("FootprintInstance")
    Footprint = get_board_type("Footprint")
    FootprintAttributes = get_board_type("FootprintAttributes")
    FootprintDesignRuleOverrides = get_board_type("FootprintDesignRuleOverrides")
    Field = get_board_type("Field")
    FieldId = get_board_type("FieldId")
    BoardText = get_board_type("BoardText")
    ZoneConnectionStyle = get_board_type("ZoneConnectionStyle")
    LibraryIdentifier = get_base_type("LibraryIdentifier")

    # Library identifier (the field is library_nickname, not nickname)
    lib_id = LibraryIdentifier()
    lib_id.library_nickname = library_id or ""
    lib_id.entry_name = footprint_name or ""

    # Footprint definition (minimal)
    fp_def = Footprint()
    fp_def.id.CopyFrom(lib_id)
    fp_def.anchor.CopyFrom(build_vector2(0.0, 0.0))

    # Attributes
    attrs = FootprintAttributes()
    attrs.description = ""
    attrs.keywords = ""
    attrs.mounting_style = MOUNTING_STYLE_SMD
    fp_def.attributes.CopyFrom(attrs)

    # Overrides
    overrides = FootprintDesignRuleOverrides()
    overrides.zone_connection = ZoneConnectionStyle.ZCS_INHERITED
    fp_def.overrides.CopyFrom(overrides)

    # Mandatory fields
    ref_field = Field()
    ref_field.id.CopyFrom(FieldId())
    ref_field.id.id = 1
    ref_field.name = "Reference"
    ref_text = BoardText()
    ref_text.text.CopyFrom(build_text(reference))
    ref_field.text.CopyFrom(ref_text)
    fp_def.reference_field.CopyFrom(ref_field)

    val_field = Field()
    val_field.id.CopyFrom(FieldId())
    val_field.id.id = 2
    val_field.name = "Value"
    val_text = BoardText()
    val_text.text.CopyFrom(build_text(value))
    val_field.text.CopyFrom(val_text)
    fp_def.value_field.CopyFrom(val_field)

    # Instance
    inst = FootprintInstance()
    inst.position.CopyFrom(build_vector2(position[0], position[1]))
    inst.orientation.CopyFrom(build_angle(orientation_deg))
    inst.layer = layer
    inst.locked = build_locked_state(locked)
    inst.definition.CopyFrom(fp_def)

    # Instance fields (mirror definition)
    inst.reference_field.CopyFrom(ref_field)
    inst.value_field.CopyFrom(val_field)

    return inst


def build_board_text(
    text_str: str,
    position: Tuple[float, float],
    layer: int = 39,  # BL_B_SilkS
    size_mm: float = 1.0,
    thickness_mm: float = 0.15,
    knockout: bool = False,
    locked: bool = False,
):
    """Create a kiapi.board.types.BoardText."""
    BoardText = get_board_type("BoardText")
    bt = BoardText()
    bt.text.CopyFrom(build_text(text_str, size_mm, thickness_mm))
    bt.layer = layer
    bt.knockout = knockout
    bt.locked = build_locked_state(locked)
    return bt


def pack_any(message):
    """Pack a protobuf message into google.protobuf.Any."""
    from google.protobuf.any_pb2 import Any
    any_msg = Any()
    any_msg.Pack(message)
    return any_msg


# =============================================================================
# Converters: protobuf -> Python dict (for snapshot reading)
# =============================================================================

def track_to_dict(track) -> dict:
    """Convert Track protobuf to simple dict."""
    return {
        "id": getattr(track.id, "value", ""),
        "start": nm_pair_to_mm((track.start.x_nm, track.start.y_nm)),
        "end": nm_pair_to_mm((track.end.x_nm, track.end.y_nm)),
        "width_mm": nm_to_mm(track.width.value_nm),
        "layer": track.layer,
        "net": track.net.name if track.net else "",
        "locked": is_locked(track.locked),
    }


def arc_to_dict(arc) -> dict:
    """Convert Arc protobuf to simple dict."""
    return {
        "id": getattr(arc.id, "value", ""),
        "start": nm_pair_to_mm((arc.start.x_nm, arc.start.y_nm)),
        "mid": nm_pair_to_mm((arc.mid.x_nm, arc.mid.y_nm)),
        "end": nm_pair_to_mm((arc.end.x_nm, arc.end.y_nm)),
        "width_mm": nm_to_mm(arc.width.value_nm),
        "layer": arc.layer,
        "net": arc.net.name if arc.net else "",
        "locked": is_locked(arc.locked),
    }


def via_to_dict(via) -> dict:
    """Convert Via protobuf to simple dict."""
    pos = via.position
    padstack = via.pad_stack
    drill_diam = 0.0
    if padstack.drill.diameter.x_nm:
        drill_diam = nm_to_mm(padstack.drill.diameter.x_nm)
    size_mm = 0.0
    if padstack.copper_layers:
        size_mm = nm_to_mm(padstack.copper_layers[0].size.x_nm)
    return {
        "id": getattr(via.id, "value", ""),
        "position": nm_pair_to_mm((pos.x_nm, pos.y_nm)),
        "size_mm": size_mm,
        "drill_mm": drill_diam,
        "net": via.net.name if via.net else "",
        "via_type": via.type,
        "locked": is_locked(via.locked),
    }


def zone_to_dict(zone) -> dict:
    """Convert Zone protobuf to simple dict.

    ``Zone.outline`` is a ``PolySet`` of ``PolygonWithHoles``; each outline is a
    ``PolyLine`` whose nodes carry a point (or an arc, which is skipped here).
    """
    vertices = []
    for poly in zone.outline.polygons:
        for node in poly.outline.nodes:
            if node.HasField("point"):
                vertices.append(nm_pair_to_mm((node.point.x_nm, node.point.y_nm)))
    return {
        "id": getattr(zone.id, "value", ""),
        "type": zone.type,
        "layers": list(zone.layers),
        "vertices": vertices,
        "name": zone.name,
        "net": zone.copper_settings.net.name if zone.copper_settings.net else "",
        "filled": zone.filled,
        "priority": zone.priority,
        "locked": is_locked(zone.locked),
    }


def footprint_instance_to_dict(fp) -> dict:
    """Convert FootprintInstance protobuf to simple dict.

    Field text nests as Field.text (BoardText) -> BoardText.text (Text) ->
    Text.text (str).
    """
    ref = ""
    val = ""
    if fp.reference_field.text.text.text:
        ref = fp.reference_field.text.text.text
    if fp.value_field.text.text.text:
        val = fp.value_field.text.text.text
    return {
        "id": getattr(fp.id, "value", ""),
        "reference": ref,
        "value": val,
        "position": nm_pair_to_mm((fp.position.x_nm, fp.position.y_nm)),
        "orientation_deg": fp.orientation.value_degrees,
        "layer": fp.layer,
        "locked": is_locked(fp.locked),
        "library": fp.definition.id.library_nickname if fp.definition.id else "",
        "footprint": fp.definition.id.entry_name if fp.definition.id else "",
    }


def pad_to_dict(pad) -> dict:
    """Convert Pad protobuf to simple dict."""
    return {
        "id": getattr(pad.id, "value", ""),
        "number": pad.number,
        "net": pad.net.name if pad.net else "",
        "position": nm_pair_to_mm((pad.position.x_nm, pad.position.y_nm)),
        "locked": is_locked(pad.locked),
    }
