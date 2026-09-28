"""Read-only PCB debugging helpers for KiCad IPC (10.0.x only).

Safe inspection tools for the LLM to find bugs WITHOUT mutating the board:
- No BeginCommit / EndCommit / Create / Update / Delete here.
- Every function is a single IPC read; failures raise PCBDebugError with
  the KiCad status string preserved.
"""

from __future__ import annotations

from typing import Any

from .messages_pcb import (
    get_base_type,
    get_board_command,
    get_board_type,
    get_editor_command,
)
from ..client import KiCadIPCClient
from ..messages import ItemRequestStatus


def _direct_proto(module_path: str, name: str) -> Any:
    """Import a proto class/enum straight from generated pb2 modules."""
    import importlib
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, name)
    except (ImportError, AttributeError) as e:
        raise PCBDebugError(
            f"{name} is not available in the local 10.0.x protos: {e}"
        ) from e


def _editor_proto(name: str) -> Any:
    return _direct_proto("common.commands.editor_commands_pb2", name)


def _board_proto(name: str) -> Any:
    return _direct_proto("board.board_commands_pb2", name)


def _base_proto(name: str) -> Any:
    return _direct_proto("common.types.base_types_pb2", name)


class PCBDebugError(Exception):
    """A read-only PCB debug probe failed."""


_NM_PER_MM = 1_000_000


def _wrap(op: str, fn):
    try:
        return fn()
    except PCBDebugError:
        raise
    except Exception as e:
        raise PCBDebugError(f"{op} failed: {e}") from e


def _header_for(doc) -> Any:
    ItemHeader = get_base_type("ItemHeader")
    header = ItemHeader()
    header.document.CopyFrom(doc)
    return header


def _require_proto(getter, name: str) -> Any:
    try:
        return getter(name)
    except (ImportError, KeyError, AttributeError) as e:
        raise PCBDebugError(
            f"{name} is not available in the local 10.0.x protos: {e}"
        ) from e


def _check_items_status(resp: Any, op: str) -> None:
    status = getattr(resp, "status", ItemRequestStatus.IRS_OK)
    if status != ItemRequestStatus.IRS_OK:
        raise PCBDebugError(f"{op} rejected: status={status}")

def hit_test(client, doc, kiid, x_mm, y_mm, tolerance_nm=0):
    """Probe whether (x_mm, y_mm) hits item kiid (HTR_HIT=2, NO_HIT=1)."""
    from typing import Dict
    HitTest = _editor_proto("HitTest")
    HitTestResponse = _editor_proto("HitTestResponse")
    HitTestResult = _editor_proto("HitTestResult")
    Vector2 = get_base_type("Vector2")
    KIID = get_base_type("KIID")
    cmd = HitTest()
    cmd.header.CopyFrom(_header_for(doc))
    kid = KIID()
    kid.value = kiid
    cmd.id.CopyFrom(kid)
    pos = Vector2()
    pos.x_nm = int(round(x_mm * _NM_PER_MM))
    pos.y_nm = int(round(y_mm * _NM_PER_MM))
    cmd.position.CopyFrom(pos)
    cmd.tolerance = int(tolerance_nm)
    resp = _wrap("HitTest", lambda: client.send(cmd, HitTestResponse))
    raw = int(getattr(resp, "result", 0))
    return {"hit": raw == int(getattr(HitTestResult, "HTR_HIT", 2)),
            "raw": raw}


def get_bboxes(client, doc, kiids, mode=1, container_kiid=None):
    """Return [{kiid, x_mm, y_mm, w_mm, h_mm}] (mode 1/2)."""
    if not kiids:
        raise PCBDebugError("get_bboxes needs at least one KIID.")
    GetBoundingBox = _editor_proto("GetBoundingBox")
    GetBoundingBoxResponse = _editor_proto("GetBoundingBoxResponse")
    KIID = get_base_type("KIID")
    cmd = GetBoundingBox()
    cmd.header.CopyFrom(_header_for(doc))
    if container_kiid:
        kid0 = KIID()
        kid0.value = container_kiid
        cmd.header.container.CopyFrom(kid0)
    for k in kiids:
        kid = KIID()
        kid.value = k
        cmd.items.append(kid)
    cmd.mode = int(mode)
    resp = _wrap("GetBoundingBox",
                 lambda: client.send(cmd, GetBoundingBoxResponse))
    out = []
    items = list(getattr(resp, "items", []))
    boxes = list(getattr(resp, "boxes", []))
    for i, kid in enumerate(items):
        if i >= len(boxes):
            break
        box = boxes[i]
        pos = getattr(box, "position", None)
        size = getattr(box, "size", None)
        out.append({
            "kiid": getattr(kid, "value", ""),
            "x_mm": getattr(pos, "x_nm", 0) / _NM_PER_MM,
            "y_mm": getattr(pos, "y_nm", 0) / _NM_PER_MM,
            "w_mm": getattr(size, "x_nm", 0) / _NM_PER_MM,
            "h_mm": getattr(size, "y_nm", 0) / _NM_PER_MM,
        })
    return out



def get_selection(client, doc, item_types=None, container_kiid=None):
    """Return currently selected items (unpacked Any list)."""
    GetSelection = _editor_proto("GetSelection")
    SelectionResponse = _editor_proto("SelectionResponse")
    cmd = GetSelection()
    cmd.header.CopyFrom(_header_for(doc))
    if container_kiid:
        KIID = get_base_type("KIID")
        kid0 = KIID()
        kid0.value = container_kiid
        cmd.header.container.CopyFrom(kid0)
    if item_types:
        cmd.types.extend(list(item_types))
    resp = _wrap("GetSelection", lambda: client.send(cmd, SelectionResponse))
    return list(getattr(resp, "items", []))


def save_selection(client):
    """Return {"ids": [...], "contents": sexpr} for the live selection."""
    SaveSelectionToString = _editor_proto("SaveSelectionToString")
    SavedSelectionResponse = _editor_proto("SavedSelectionResponse")
    resp = _wrap("SaveSelectionToString",
                 lambda: client.send(SaveSelectionToString(),
                                     SavedSelectionResponse))
    return {
        "ids": [getattr(k, "value", "") for k in getattr(resp, "ids", [])],
        "contents": getattr(resp, "contents", "") or "",
    }


def get_design_rules(client, doc):
    """Return {"rules": BoardDesignRules, "custom_rules_status": int}."""
    GetBoardDesignRules = _board_proto("GetBoardDesignRules")
    BoardDesignRulesResponse = _board_proto("BoardDesignRulesResponse")
    cmd = GetBoardDesignRules()
    cmd.board.CopyFrom(doc)
    resp = _wrap("GetBoardDesignRules",
                 lambda: client.send(cmd, BoardDesignRulesResponse))
    return {"rules": resp.rules,
            "custom_rules_status": int(
                getattr(resp, "custom_rules_status", 0))}


def get_custom_rules(client, doc):
    """Return {"status": int, "rules": [...], "error_text": str}."""
    GetCustomDesignRules = _board_proto("GetCustomDesignRules")
    CustomRulesResponse = _board_proto("CustomRulesResponse")
    cmd = GetCustomDesignRules()
    cmd.board.CopyFrom(doc)
    resp = _wrap("GetCustomDesignRules",
                 lambda: client.send(cmd, CustomRulesResponse))
    return {"status": int(getattr(resp, "status", 0)),
            "rules": list(getattr(resp, "rules", [])),
            "error_text": getattr(resp, "error_text", "") or ""}


def get_netclass_for_nets(client, doc, net_names):
    """Return {net_name: NetClass} for effective merged netclasses."""
    if not net_names:
        raise PCBDebugError("get_netclass_for_nets needs a net name.")
    from .snapshot import PCBSnapshotReader
    GetNetClassForNets = _board_proto("GetNetClassForNets")
    NetClassForNetsResponse = _board_proto("NetClassForNetsResponse")
    reader = PCBSnapshotReader(client)
    live = reader.get_nets()
    by_name = {n["name"]: n["code"] for n in live}
    cmd = GetNetClassForNets()
    for name in net_names:
        if name not in by_name:
            raise PCBDebugError(f"Net '{name}' not found on board.")
        code_val = by_name[name]
        code_int = int(getattr(code_val, "value", code_val))
        item = cmd.net.add() if hasattr(cmd, "net") else cmd.nets.add()
        item.name = name
        item.code.value = code_int
    resp = _wrap("GetNetClassForNets",
                 lambda: client.send(cmd, NetClassForNetsResponse))
    return dict(getattr(resp, "classes", {}))


def get_items_by_netclass(client, doc, net_classes, item_types=None,
                          container_kiid=None):
    """Return copper items in net_classes (pads/vias/tracks/zones)."""
    if not net_classes:
        raise PCBDebugError("get_items_by_netclass needs a net class.")
    GetItemsByNetClass = _board_proto("GetItemsByNetClass")
    GetItemsResponse = _editor_proto("GetItemsResponse")
    cmd = GetItemsByNetClass()
    cmd.header.CopyFrom(_header_for(doc))
    if container_kiid:
        KIID = get_base_type("KIID")
        kid0 = KIID()
        kid0.value = container_kiid
        cmd.header.container.CopyFrom(kid0)
    if item_types:
        cmd.types.extend(list(item_types))
    cmd.net_classes.extend(list(net_classes))
    resp = _wrap("GetItemsByNetClass",
                 lambda: client.send(cmd, GetItemsResponse))
    _check_items_status(resp, "GetItemsByNetClass")
    return list(getattr(resp, "items", []))


def get_pad_polygon(client, doc, pad_kiids, layer):
    """Return tessellated flashed shape per pad: [{pad, polygons}]."""
    if not pad_kiids:
        raise PCBDebugError("get_pad_polygon needs a pad KIID.")
    GetPadShapeAsPolygon = _board_proto("GetPadShapeAsPolygon")
    PadShapeAsPolygonResponse = _board_proto("PadShapeAsPolygonResponse")
    KIID = get_base_type("KIID")
    cmd = GetPadShapeAsPolygon()
    cmd.board.CopyFrom(doc)
    for k in pad_kiids:
        kid = KIID()
        kid.value = k
        cmd.pads.append(kid)
    cmd.layer = int(layer)
    resp = _wrap("GetPadShapeAsPolygon",
                 lambda: client.send(cmd, PadShapeAsPolygonResponse))
    pads = list(getattr(resp, "pads", []))
    polys = list(getattr(resp, "polygons", []))
    out = []
    for i, pad in enumerate(pads):
        if i >= len(polys):
            break
        out.append({"pad": getattr(pad, "value", ""),
                    "polygons": polys[i]})
    return out


def check_padstack(client, doc, kiids, layers):
    """Return [{item, layer, presence}] (1=PRESENT, 2=NOT_PRESENT)."""
    if not kiids:
        raise PCBDebugError("check_padstack needs an item KIID.")
    if not layers:
        raise PCBDebugError("check_padstack needs a layer.")
    CheckPadstack = _board_proto("CheckPadstackPresenceOnLayers")
    PadstackResp = _board_proto("PadstackPresenceResponse")
    KIID = get_base_type("KIID")
    cmd = CheckPadstack()
    cmd.board.CopyFrom(doc)
    for k in kiids:
        kid = KIID()
        kid.value = k
        cmd.items.append(kid)
    cmd.layers.extend([int(v) for v in layers])
    resp = _wrap("CheckPadstackPresenceOnLayers",
                 lambda: client.send(cmd, PadstackResp))
    out = []
    for entry in getattr(resp, "entries", []):
        out.append({
            "item": getattr(getattr(entry, "item", None), "value", ""),
            "layer": int(getattr(entry, "layer", 0)),
            "presence": int(getattr(entry, "presence", 0)),
        })
    return out


def get_appearance(client):
    """Return editor appearance modes (ints, read-only)."""
    GetAppearance = _board_proto("GetBoardEditorAppearanceSettings")
    AppearanceSettings = _board_proto("BoardEditorAppearanceSettings")
    resp = _wrap("GetBoardEditorAppearanceSettings",
                 lambda: client.send(GetAppearance(), AppearanceSettings))
    return {
        "inactive_layer_display": int(
            getattr(resp, "inactive_layer_display", 0)),
        "net_color_display": int(getattr(resp, "net_color_display", 0)),
        "board_flip": int(getattr(resp, "board_flip", 0)),
        "ratsnest_display": int(getattr(resp, "ratsnest_display", 0)),
    }
