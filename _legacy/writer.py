import uuid
import os
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from .schematic import Schematic
    from ..symbols.registry import SymbolRegistry

# Built-in fallback library symbol templates
LIB_SYMBOL_TEMPLATES: Dict[str, str] = {
    "Device:R": """\t\t(symbol "Device:R"
\t\t\t(pin_numbers (hide yes))
\t\t\t(pin_names (offset 0))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "R" (at 2.032 0 90) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(property "Value" "R" (at 0 0 90) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(property "Footprint" "" (at -1.778 0 90) (show_name no) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(property "Datasheet" "" (at 0 0 0) (show_name no) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(property "Description" "Resistor" (at 0 0 0) (show_name no) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "R_0_1"
\t\t\t\t(rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none)))
\t\t\t)
\t\t\t(symbol "R_1_1"
\t\t\t\t(pin passive line (at 0 3.81 270) (length 1.27) (name "" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 0 -3.81 90) (length 1.27) (name "" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)""",

    "Device:C": """\t\t(symbol "Device:C"
\t\t\t(pin_numbers (hide yes))
\t\t\t(pin_names (offset 0.254))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "C" (at 0.635 2.54 0) (show_name no) (effects (font (size 1.27 1.27)) (justify left)))
\t\t\t(property "Value" "C" (at 0.635 -2.54 0) (show_name no) (effects (font (size 1.27 1.27)) (justify left)))
\t\t\t(property "Footprint" "" (at 0.9652 -3.81 0) (show_name no) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(property "Datasheet" "" (at 0 0 0) (show_name no) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(property "Description" "Unpolarized capacitor" (at 0 0 0) (show_name no) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "C_0_1"
\t\t\t\t(polyline (pts (xy -2.032 0.762) (xy 2.032 0.762)) (stroke (width 0.508) (type default)) (fill (type none)))
\t\t\t\t(polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762)) (stroke (width 0.508) (type default)) (fill (type none)))
\t\t\t)
\t\t\t(symbol "C_1_1"
\t\t\t\t(pin passive line (at 0 3.81 270) (length 2.794) (name "" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 0 -3.81 90) (length 2.794) (name "" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)""",

    "Device:LED": """\t\t(symbol "Device:LED"
\t\t\t(pin_numbers (hide yes))
\t\t\t(pin_names (offset 1.016) (hide yes))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "D" (at 0 2.54 0) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(property "Value" "LED" (at 0 -2.54 0) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(property "Footprint" "" (at 0 0 0) (show_name no) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(property "Datasheet" "" (at 0 0 0) (show_name no) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(property "Description" "Light emitting diode" (at 0 0 0) (show_name no) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "LED_0_1"
\t\t\t\t(polyline (pts (xy -1.27 0) (xy 1.27 0)) (stroke (width 0) (type default)) (fill (type none)))
\t\t\t\t(polyline (pts (xy -1.27 -1.27) (xy -1.27 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
\t\t\t\t(polyline (pts (xy 1.27 -1.27) (xy 1.27 1.27) (xy -1.27 0) (xy 1.27 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
\t\t\t)
\t\t\t(symbol "LED_1_1"
\t\t\t\t(pin passive line (at -3.81 0 0) (length 2.54) (name "K" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 3.81 0 180) (length 2.54) (name "A" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)""",

    "Switch:SW_Push": """\t\t(symbol "Switch:SW_Push"
\t\t\t(pin_numbers (hide yes))
\t\t\t(pin_names (offset 1.016) (hide yes))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "SW" (at 1.27 2.54 0) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(property "Value" "SW_Push" (at 1.27 -2.54 0) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "SW_Push_0_1"
\t\t\t\t(polyline (pts (xy -2.54 1.27) (xy -2.54 2.54) (xy 2.54 2.54) (xy 2.54 1.27)) (stroke (width 0) (type default)) (fill (type none)))
\t\t\t)
\t\t\t(symbol "SW_Push_1_1"
\t\t\t\t(pin passive line (at -5.08 0 0) (length 2.54) (name "1" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 5.08 0 180) (length 2.54) (name "2" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)""",

    "power:+5V": """\t\t(symbol "power:+5V"
\t\t\t(power)
\t\t\t(pin_names (offset 0))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "#PWR" (at 0 -3.81 0) (hide yes) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(property "Value" "+5V" (at 0 3.81 0) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "+5V_0_1"
\t\t\t\t(polyline (pts (xy 0 0) (xy 0 1.27) (xy -0.762 1.27) (xy 0 2.54) (xy 0.762 1.27) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none)))
\t\t\t)
\t\t\t(symbol "+5V_1_1"
\t\t\t\t(pin power_in line (at 0 0 90) (length 0) (hide yes) (name "+5V" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)""",

    "power:GND": """\t\t(symbol "power:GND"
\t\t\t(power)
\t\t\t(pin_names (offset 0))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "#PWR" (at 0 -6.35 0) (hide yes) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(property "Value" "GND" (at 0 -3.81 0) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "GND_0_1"
\t\t\t\t(polyline (pts (xy 0 0) (xy 0 -1.27) (xy -1.27 -1.27) (xy 0 -2.54) (xy 1.27 -1.27) (xy 0 -1.27)) (stroke (width 0) (type default)) (fill (type none)))
\t\t\t)
\t\t\t(symbol "GND_1_1"
\t\t\t\t(pin power_in line (at 0 0 270) (length 0) (hide yes) (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)"""
}

class KiCadWriter:
    """
    Serializes a Schematic container into a valid KiCad 10 .kicad_sch file format.
    Dynamically fetches symbol definitions from SymbolRegistry.
    """

    def __init__(self, schematic: "Schematic", registry: Optional["SymbolRegistry"] = None) -> None:
        self.schematic = schematic
        self.file_uuid = str(uuid.uuid4())
        
        if registry is None:
            from ..symbols.registry import SymbolRegistry
            self.registry = SymbolRegistry.get_default()
        else:
            self.registry = registry

    def to_sexpr(self) -> str:
        lines = []

        # 1. Root Header
        lines.append("(kicad_sch")
        lines.append("\t(version 20260306)")
        lines.append('\t(generator "eeschema")')
        lines.append('\t(generator_version "10.0")')
        lines.append(f'\t(uuid "{self.file_uuid}")')
        lines.append('\t(paper "A4")')

        # 2. Library Symbols Section (lib_symbols)
        lines.append("\t(lib_symbols")
        used_lib_ids = set()
        for comp in self.schematic.components:
            used_lib_ids.add(comp.lib_id)
        for pwr in self.schematic.power_symbols:
            used_lib_ids.add(pwr.lib_id)

        for lib_id in sorted(used_lib_ids):
            sym_info = self.registry.get(lib_id)
            if sym_info and sym_info.raw_sexpr:
                lines.append(sym_info.raw_sexpr)
            elif lib_id in LIB_SYMBOL_TEMPLATES:
                lines.append(LIB_SYMBOL_TEMPLATES[lib_id])
        lines.append("\t)")

        # 3. Junctions Section
        for j in self.schematic.junctions:
            lines.append("\t(junction")
            lines.append(f"\t\t(at {j.x:.2f} {j.y:.2f})")
            lines.append("\t\t(diameter 0)")
            lines.append("\t\t(color 0 0 0 0)")
            lines.append(f'\t\t(uuid "{j.uuid}")')
            lines.append("\t)")

        # 4. Wires Section
        for w in self.schematic.wires:
            lines.append("\t(wire")
            lines.append("\t\t(pts")
            lines.append(f"\t\t\t(xy {w.x1:.2f} {w.y1:.2f}) (xy {w.x2:.2f} {w.y2:.2f})")
            lines.append("\t\t)")
            lines.append("\t\t(stroke")
            lines.append("\t\t\t(width 0)")
            lines.append("\t\t\t(type default)")
            lines.append("\t\t)")
            lines.append(f'\t\t(uuid "{w.uuid}")')
            lines.append("\t)")

        # 5. Placed Component Symbol Instances
        for c in self.schematic.components:
            lines.append("\t(symbol")
            lines.append(f'\t\t(lib_id "{c.lib_id}")')
            lines.append(f"\t\t(at {c.x:.2f} {c.y:.2f} 0)")
            lines.append("\t\t(unit 1)")
            lines.append("\t\t(body_style 1)")
            lines.append("\t\t(exclude_from_sim no)")
            lines.append("\t\t(in_bom yes)")
            lines.append("\t\t(on_board yes)")
            lines.append("\t\t(in_pos_files yes)")
            lines.append("\t\t(dnp no)")
            lines.append("\t\t(fields_autoplaced yes)")
            lines.append(f'\t\t(uuid "{c.uuid}")')
            lines.append(f'\t\t(property "Reference" "{c.reference}"')
            lines.append(f"\t\t\t(at {c.x + 2.032:.2f} {c.y:.2f} 0)")
            lines.append("\t\t\t(show_name no)")
            lines.append("\t\t\t(do_not_autoplace no)")
            lines.append("\t\t\t(effects (font (size 1.27 1.27)) (justify left))")
            lines.append("\t\t)")
            lines.append(f'\t\t(property "Value" "{c.value}"')
            lines.append(f"\t\t\t(at {c.x + 2.032:.2f} {c.y + 2.54:.2f} 0)")
            lines.append("\t\t\t(show_name no)")
            lines.append("\t\t\t(do_not_autoplace no)")
            lines.append("\t\t\t(effects (font (size 1.27 1.27)) (justify left))")
            lines.append("\t\t)")
            lines.append(f'\t\t(property "Footprint" "{c.footprint}"')
            lines.append(f"\t\t\t(at {c.x:.2f} {c.y:.2f} 0)")
            lines.append("\t\t\t(hide yes)")
            lines.append("\t\t\t(show_name no)")
            lines.append("\t\t\t(do_not_autoplace no)")
            lines.append("\t\t\t(effects (font (size 1.27 1.27)))")
            lines.append("\t\t)")
            for pin_num, pin_uuid in c.pin_uuids.items():
                lines.append(f'\t\t(pin "{pin_num}" (uuid "{pin_uuid}"))')
            lines.append("\t\t(instances")
            lines.append('\t\t\t(project "schematic"')
            lines.append(f'\t\t\t\t(path "/{self.file_uuid}"')
            lines.append(f'\t\t\t\t\t(reference "{c.reference}")')
            lines.append("\t\t\t\t\t(unit 1)")
            lines.append("\t\t\t\t)")
            lines.append("\t\t\t)")
            lines.append("\t\t)")
            lines.append("\t)")

        # 6. Placed Power Symbol Instances
        for p in self.schematic.power_symbols:
            lines.append("\t(symbol")
            lines.append(f'\t\t(lib_id "{p.lib_id}")')
            lines.append(f"\t\t(at {p.x:.2f} {p.y:.2f} 0)")
            lines.append("\t\t(unit 1)")
            lines.append("\t\t(body_style 1)")
            lines.append("\t\t(exclude_from_sim no)")
            lines.append("\t\t(in_bom yes)")
            lines.append("\t\t(on_board yes)")
            lines.append("\t\t(in_pos_files yes)")
            lines.append("\t\t(dnp no)")
            lines.append("\t\t(fields_autoplaced yes)")
            lines.append(f'\t\t(uuid "{p.uuid}")')
            lines.append(f'\t\t(property "Reference" "{p.reference}"')
            lines.append(f"\t\t\t(at {p.x:.2f} {p.y + 3.81:.2f} 0)")
            lines.append("\t\t\t(hide yes)")
            lines.append("\t\t\t(show_name no)")
            lines.append("\t\t\t(do_not_autoplace no)")
            lines.append("\t\t\t(effects (font (size 1.27 1.27)))")
            lines.append("\t\t)")
            lines.append(f'\t\t(property "Value" "{p.name}"')
            lines.append(f"\t\t\t(at {p.x:.2f} {p.y - 3.81:.2f} 0)")
            lines.append("\t\t\t(show_name no)")
            lines.append("\t\t\t(do_not_autoplace no)")
            lines.append("\t\t\t(effects (font (size 1.27 1.27)))")
            lines.append("\t\t)")
            lines.append(f'\t\t(pin "1" (uuid "{p.pin_uuid}"))')
            lines.append("\t\t(instances")
            lines.append('\t\t\t(project "schematic"')
            lines.append(f'\t\t\t\t(path "/{self.file_uuid}"')
            lines.append(f'\t\t\t\t\t(reference "{p.reference}")')
            lines.append("\t\t\t\t\t(unit 1)")
            lines.append("\t\t\t\t)")
            lines.append("\t\t\t)")
            lines.append("\t\t)")
            lines.append("\t)")

        # 7. Sheet instances & closing
        lines.append("\t(sheet_instances")
        lines.append('\t\t(path "/"')
        lines.append('\t\t\t(page "1")')
        lines.append("\t\t)")
        lines.append("\t)")
        lines.append("\t(embedded_fonts no)")
        lines.append(")")

        return "\n".join(lines) + "\n"

    def save(self, filepath: str) -> None:
        content = self.to_sexpr()
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
