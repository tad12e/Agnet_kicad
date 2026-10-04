"""Library pin geometry for KiCad schematics (source-agnostic).

Resolves a placed symbol's pin tips in board coordinates from the
installed KiCad symbol libraries, and checks wire-endpoint connectivity
against those tips. Works on raw `.kicad_sch` text, so file edits and
live `SaveDocumentToString` output share one code path.

Verified pin rule (KiCad 10.0 libs): a lib pin's `(at X Y)` IS the wire
connection tip in symbol-local coordinates. Instance rotation is
counter-clockwise, applied before translation.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional, Tuple

from ..backends.sexpr import (
    find_symbol_in_lib,
    get_symbol_pins_from_def,
    parse_sexp,
)
from ..utils.paths import get_kicad_symbols_dir
from .sexpr_summary import summarize_schematic_text

_TOL_DEFAULT_MM = 0.02


# =============================================================================
# Rotation (counter-clockwise, degrees)
# =============================================================================

def rotate_point_ccw(x: float, y: float, angle_deg: float) -> Tuple[float, float]:
    """Rotate (x, y) counter-clockwise about the origin."""
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)


# =============================================================================
# Library definition resolution (extends-aware)
# =============================================================================

def _rename_symbol_tree(node: Any, src_base: str, dst_base: str) -> None:
    """Rename a (symbol "SRC...") node and its unit children to DST... in place."""
    if isinstance(node, list) and node and node[0] == "symbol" and len(node) > 1:
        name = node[1].strip('"') if isinstance(node[1], str) else ""
        if name == src_base or name.startswith(src_base + "_"):
            node[1] = f'"{dst_base}{name[len(src_base):]}"'
    if isinstance(node, list):
        for child in node:
            if isinstance(child, list):
                _rename_symbol_tree(child, src_base, dst_base)


def _unit_subsymbol(tree: List[Any], unit: int = 1) -> Optional[List[Any]]:
    """Unit sub-symbol block (e.g. LM358_1_1), preferring pin-carrying units."""
    def _scan(suffix: str) -> Optional[List[Any]]:
        for item in tree:
            if isinstance(item, list) and len(item) > 1 and item[0] == "symbol":
                name = item[1].strip('"') if isinstance(item[1], str) else ""
                if name.endswith(suffix):
                    has_pins = any(
                        isinstance(sub, list) and sub and sub[0] == "pin"
                        for sub in item
                    )
                    if has_pins:
                        return item
        return None

    return _scan(f"_{unit}_1") or _scan(f"_{unit}")


def resolve_lib_def(
    lib_name: str, symbol_name: str, unit: int = 1
) -> Tuple[Optional[List[Any]], List[str]]:
    """Resolve a library symbol to a standalone definition tree + unit pins.

    Handles `extends' aliases (LM358 -> LM2904) by copying the parent and
    renaming unit children. Returns (tree_or_None, pin_numbers); the pin
    fallback is ["1", "2"] when the library is missing or unparsable.
    """
    fallback_pins = ["1", "2"]
    if not lib_name:
        return None, fallback_pins
    lib_file = os.path.join(get_kicad_symbols_dir(), f"{lib_name}.kicad_sym")
    if not os.path.exists(lib_file):
        return None, fallback_pins
    try:
        with open(lib_file, "r", encoding="utf-8", errors="ignore") as f:
            lib_content = f.read()
        lib_sexp = parse_sexp(lib_content)
        resolved = find_symbol_in_lib(lib_sexp, symbol_name)
        if resolved is None:
            return None, fallback_pins
        src_base = symbol_name
        for item in lib_sexp:
            if isinstance(item, list) and len(item) > 1 and item[0] == "symbol":
                nm = item[1].strip('"') if isinstance(item[1], str) else ""
                if nm == symbol_name:
                    for sub in item:
                        if (isinstance(sub, list) and sub
                                and sub[0] == "extends" and len(sub) > 1):
                            src_base = sub[1].strip('"')
                            break
                    break
        _rename_symbol_tree(resolved, src_base, symbol_name)
        unit_block = _unit_subsymbol(resolved, unit=unit)
        pins = get_symbol_pins_from_def(unit_block) if unit_block else fallback_pins
        return resolved, pins or fallback_pins
    except Exception:
        return None, fallback_pins


def unit_pin_positions(
    tree: List[Any], unit: int = 1
) -> Dict[str, Tuple[float, float]]:
    """Pin-number -> (x, y) lib-local tip coordinates for one unit."""
    from .sexpr_summary import find_child, to_float

    tips: Dict[str, Tuple[float, float]] = {}
    unit_block = _unit_subsymbol(tree, unit=unit)
    if unit_block is None:
        return tips
    for sub in unit_block:
        if not (isinstance(sub, list) and sub and sub[0] == "pin"):
            continue
        at = find_child(sub, "at")
        num = find_child(sub, "number")
        if at is None or num is None or len(at) < 3 or len(num) < 2:
            continue
        number = num[1].strip('"') if isinstance(num[1], str) else ""
        if number:
            tips[number] = (to_float(at[1]), to_float(at[2]))
    return tips


def resolve_pin_tips(
    lib_id: str, x_mm: float, y_mm: float, rotation_deg: float = 0.0, unit: int = 1
) -> Optional[Dict[str, Tuple[float, float]]]:
    """Pin-number -> board-coordinate tips for a placed symbol.

    Returns None when the library cannot be resolved (caller must skip
    pin checks honestly instead of guessing).
    """
    if ":" in lib_id:
        lib_name, symbol_name = lib_id.split(":", 1)
    else:
        lib_name, symbol_name = "", lib_id
    tree, _pins = resolve_lib_def(lib_name, symbol_name, unit=unit)
    if tree is None:
        return None
    local = unit_pin_positions(tree, unit=unit)
    if not local:
        return None
    tips = {}
    for number, (lx, ly) in local.items():
        rx, ry = rotate_point_ccw(lx, ly, rotation_deg)
        tips[number] = (x_mm + rx, y_mm + ry)
    return tips


# =============================================================================
# Wire-endpoint connectivity report
# =============================================================================

def _close(a: Tuple[float, float], b: Tuple[float, float], tol: float) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def endpoint_report(
    sch_text: str, tol_mm: float = _TOL_DEFAULT_MM
) -> Dict[str, Any]:
    """Check every wire/bus segment endpoint for a landing point.

    Landing points: pin tips (lib-resolved), junction dots, label anchors,
    other segment endpoints (elbows OK, 3+-way meets without a junction dot
    are errors, dangling ends are errors, unconnected pins are warnings).
    """
    summary = summarize_schematic_text(sch_text)
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    # Structural checks that need no library geometry.
    refs: Dict[str, int] = {}
    for sym in summary["symbols"]:
        refs[sym["reference"]] = refs.get(sym["reference"], 0) + 1
    for ref, count in refs.items():
        if ref and count > 1:
            errors.append({
                "kind": "duplicate_reference",
                "reference": ref,
                "message": f"Reference '{ref}' appears {count} times",
            })

    # Pin tips per symbol.
    pin_tips: List[Tuple[Tuple[float, float], str, str]] = []  # ((x,y), ref, pin)
    unresolved: List[str] = []
    for sym in summary["symbols"]:
        tips = resolve_pin_tips(
            sym.get("lib_id", ""), sym.get("x_mm", 0.0), sym.get("y_mm", 0.0),
            sym.get("rotation", 0.0),
        )
        if tips is None:
            unresolved.append(f"{sym.get('reference', '?')} ({sym.get('lib_id', '?')})")
        else:
            for number, pos in tips.items():
                pin_tips.append((pos, sym.get("reference", ""), number))
    if unresolved:
        warnings.append({
            "kind": "unresolved_library",
            "message": "Pin checks skipped for symbols whose library is missing: "
                       + ", ".join(sorted(set(unresolved))),
        })

    junctions = [(j["x_mm"], j["y_mm"]) for j in summary["junctions"]]
    labels = [(label["x_mm"], label["y_mm"]) for label in summary["labels"]]
    segments = summary["wires"]
    ends: List[Tuple[float, float]] = []
    for seg in segments:
        ends.append(tuple(seg["start_mm"]))
        ends.append(tuple(seg["end_mm"]))

    def _coincidences(pt: Tuple[float, float]) -> Dict[str, int]:
        found = {"pins": 0, "junctions": 0, "labels": 0, "ends": 0}
        for tip, _ref, _num in pin_tips:
            if _close(pt, tip, tol_mm):
                found["pins"] += 1
        for jpos in junctions:
            if _close(pt, jpos, tol_mm):
                found["junctions"] += 1
        for lpos in labels:
            if _close(pt, lpos, tol_mm):
                found["labels"] += 1
        for epos in ends:
            if _close(pt, epos, tol_mm):
                found["ends"] += 1
        return found

    seen: set = set()
    for seg in segments:
        for role in ("start_mm", "end_mm"):
            pt = tuple(seg[role])
            key = (round(pt[0], 3), round(pt[1], 3))
            if key in seen:
                continue
            seen.add(key)
            coin = _coincidences(pt)
            # Segment's own two ends each counted once in "ends".
            other_ends = coin["ends"] - 1
            foreign = coin["pins"] + coin["junctions"] + coin["labels"]
            if foreign > 0:
                continue  # landed on a pin, junction, or label
            if other_ends == 0:
                errors.append({
                    "kind": "dangling_end",
                    "wire_id": seg["id"],
                    "point": [pt[0], pt[1]],
                    "message": f"Wire end at ({pt[0]}, {pt[1]}) lands on nothing",
                })
            elif other_ends >= 2:
                errors.append({
                    "kind": "missing_junction",
                    "wire_id": seg["id"],
                    "point": [pt[0], pt[1]],
                    "message": f"{other_ends + 1} wire ends meet at "
                               f"({pt[0]}, {pt[1]}) with no junction dot",
                })
            # other_ends == 1 -> plain elbow, fine.

    # Unconnected pins (warnings: legitimate NC cases exist).
    for tip, ref, number in pin_tips:
        if not any(_close(tip, epos, tol_mm) for epos in ends):
            warnings.append({
                "kind": "unconnected_pin",
                "reference": ref,
                "pin": number,
                "message": f"{ref} pin {number} at ({tip[0]}, {tip[1]}) has no wire",
            })

    return {
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "symbols": len(summary["symbols"]),
            "wire_segments": len(segments),
            "junctions": len(junctions),
            "labels": len(labels),
            "unresolved_libraries": len(set(unresolved)),
        },
    }
