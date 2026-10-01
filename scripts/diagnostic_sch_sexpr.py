"""Schematic S-expression file probe (read-only).

Usage:
    python scripts/diagnostic_sch_sexpr.py [path/to/file.kicad_sch]

Checks, without modifying the file:
  1. S-expression structure (root tag, paren balance outside strings)
  2. Block counts (symbols / wire segments / junctions / labels / sheets)
  3. Dangling `extends' references in (lib_symbols ...)
  4. Duplicate reference designators
  5. Wire-endpoint connectivity (pin tips via installed KiCad libs,
     junction dots, label anchors, other wire ends)
  6. Unconnected pins (warnings: legitimate NC cases exist)

Exit code 0 = no errors (warnings allowed), 1 = errors found.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from kicad_agent.backends.sexpr import parse_sexp  # noqa: E402
from kicad_agent.schematic.pin_geometry import endpoint_report  # noqa: E402
from kicad_agent.schematic.sexpr_summary import (  # noqa: E402
    summarize_schematic_text,
    unquote,
)


def _paren_balance_outside_strings(text: str) -> tuple:
    depth = 0
    min_depth = 0
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                min_depth = min(min_depth, depth)
    return depth, min_depth


def _dangling_extends(ast: list) -> list:
    defined = set()
    extends_refs = []

    def _walk(node, in_lib=False):
        if isinstance(node, list) and node:
            if node[0] == "symbol" and len(node) > 1 and in_lib:
                name = node[1].strip('"') if isinstance(node[1], str) else ""
                if ":" in name:
                    name = name.split(":", 1)[1]
                defined.add(name)
            if node[0] == "extends" and len(node) > 1:
                extends_refs.append(unquote(node[1]))
            for child in node:
                _walk(child, in_lib or (node[0] == "lib_symbols"))

    for child in ast[1:]:
        _walk(child, False)
    # Top-level instance lib_ids also define usable names.
    return sorted({r for r in extends_refs if r not in defined})


def main() -> int:
    if len(sys.argv) > 1:
        sch_path = sys.argv[1]
    else:
        repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        first = os.path.join(repo, "first.kicad_sch")
        fixture = os.path.join(
            repo, "tests", "fixtures", "schematic", "simple_schematic.kicad_sch"
        )
        sch_path = first if os.path.exists(first) else fixture

    print("=" * 60)
    print("Schematic S-expr probe (read-only)")
    print(f"File: {sch_path}")
    print("=" * 60)

    if not os.path.exists(sch_path):
        print(f"[FAIL] file not found: {sch_path}")
        return 1
    with open(sch_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    errors: list = []
    warnings: list = []

    # 1. Structure.
    print("\n--- 1. Structure ---")
    depth, min_depth = _paren_balance_outside_strings(content)
    print(f"paren balance: depth={depth} min_depth={min_depth}")
    if depth != 0 or min_depth < 0:
        errors.append("unbalanced parentheses outside strings")
    try:
        ast = parse_sexp(content)
    except Exception as e:
        print(f"[FAIL] parse error: {e}")
        return 1
    if not ast or ast[0] != "kicad_sch":
        print("[FAIL] missing kicad_sch root")
        return 1
    print("root: kicad_sch OK")

    # 2. Counts.
    print("\n--- 2. Blocks ---")
    try:
        summary = summarize_schematic_text(content)
    except ValueError as e:
        print(f"[FAIL] {e}")
        return 1
    print(f"symbols:   {len(summary['symbols'])}")
    print(f"wire segs: {len(summary['wires'])}")
    print(f"junctions: {len(summary['junctions'])}")
    print(f"labels:    {len(summary['labels'])}")
    print(f"sheets:    {len(summary['sheets'])}")
    if summary["unknown_blocks"]:
        kinds = sorted({b["type"] for b in summary["unknown_blocks"]})
        warnings.append(f"unknown top-level blocks: {kinds}")
        print(f"unknown:   {kinds}")

    # 3. Dangling extends.
    print("\n--- 3. Library references ---")
    dangling = _dangling_extends(ast)
    if dangling:
        errors.append(f"dangling extends: {dangling}")
        print(f"[ERROR] dangling extends: {dangling}")
    else:
        print("extends: all resolved in-file")

    # 4+5+6. Connectivity report.
    print("\n--- 4. Connectivity ---")
    report = endpoint_report(content)
    stats = report["stats"]
    print(f"unresolved libraries: {stats['unresolved_libraries']}")
    for w in report["warnings"]:
        warnings.append(w["message"])
        print(f"[WARN] {w['message']}")
    for e in report["errors"]:
        errors.append(e["message"])
        print(f"[ERROR] {e['message']}")
    if not report["errors"] and not report["warnings"]:
        print("all wire ends land on pins/junctions/labels/elbows")

    print("\n" + "=" * 60)
    if errors:
        print(f"RESULT: FAIL ({len(errors)} errors, {len(warnings)} warnings)")
        return 1
    print(f"RESULT: CLEAN ({len(warnings)} warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
