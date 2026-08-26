"""KiCad S-Expression Engine based on Microsoft's open-source SchGen project.

Used for KiCad 10.x schematic symbol placement where the live IPC CreateItems
API has a known C++ nullptr dereference bug in KiCad 10.0.4.
For KiCad 11+, the live IPC API is used directly.
"""

import os
import re
import uuid
import copy
from typing import Any, List, Optional, Tuple


def get_kicad_symbols_dir() -> str:
    """Return the KiCad system symbol libraries directory."""
    candidates = [
        r"C:\Program Files\KiCad\10.0\share\kicad\symbols",
        r"C:\Program Files\KiCad\9.0\share\kicad\symbols",
        r"C:\Program Files\KiCad\8.0\share\kicad\symbols",
        "/usr/share/kicad/symbols",
        "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols",
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0]


def parse_sexp(sexp_str: str) -> List[Any]:
    """Parse an S-expression string into nested Python lists (Microsoft SchGen implementation)."""
    sexp_str = sexp_str.replace('(', ' ( ').replace(')', ' ) ')
    tokens = re.findall(r'[()]|"(?:\\.|[^"])*"|[^()\s]+', sexp_str)
    tokens = [t.strip() for t in tokens if t.strip()]

    stack: List[List[Any]] = []
    for token in tokens:
        if token == '(':
            stack.append([])
        elif token == ')':
            if len(stack) > 1:
                closed = stack.pop()
                stack[-1].append(closed)
        else:
            stack[-1].append(token)
    return stack[0] if stack else []


def format_sexp(sexp: Any, indent: int = 0, indent_size: int = 2) -> str:
    """Format nested lists back into a formatted KiCad S-expression string."""
    if not isinstance(sexp, list):
        return str(sexp)

    if not sexp:
        return "()"

    result = []
    result.append("(" + format_sexp(sexp[0]))

    for item in sexp[1:]:
        if isinstance(item, list):
            result.append("\n" + " " * (indent + indent_size))
            result.append(format_sexp(item, indent + indent_size, indent_size))
        else:
            result.append(" " + format_sexp(item))

    result.append(")")
    return "".join(result)


def find_symbol_in_lib(lib_sexp: List[Any], symbol_name: str) -> Optional[List[Any]]:
    """Find a symbol definition in a KiCad .kicad_sym file, resolving 'extends' if needed."""
    target_clean = symbol_name.strip('"')
    for item in lib_sexp:
        if isinstance(item, list) and len(item) > 1 and item[0] == 'symbol':
            name = item[1].strip('"')
            if name == target_clean:
                # Check for 'extends'
                if len(item) > 2 and isinstance(item[2], list) and item[2] and item[2][0] == 'extends':
                    extends_source = item[2][1].strip('"')
                    ext_item = None
                    for candidate in lib_sexp:
                        if isinstance(candidate, list) and len(candidate) > 1 and candidate[0] == 'symbol':
                            if candidate[1].strip('"') == extends_source:
                                ext_item = candidate
                                break
                    if ext_item:
                        combined = copy.deepcopy(ext_item)
                        combined[1] = f'"{target_clean}"'
                        return combined
                return copy.deepcopy(item)
    return None


def get_symbol_pins_from_def(sym_def: List[Any]) -> List[str]:
    """Extract pin numbers from a symbol definition S-expression."""
    pins = []
    def _search(node: Any):
        if isinstance(node, list):
            if node and node[0] == 'pin' and len(node) > 2:
                # find number
                for sub in node:
                    if isinstance(sub, list) and sub and sub[0] == 'number' and len(sub) > 1:
                        pins.append(sub[1].strip('"'))
            for child in node:
                _search(child)
    _search(sym_def)
    return sorted(list(set(pins))) if pins else ["1", "2"]


def add_symbol_to_schematic(
    sch_path: str,
    lib_name: str,
    symbol_name: str,
    reference: str,
    value: str,
    pos_x_mm: float,
    pos_y_mm: float,
    footprint: str = "",
    rotation: float = 0,
    project_name: Optional[str] = None,
    sheet_uuid: Optional[str] = None,
) -> str:
    """Insert a symbol into a KiCad schematic file via S-expression manipulation.

    Returns the assigned symbol instance UUID.
    """
    with open(sch_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract root sheet UUID if not supplied
    if not sheet_uuid:
        m = re.search(r'\(uuid\s+"?([0-9a-fA-F\-]{36})"?\)', content[:4096])
        sheet_uuid = m.group(1) if m else str(uuid.uuid4())

    # Extract project name if not supplied
    if not project_name:
        base = os.path.splitext(os.path.basename(sch_path))[0]
        project_name = base

    sym_uuid = str(uuid.uuid4())
    full_lib_id = f"{lib_name}:{symbol_name}"

    # Check if symbol definition is already in lib_symbols
    lib_symbols_pattern = r'\(lib_symbols\b'
    has_lib_symbols = bool(re.search(lib_symbols_pattern, content))

    has_sym_in_lib = f'(symbol "{full_lib_id}"' in content or f'(symbol {full_lib_id}' in content

    sym_pins = ["1", "2"]

    if not has_sym_in_lib:
        # Load from KiCad symbol library
        symbols_dir = get_kicad_symbols_dir()
        lib_file = os.path.join(symbols_dir, f"{lib_name}.kicad_sym")
        if os.path.exists(lib_file):
            with open(lib_file, "r", encoding="utf-8", errors="ignore") as f:
                lib_content = f.read()
            lib_tree = parse_sexp(lib_content)
            sym_def = find_symbol_in_lib(lib_tree, symbol_name)
            if sym_def:
                sym_pins = get_symbol_pins_from_def(sym_def)
                # Rename the top symbol in definition to full_lib_id
                sym_def[1] = f'"{full_lib_id}"'
                sym_def_str = format_sexp(sym_def, indent=2, indent_size=2)

                if has_lib_symbols:
                    # Insert right after (lib_symbols
                    idx = content.find("(lib_symbols")
                    if idx != -1:
                        insert_pos = idx + len("(lib_symbols")
                        content = content[:insert_pos] + "\n    " + sym_def_str + content[insert_pos:]
                else:
                    # Insert new lib_symbols block after (paper ...)
                    m_paper = re.search(r'\(paper\s+"[^"]+"\)', content)
                    if m_paper:
                        insert_pos = m_paper.end()
                        content = (
                            content[:insert_pos]
                            + f"\n  (lib_symbols\n    {sym_def_str}\n  )"
                            + content[insert_pos:]
                        )

    # Build the symbol instance S-expression
    pin_blocks = []
    for p in sym_pins:
        p_uuid = str(uuid.uuid4())
        pin_blocks.append(f'    (pin "{p}" (uuid "{p_uuid}"))')
    pins_str = "\n".join(pin_blocks)

    instance_sexp = f"""  (symbol
    (lib_id "{full_lib_id}")
    (at {pos_x_mm} {pos_y_mm} {rotation})
    (unit 1)
    (body_style 1)
    (exclude_from_sim no)
    (in_bom yes)
    (on_board yes)
    (in_pos_files yes)
    (dnp no)
    (fields_autoplaced yes)
    (uuid "{sym_uuid}")
    (property "Reference" "{reference}"
      (at {pos_x_mm + 2.54} {pos_y_mm - 1.27} 0)
      (effects (font (size 1.27 1.27)) (justify left))
    )
    (property "Value" "{value}"
      (at {pos_x_mm + 2.54} {pos_y_mm + 1.27} 0)
      (effects (font (size 1.27 1.27)) (justify left))
    )
    (property "Footprint" "{footprint}"
      (at {pos_x_mm} {pos_y_mm} 0)
      (hide yes)
      (effects (font (size 1.27 1.27)))
    )
    (property "Datasheet" "~"
      (at {pos_x_mm} {pos_y_mm} 0)
      (hide yes)
      (effects (font (size 1.27 1.27)))
    )
    (property "Description" "{value} {symbol_name}"
      (at {pos_x_mm} {pos_y_mm} 0)
      (hide yes)
      (effects (font (size 1.27 1.27)))
    )
{pins_str}
    (instances
      (project "{project_name}"
        (path "/{sheet_uuid}"
          (reference "{reference}")
          (unit 1)
        )
      )
    )
  )"""

    # Insert symbol before the final closing parenthesis of the schematic
    last_paren = content.rfind(")")
    if last_paren != -1:
        new_content = content[:last_paren].rstrip() + "\n" + instance_sexp + "\n)\n"
    else:
        new_content = content + "\n" + instance_sexp + "\n)\n"

    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return sym_uuid


def add_wire_to_schematic(
    sch_path: str,
    start: Tuple[float, float],
    end: Tuple[float, float],
) -> str:
    """Insert a wire connection into a KiCad schematic file via S-expression.

    Args:
        sch_path: Absolute path to the .kicad_sch file.
        start: (x, y) starting coordinate in mm.
        end: (x, y) ending coordinate in mm.

    Returns:
        The wire UUID string.
    """
    wire_uuid = str(uuid.uuid4())
    wire_sexp = f"""  (wire
    (pts
      (xy {start[0]} {start[1]}) (xy {end[0]} {end[1]})
    )
    (stroke
      (width 0)
      (type default)
    )
    (uuid "{wire_uuid}")
  )"""

    with open(sch_path, "r", encoding="utf-8") as f:
        content = f.read()

    last_paren = content.rfind(")")
    if last_paren != -1:
        new_content = content[:last_paren].rstrip() + "\n" + wire_sexp + "\n)\n"
    else:
        new_content = content + "\n" + wire_sexp + "\n)\n"

    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return wire_uuid

