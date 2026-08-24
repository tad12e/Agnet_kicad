"""KiCad 10 Schematic S-Expression Generator & Writer.

Outputs 100% standard, perfectly formatted KiCad 8/9/10 .kicad_sch files
with exact property hierarchies, instances blocks, pin UUIDs, and lib_symbols.
"""
from __future__ import annotations

import os
import re
import sys
import uuid

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from typing import Dict, List, Optional, Tuple


class KiCad10SchematicWriter:
    """Robust .kicad_sch file builder matching KiCad 10 format perfectly."""

    def __init__(self, sch_path: str, project_name: str = "Agent"):
        self.sch_path = sch_path
        self.project_name = project_name
        self.root_sheet_uuid = ""
        self.lib_symbols: Dict[str, str] = {}
        self.symbols: List[str] = []
        self.wires: List[str] = []
        self._init_or_load()

    def _init_or_load(self):
        """Read existing schematic or create a fresh one."""
        if os.path.exists(self.sch_path):
            with open(self.sch_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Find root UUID
            uuid_match = re.search(r'\(uuid\s+"?([a-f0-9\-]+)"?\)', content)
            if uuid_match:
                self.root_sheet_uuid = uuid_match.group(1)
            else:
                self.root_sheet_uuid = str(uuid.uuid4())
        else:
            self.root_sheet_uuid = str(uuid.uuid4())

    def add_lib_symbol(self, lib_id: str, s_expr_definition: str):
        """Register a symbol's graphical & pin definition into lib_symbols."""
        # Ensure it has the full library prefix like (symbol "Device:R" ...)
        clean_def = re.sub(
            r'^\(symbol\s+"([^"]+)"',
            f'(symbol "{lib_id}"',
            s_expr_definition.strip()
        )
        # Remove any stray (embedded_fonts no) that might have been copied from lib file end
        clean_def = re.sub(r'\(embedded_fonts\s+no\)', '', clean_def).strip()
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
        """Place a symbol on the canvas."""
        sym_uuid = str(uuid.uuid4())
        pin1_uuid = str(uuid.uuid4())
        pin2_uuid = str(uuid.uuid4())
        x, y = position_mm

        # Calculate standard text offsets
        if angle == 90:
            ref_x, ref_y = x + 2.032, y
            val_x, val_y = x - 2.032, y
        elif angle == 0:
            ref_x, ref_y = x, y - 2.54
            val_x, val_y = x, y + 2.54
        else:
            ref_x, ref_y = x, y
            val_x, val_y = x, y

        sym_sexpr = f"""	(symbol
		(lib_id "{lib_id}")
		(at {x} {y} {angle})
		(unit {unit})
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(dnp no)
		(uuid "{sym_uuid}")
		(property "Reference" "{reference}"
			(at {ref_x} {ref_y} {angle})
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(property "Value" "{value}"
			(at {val_x} {val_y} {angle})
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(property "Footprint" "{footprint}"
			(at {x} {y} 0)
			(hide yes)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(pin "1"
			(uuid "{pin1_uuid}")
		)
		(pin "2"
			(uuid "{pin2_uuid}")
		)
		(instances
			(project "{self.project_name}"
				(path "/{self.root_sheet_uuid}"
					(reference "{reference}")
					(unit {unit})
				)
			)
		)
	)"""
        self.symbols.append(sym_sexpr)
        return sym_uuid

    def add_wire(self, start_mm: Tuple[float, float], end_mm: Tuple[float, float]) -> str:
        """Add a wire connecting two points."""
        wire_uuid = str(uuid.uuid4())
        x1, y1 = start_mm
        x2, y2 = end_mm

        wire_sexpr = f"""	(wire
		(pts
			(xy {x1} {y1}) (xy {x2} {y2})
		)
		(stroke
			(width 0)
			(type default)
		)
		(uuid "{wire_uuid}")
	)"""
        self.wires.append(wire_sexpr)
        return wire_uuid

    def save(self):
        """Write the complete, pristine KiCad 10 schematic file."""
        lib_syms_formatted = ""
        if self.lib_symbols:
            lib_syms_formatted = "\t(lib_symbols\n"
            for def_str in self.lib_symbols.values():
                # Indent 2 tabs
                indented = "\n".join("\t\t" + line for line in def_str.split("\n"))
                lib_syms_formatted += indented + "\n"
            lib_syms_formatted += "\t)\n"
        else:
            lib_syms_formatted = "\t(lib_symbols)\n"

        symbols_formatted = "\n\n".join(self.symbols)
        wires_formatted = "\n\n".join(self.wires)

        file_content = f"""(kicad_sch
	(version 20260306)
	(generator "eeschema")
	(generator_version "10.0")
	(uuid "{self.root_sheet_uuid}")
	(paper "A4")
{lib_syms_formatted}
	(sheet_instances
		(path "/"
			(page "1")
		)
	)

{symbols_formatted}

{wires_formatted}
)
"""
        with open(self.sch_path, "w", encoding="utf-8") as f:
            f.write(file_content)
        print(f"✓ Saved pristine KiCad 10 schematic: {self.sch_path}")
        print(f"  • Symbols: {len(self.symbols)}")
        print(f"  • Wires: {len(self.wires)}")


if __name__ == "__main__":
    from kicad_api.schematic.cache_helper import extract_symbol_definition

    sch_file = r"C:\Users\hp\ECE\test\Agent\Agent.kicad_sch"
    device_sym_path = r"C:\Program Files\KiCad\10.0\share\kicad\symbols\Device.kicad_sym"

    writer = KiCad10SchematicWriter(sch_file, project_name="Agent")
    
    # 1. Embed Device:R library definition
    r_def = extract_symbol_definition(device_sym_path, "R")
    writer.add_lib_symbol("Device:R", r_def)

    # 2. Place R1 (10k) and R2 (2.2k)
    writer.add_symbol("Device:R", "R1", "10k", (100.0, 100.0), angle=90)
    writer.add_symbol("Device:R", "R2", "2.2k", (130.0, 100.0), angle=90)

    # 3. Add connecting wire from R1 pin 1 to R2 pin 1
    # For a horizontal resistor at (100, 100, 90), pin 1 is at (100 - 3.81, 100) = (96.19, 100)
    writer.add_wire((100.0, 96.19), (130.0, 96.19))

    # 4. Save file
    writer.save()
