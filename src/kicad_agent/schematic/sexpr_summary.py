"""S-expression schematic summarizer (cascade Step 2).

Pure functions turning `.kicad_sch` text — from a file OR from live
`SaveDocumentToString` contents — into the same summary shapes the IPC
Part 5 path produces, so downstream code is source-agnostic.

Scope: instance blocks at the `kicad_sch` root (symbol/wire/bus/junction/
label family/sheet). Library definitions (`lib_symbols`), sheet-instance
bookkeeping, fonts, and header keys are known-skipped, never counted.
Any other top-level block is recorded under `unknown_blocks`, never faked.
Pin-level net mapping is out of scope (needs library pin geometry); use
the wire-graph step for connectivity.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..backends.sexpr import parse_sexp

# Top-level keys that carry no instances.
_SKIP_ROOT_TAGS = frozenset({
    "version", "generator", "generator_version", "uuid", "paper",
    "lib_symbols", "sheet_instances", "embedded_fonts", "title_block",
})

_LABEL_KIND = {
    "label": "local_label",
    "global_label": "global_label",
    "hierarchical_label": "hierarchical_label",
    "directive_label": "directive_label",
}


def unquote(token: Any) -> str:
    """Strip one layer of double quotes from a parsed token."""
    if not isinstance(token, str):
        return ""
    token = token.strip()
    if len(token) >= 2 and token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    return token


def to_float(token: Any, default: float = 0.0) -> float:
    try:
        return float(unquote(token))
    except (TypeError, ValueError):
        return default


def find_child(block: list, tag: str) -> Optional[list]:
    """First direct sublist of block whose head equals tag."""
    for node in block[1:]:
        if isinstance(node, list) and node and node[0] == tag:
            return node
    return None


def children_of(block: list, tag: str) -> List[list]:
    return [n for n in block[1:]
            if isinstance(n, list) and n and n[0] == tag]


def at_xy(block: list) -> Tuple[float, float]:
    at = find_child(block, "at")
    if at is None or len(at) < 3:
        return (0.0, 0.0)
    return (to_float(at[1]), to_float(at[2]))


def property_value(block: list, name: str) -> str:
    for prop in children_of(block, "property"):
        if len(prop) >= 3 and unquote(prop[1]) == name:
            return unquote(prop[2])
    return ""


def uuid_of(block: list) -> str:
    uuid = find_child(block, "uuid")
    if uuid is not None and len(uuid) >= 2:
        return unquote(uuid[1])
    return ""


def summarize_symbol(block: list) -> Dict[str, Any]:
    lib = find_child(block, "lib_id")
    x, y = at_xy(block)
    return {
        "id": uuid_of(block),
        "reference": property_value(block, "Reference"),
        "value": property_value(block, "Value"),
        "lib_id": unquote(lib[1]) if lib is not None and len(lib) >= 2 else "",
        "x_mm": x,
        "y_mm": y,
    }


def summarize_wire(block: list, kind: str) -> List[Dict[str, Any]]:
    """One entry per segment (polylines share the wire id)."""
    pts = find_child(block, "pts")
    points: List[List[float]] = []
    if pts is not None:
        for node in pts[1:]:
            if isinstance(node, list) and node and node[0] == "xy" and len(node) >= 3:
                points.append([to_float(node[1]), to_float(node[2])])
    wire_id = uuid_of(block)
    segments = []
    for i in range(max(len(points) - 1, 0)):
        segments.append({
            "id": wire_id,
            "kind": kind,
            "segment_index": i,
            "start_mm": points[i],
            "end_mm": points[i + 1],
        })
    if not segments:
        segments.append({
            "id": wire_id, "kind": kind, "segment_index": 0,
            "start_mm": [0.0, 0.0], "end_mm": [0.0, 0.0],
        })
    return segments


def summarize_junction(block: list) -> Dict[str, Any]:
    x, y = at_xy(block)
    return {"id": uuid_of(block), "x_mm": x, "y_mm": y}


def summarize_label(block: list) -> Dict[str, Any]:
    tag = block[0] if block else ""
    text = unquote(block[1]) if len(block) >= 2 and isinstance(block[1], str) else ""
    x, y = at_xy(block)
    return {
        "id": uuid_of(block),
        "label_type": _LABEL_KIND.get(tag, tag),
        "text": text,
        "x_mm": x,
        "y_mm": y,
    }


def summarize_sheet(block: list) -> Dict[str, Any]:
    return {
        "id": uuid_of(block),
        "name": property_value(block, "Sheetname"),
        "filename": property_value(block, "Sheetfile"),
    }


def summarize_schematic_text(contents: str) -> Dict[str, Any]:
    """Summarize a `.kicad_sch` document string (file or live text)."""
    if not contents or not contents.strip():
        raise ValueError("Cannot summarize empty schematic text.")
    try:
        ast = parse_sexp(contents)
    except Exception as e:
        raise ValueError(f"S-expression parse failed: {e}") from e
    if not isinstance(ast, list) or not ast or ast[0] != "kicad_sch":
        raise ValueError("Not a KiCad schematic document (missing kicad_sch root).")

    summary: Dict[str, Any] = {
        "symbols": [], "wires": [], "junctions": [], "labels": [],
        "sheets": [], "unknown_blocks": [],
    }
    for node in ast[1:]:
        if not isinstance(node, list) or not node:
            continue
        tag = node[0]
        if tag in _SKIP_ROOT_TAGS:
            continue
        if tag == "symbol":
            summary["symbols"].append(summarize_symbol(node))
        elif tag == "wire":
            summary["wires"].extend(summarize_wire(node, "wire"))
        elif tag == "bus":
            summary["wires"].extend(summarize_wire(node, "bus"))
        elif tag == "junction":
            summary["junctions"].append(summarize_junction(node))
        elif tag in _LABEL_KIND:
            summary["labels"].append(summarize_label(node))
        elif tag == "sheet":
            summary["sheets"].append(summarize_sheet(node))
        else:
            summary["unknown_blocks"].append({"type": str(tag)})
    return summary
