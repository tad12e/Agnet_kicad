"""KiCad S-Expression Backend & Serialization Engine.

Provides safe S-expression parsing, formatting, and manipulation for:
- PCB files (.kicad_pcb): footprints, tracks, vias, zones
- Schematic files (.kicad_sch): symbols, wires, lib_symbols, sheet instances
"""

from __future__ import annotations

import copy
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..core.actions import Action, ActionType
from ..core.errors import AgentError, ErrorCategory
from ..core.results import ActionResult
from ..utils.paths import get_kicad_footprints_dir, get_kicad_symbols_dir
from .base import KiCadBackend


# ===========================================================================
# S-Expression Parser & Formatter
# ===========================================================================

def parse_sexp(sexp_str: str) -> List[Any]:
    """Parse an S-expression string into nested Python lists."""
    sexp_str = sexp_str.replace("(", " ( ").replace(")", " ) ")
    tokens = re.findall(r'[()]|"(?:\\.|[^"])*"|[^()\s]+', sexp_str)
    tokens = [t.strip() for t in tokens if t.strip()]

    stack: List[List[Any]] = []
    for token in tokens:
        if token == "(":
            stack.append([])
        elif token == ")":
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

    result = ["(" + format_sexp(sexp[0])]

    for item in sexp[1:]:
        if isinstance(item, list):
            result.append("\n" + " " * (indent + indent_size))
            result.append(format_sexp(item, indent + indent_size, indent_size))
        else:
            result.append(" " + format_sexp(item))

    result.append(")")
    return "".join(result)


# ===========================================================================
# PCB S-Expression Operations
# ===========================================================================

def load_footprint_mod(lib_name: str, mod_name: str) -> Optional[List[Any]]:
    """Load a footprint definition (.kicad_mod) from a .pretty library."""
    footprints_dir = get_kicad_footprints_dir()
    pretty_dir = os.path.join(footprints_dir, f"{lib_name}.pretty")
    mod_file = os.path.join(pretty_dir, f"{mod_name}.kicad_mod")

    if not os.path.exists(mod_file):
        return None

    try:
        with open(mod_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return parse_sexp(content)
    except Exception:
        return None


def add_footprint_to_pcb(
    pcb_path: str,
    footprint_id: str,
    reference: str,
    value: str,
    pos_x_mm: float,
    pos_y_mm: float,
    layer: str = "F.Cu",
    rotation: float = 0,
) -> str:
    """Add a footprint to a .kicad_pcb file."""
    fp_uuid = str(uuid.uuid4())

    if ":" in footprint_id:
        lib_name, mod_name = footprint_id.split(":", 1)
    else:
        lib_name, mod_name = "", footprint_id

    mod_tree = load_footprint_mod(lib_name, mod_name) if lib_name else None

    if mod_tree and isinstance(mod_tree, list) and len(mod_tree) > 1:
        fp = copy.deepcopy(mod_tree)
        fp[0] = "footprint"
        fp[1] = f'"{footprint_id}"'

        has_layer = False
        has_at = False
        has_uuid = False

        for item in fp:
            if isinstance(item, list) and item:
                tag = item[0]
                if tag == "layer":
                    item[1] = f'"{layer}"'
                    has_layer = True
                elif tag == "at":
                    item[1] = str(pos_x_mm)
                    item[2] = str(pos_y_mm)
                    if rotation != 0:
                        if len(item) > 3:
                            item[3] = str(rotation)
                        else:
                            item.append(str(rotation))
                    has_at = True
                elif tag == "uuid":
                    item[1] = f'"{fp_uuid}"'
                    has_uuid = True
                elif tag == "property" and len(item) > 2:
                    prop_name = item[1].strip('"')
                    if prop_name == "Reference":
                        item[2] = f'"{reference}"'
                    elif prop_name == "Value":
                        item[2] = f'"{value}"'

        if not has_layer:
            fp.insert(2, ["layer", f'"{layer}"'])
        if not has_at:
            at_item = ["at", str(pos_x_mm), str(pos_y_mm)]
            if rotation != 0:
                at_item.append(str(rotation))
            fp.insert(3, at_item)
        if not has_uuid:
            fp.insert(4, ["uuid", f'"{fp_uuid}"'])

        fp_sexp = format_sexp(fp, indent=2, indent_size=2)
    else:
        fp_sexp = f"""  (footprint "{footprint_id}"
    (layer "{layer}")
    (uuid "{fp_uuid}")
    (at {pos_x_mm} {pos_y_mm} {rotation})
    (property "Reference" "{reference}"
      (at 0 -1.5 0)
      (layer "F.SilkS")
      (uuid "{uuid.uuid4()}")
      (effects (font (size 1 1) (thickness 0.15)))
    )
    (property "Value" "{value}"
      (at 0 1.5 0)
      (layer "F.Fab")
      (uuid "{uuid.uuid4()}")
      (effects (font (size 1 1) (thickness 0.15)))
    )
    (property "Footprint" "{footprint_id}"
      (at 0 0 0)
      (layer "F.Fab")
      (hide yes)
      (uuid "{uuid.uuid4()}")
      (effects (font (size 1 1) (thickness 0.15)))
    )
  )"""

    with open(pcb_path, "r", encoding="utf-8") as f:
        content = f.read()

    last_paren = content.rfind(")")
    if last_paren != -1:
        new_content = content[:last_paren].rstrip() + "\n" + fp_sexp + "\n)\n"
    else:
        new_content = content + "\n" + fp_sexp + "\n)\n"

    with open(pcb_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return fp_uuid


def add_track_to_pcb(
    pcb_path: str,
    start: Tuple[float, float],
    end: Tuple[float, float],
    width_mm: float = 0.25,
    layer: str = "F.Cu",
    net: int = 0,
) -> str:
    """Add a copper track segment to a .kicad_pcb file."""
    track_uuid = str(uuid.uuid4())
    segment_sexp = f"""  (segment
    (start {start[0]} {start[1]})
    (end {end[0]} {end[1]})
    (width {width_mm})
    (layer "{layer}")
    (net {net})
    (uuid "{track_uuid}")
  )"""

    with open(pcb_path, "r", encoding="utf-8") as f:
        content = f.read()

    last_paren = content.rfind(")")
    if last_paren != -1:
        new_content = content[:last_paren].rstrip() + "\n" + segment_sexp + "\n)\n"
    else:
        new_content = content + "\n" + segment_sexp + "\n)\n"

    with open(pcb_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return track_uuid


def add_via_to_pcb(
    pcb_path: str,
    at: Tuple[float, float],
    size_mm: float = 0.8,
    drill_mm: float = 0.4,
    layers: Tuple[str, str] = ("F.Cu", "B.Cu"),
    net: int = 0,
) -> str:
    """Add a via to a .kicad_pcb file."""
    via_uuid = str(uuid.uuid4())
    via_sexp = f"""  (via
    (at {at[0]} {at[1]})
    (size {size_mm})
    (drill {drill_mm})
    (layers "{layers[0]}" "{layers[1]}")
    (net {net})
    (uuid "{via_uuid}")
  )"""

    with open(pcb_path, "r", encoding="utf-8") as f:
        content = f.read()

    last_paren = content.rfind(")")
    if last_paren != -1:
        new_content = content[:last_paren].rstrip() + "\n" + via_sexp + "\n)\n"
    else:
        new_content = content + "\n" + via_sexp + "\n)\n"

    with open(pcb_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return via_uuid


def add_zone_to_pcb(
    pcb_path: str,
    polygon: List[Tuple[float, float]],
    layer: str = "F.Cu",
    net: int = 0,
    net_name: str = "",
) -> str:
    """Add a copper polygon zone/pour to a .kicad_pcb file."""
    zone_uuid = str(uuid.uuid4())
    pts_str = " ".join([f"(xy {pt[0]} {pt[1]})" for pt in polygon])

    zone_sexp = f"""  (zone
    (net {net})
    (net_name "{net_name}")
    (layers "{layer}")
    (uuid "{zone_uuid}")
    (hatch edge 0.5)
    (connect_pads (clearance 0.5))
    (min_thickness 0.25)
    (filled_areas_thickness no)
    (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))
    (polygon
      (pts
        {pts_str}
      )
    )
  )"""

    with open(pcb_path, "r", encoding="utf-8") as f:
        content = f.read()

    last_paren = content.rfind(")")
    if last_paren != -1:
        new_content = content[:last_paren].rstrip() + "\n" + zone_sexp + "\n)\n"
    else:
        new_content = content + "\n" + zone_sexp + "\n)\n"

    with open(pcb_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return zone_uuid


# ===========================================================================
# Schematic S-Expression Operations
# ===========================================================================

def find_symbol_in_lib(lib_sexp: List[Any], symbol_name: str) -> Optional[List[Any]]:
    """Find a symbol definition in a KiCad .kicad_sym file, resolving 'extends' if needed."""
    target_clean = symbol_name.strip('"')
    for item in lib_sexp:
        if isinstance(item, list) and len(item) > 1 and item[0] == "symbol":
            name = item[1].strip('"')
            if name == target_clean:
                if len(item) > 2 and isinstance(item[2], list) and item[2] and item[2][0] == "extends":
                    extends_source = item[2][1].strip('"')
                    ext_item = None
                    for candidate in lib_sexp:
                        if isinstance(candidate, list) and len(candidate) > 1 and candidate[0] == "symbol":
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
            if node and node[0] == "pin" and len(node) > 2:
                for sub in node:
                    if isinstance(sub, list) and sub and sub[0] == "number" and len(sub) > 1:
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
    """Insert a symbol into a KiCad schematic file via S-expression manipulation."""
    with open(sch_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not sheet_uuid:
        m = re.search(r'\(uuid\s+"?([0-9a-fA-F\-]{36})"?\)', content[:4096])
        sheet_uuid = m.group(1) if m else str(uuid.uuid4())

    if not project_name:
        base = os.path.splitext(os.path.basename(sch_path))[0]
        project_name = base

    sym_uuid = str(uuid.uuid4())
    full_lib_id = f"{lib_name}:{symbol_name}" if lib_name else symbol_name

    lib_symbols_pattern = r"\(lib_symbols\b"
    has_lib_symbols = bool(re.search(lib_symbols_pattern, content))
    has_sym_in_lib = f'(symbol "{full_lib_id}"' in content or f"(symbol {full_lib_id}" in content

    sym_pins = ["1", "2"]

    if not has_sym_in_lib and lib_name:
        symbols_dir = get_kicad_symbols_dir()
        lib_file = os.path.join(symbols_dir, f"{lib_name}.kicad_sym")
        if os.path.exists(lib_file):
            try:
                sym_def_str = extract_symbol_definition(lib_file, symbol_name)
                formatted_def = re.sub(r'^\(symbol\s+"([^"]+)"', f'(symbol "{full_lib_id}"', sym_def_str.strip())
                if has_lib_symbols:
                    idx = content.find("(lib_symbols")
                    if idx != -1:
                        insert_pos = idx + len("(lib_symbols")
                        content = content[:insert_pos] + "\n    " + formatted_def + content[insert_pos:]
                else:
                    m_paper = re.search(r'\(paper\s+"[^"]+"\)', content)
                    if m_paper:
                        insert_pos = m_paper.end()
                        content = (
                            content[:insert_pos]
                            + f"\n  (lib_symbols\n    {formatted_def}\n  )"
                            + content[insert_pos:]
                        )
            except Exception:
                pass

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
    """Insert a wire connection into a KiCad schematic file via S-expression."""
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


def extract_symbol_definition(sym_lib_path: str, symbol_name: str) -> str:
    """Extract a symbol definition block from a .kicad_sym file."""
    with open(sym_lib_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf'\(symbol\s+"{re.escape(symbol_name)}"\s+'
    match = re.search(pattern, content)
    if not match:
        raise ValueError(f"Symbol '{symbol_name}' not found in {sym_lib_path}")

    start = match.start()
    depth = 0
    for i, ch in enumerate(content[start:], start):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return content[start : i + 1]
    return content[start:]


def inject_lib_symbols_into_schematic(sch_path: str, symbols: Dict[str, str]) -> None:
    """Inject symbol definitions into the (lib_symbols ...) section of a .kicad_sch file."""
    with open(sch_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"\(lib_symbols(\s*|\s+[\s\S]*?)\n\t\)", content)
    if not match:
        match = re.search(r"\(lib_symbols\)", content)

    if not match:
        raise ValueError(f"Could not find (lib_symbols) in {sch_path}")

    lib_symbols_text = "(lib_symbols\n"
    for full_lib_id, sym_s_expr in symbols.items():
        formatted_sym = re.sub(r'^\(symbol\s+"([^"]+)"', f'(symbol "{full_lib_id}"', sym_s_expr.strip())
        indented = "\n".join("\t\t" + line for line in formatted_sym.split("\n"))
        lib_symbols_text += indented + "\n"
    lib_symbols_text += "\t)"

    new_content = content[:match.start()] + lib_symbols_text + content[match.end():]
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(new_content)


class KiCad10SchematicWriter:
    """Standalone .kicad_sch generator creating valid KiCad 10 schematic files."""

    def __init__(self, sch_path: str, project_name: str = "Agent"):
        self.sch_path = sch_path
        self.project_name = project_name
        self.root_sheet_uuid = str(uuid.uuid4())
        self.lib_symbols: Dict[str, str] = {}
        self.symbols: List[str] = []
        self.wires: List[str] = []

    def add_lib_symbol(self, lib_id: str, s_expr_definition: str):
        clean_def = re.sub(r'^\(symbol\s+"([^"]+)"', f'(symbol "{lib_id}"', s_expr_definition.strip())
        clean_def = re.sub(r"\(embedded_fonts\s+no\)", "", clean_def).strip()
        self.lib_symbols[lib_id] = clean_def

    def add_symbol(
        self,
        lib_id: str,
        reference: str,
        value: str,
        position_mm: Tuple[float, float],
        angle: int = 0,
        footprint: str = "",
        unit: int = 1,
    ) -> str:
        sym_uuid = str(uuid.uuid4())
        x, y = position_mm
        ref_x, ref_y = (x + 2.032, y) if angle == 90 else (x, y - 2.54)
        val_x, val_y = (x - 2.032, y) if angle == 90 else (x, y + 2.54)

        sym_sexpr = f"""\t(symbol
\t\t(lib_id "{lib_id}")
\t\t(at {x} {y} {angle})
\t\t(unit {unit})
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(uuid "{sym_uuid}")
\t\t(property "Reference" "{reference}"
\t\t\t(at {ref_x} {ref_y} {angle})
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at {val_x} {val_y} {angle})
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Footprint" "{footprint}"
\t\t\t(at {x} {y} 0)
\t\t\t(hide yes)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(pin "1" (uuid "{uuid.uuid4()}"))
\t\t(pin "2" (uuid "{uuid.uuid4()}"))
\t\t(instances
\t\t\t(project "{self.project_name}"
\t\t\t\t(path "/{self.root_sheet_uuid}"
\t\t\t\t\t(reference "{reference}")
\t\t\t\t\t(unit {unit})
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""
        self.symbols.append(sym_sexpr)
        return sym_uuid

    def add_wire(self, start_mm: Tuple[float, float], end_mm: Tuple[float, float]) -> str:
        wire_uuid = str(uuid.uuid4())
        x1, y1 = start_mm
        x2, y2 = end_mm
        wire_sexpr = f"""\t(wire
\t\t(pts (xy {x1} {y1}) (xy {x2} {y2}))
\t\t(stroke (width 0) (type default))
\t\t(uuid "{wire_uuid}")
\t)"""
        self.wires.append(wire_sexpr)
        return wire_uuid

    def save(self):
        lib_syms_formatted = "\t(lib_symbols)\n"
        if self.lib_symbols:
            lib_syms_formatted = "\t(lib_symbols\n"
            for def_str in self.lib_symbols.values():
                indented = "\n".join("\t\t" + line for line in def_str.split("\n"))
                lib_syms_formatted += indented + "\n"
            lib_syms_formatted += "\t)\n"

        symbols_formatted = "\n\n".join(self.symbols)
        wires_formatted = "\n\n".join(self.wires)

        file_content = f"""(kicad_sch
\t(version 20260306)
\t(generator "eeschema")
\t(generator_version "10.0")
\t(uuid "{self.root_sheet_uuid}")
\t(paper "A4")
{lib_syms_formatted}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)

{symbols_formatted}

{wires_formatted}
)
"""
        with open(self.sch_path, "w", encoding="utf-8") as f:
            f.write(file_content)


# ===========================================================================
# SexprBackend (KiCadBackend Implementation)
# ===========================================================================

class SexprBackend(KiCadBackend):
    """File-based S-expression manipulation fallback backend."""

    def __init__(self, pcb_filepath: Optional[str] = None, sch_filepath: Optional[str] = None):
        self.pcb_filepath = pcb_filepath
        self.sch_filepath = sch_filepath

    @property
    def name(self) -> str:
        return "sexpr"

    def is_available(self) -> bool:
        return True

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def load_board(self, filepath: str) -> Dict[str, Any]:
        self.pcb_filepath = filepath
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"PCB file not found: {filepath}")
        return self.get_state("pcb")

    def save_board(self, filepath: Optional[str] = None) -> bool:
        return True

    def load_schematic(self, filepath: str) -> Dict[str, Any]:
        self.sch_filepath = filepath
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Schematic file not found: {filepath}")
        return self.get_state("schematic")

    def save_schematic(self, filepath: Optional[str] = None) -> bool:
        return True

    def get_state(self, domain: str = "pcb") -> Dict[str, Any]:
        if domain == "pcb" and self.pcb_filepath and os.path.exists(self.pcb_filepath):
            with open(self.pcb_filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            fp_refs = re.findall(r'\(property\s+"Reference"\s+"([^"]+)"', content)
            return {"components": fp_refs, "file": self.pcb_filepath}
        elif domain == "schematic" and self.sch_filepath and os.path.exists(self.sch_filepath):
            with open(self.sch_filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            sym_refs = re.findall(r'\(property\s+"Reference"\s+"([^"]+)"', content)
            return {"symbols": sym_refs, "file": self.sch_filepath}
        return {}

    def execute(self, action: Action) -> ActionResult:
        t0 = time.time()
        p = action.parameters

        try:
            if action.action_type == ActionType.ADD_FOOTPRINT:
                if not self.pcb_filepath:
                    raise AgentError(category=ErrorCategory.FILE_ERROR, message="No PCB file set for S-expr execution")
                fp_uuid = add_footprint_to_pcb(
                    pcb_path=self.pcb_filepath,
                    footprint_id=p["footprint_id"],
                    reference=p["reference"],
                    value=p.get("value", ""),
                    pos_x_mm=p["x"],
                    pos_y_mm=p["y"],
                    layer=p.get("layer", "F.Cu"),
                    rotation=p.get("rotation", 0),
                )
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"uuid": fp_uuid, "reference": p["reference"]},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.ADD_TRACK:
                if not self.pcb_filepath:
                    raise AgentError(category=ErrorCategory.FILE_ERROR, message="No PCB file set for S-expr execution")
                track_uuid = add_track_to_pcb(
                    pcb_path=self.pcb_filepath,
                    start=p["start"],
                    end=p["end"],
                    width_mm=p.get("width_mm", 0.25),
                    layer=p.get("layer", "F.Cu"),
                    net=p.get("net", 0),
                )
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"uuid": track_uuid},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.ADD_VIA:
                if not self.pcb_filepath:
                    raise AgentError(category=ErrorCategory.FILE_ERROR, message="No PCB file set for S-expr execution")
                via_uuid = add_via_to_pcb(
                    pcb_path=self.pcb_filepath,
                    at=p["at"],
                    size_mm=p.get("size_mm", 0.8),
                    drill_mm=p.get("drill_mm", 0.4),
                    layers=p.get("layers", ("F.Cu", "B.Cu")),
                    net=p.get("net", 0),
                )
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"uuid": via_uuid},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.ADD_ZONE:
                if not self.pcb_filepath:
                    raise AgentError(category=ErrorCategory.FILE_ERROR, message="No PCB file set for S-expr execution")
                zone_uuid = add_zone_to_pcb(
                    pcb_path=self.pcb_filepath,
                    polygon=p["polygon"],
                    layer=p.get("layer", "F.Cu"),
                    net=p.get("net", 0),
                    net_name=p.get("net_name", ""),
                )
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"uuid": zone_uuid},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.ADD_SYMBOL:
                if not self.sch_filepath:
                    raise AgentError(category=ErrorCategory.FILE_ERROR, message="No Schematic file set for S-expr execution")
                lib_id = p.get("lib_id", "")
                lib_name, sym_name = lib_id.split(":", 1) if ":" in lib_id else ("", lib_id)
                sym_uuid = add_symbol_to_schematic(
                    sch_path=self.sch_filepath,
                    lib_name=lib_name,
                    symbol_name=sym_name,
                    reference=p["reference"],
                    value=p.get("value", ""),
                    pos_x_mm=p["x"],
                    pos_y_mm=p["y"],
                    rotation=p.get("rotation", 0),
                )
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"uuid": sym_uuid, "reference": p["reference"]},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.ADD_WIRE:
                if not self.sch_filepath:
                    raise AgentError(category=ErrorCategory.FILE_ERROR, message="No Schematic file set for S-expr execution")
                wire_uuid = add_wire_to_schematic(
                    sch_path=self.sch_filepath,
                    start=p["start"],
                    end=p["end"],
                )
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"uuid": wire_uuid},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            else:
                raise AgentError(
                    category=ErrorCategory.INVALID_ACTION,
                    message=f"SexprBackend does not support action {action.action_type}",
                )

        except Exception as e:
            err = e if isinstance(e, AgentError) else AgentError(
                category=ErrorCategory.API_ERROR,
                message=str(e),
                operation=action.action_type.value,
            )
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=err,
                execution_time_ms=(time.time() - t0) * 1000,
                backend_used=self.name,
            )
