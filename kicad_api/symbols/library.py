"""KiCad Symbol Library File Parser.

Parses .kicad_sym files (KiCad's symbol library format) to extract
symbol definitions including pins, properties, and raw S-expressions.

The .kicad_sym format is an S-expression (Lisp-like) text format.
Each file represents one library (e.g., "Device.kicad_sym" = the "Device" library)
and contains multiple symbol definitions.

Example structure of a .kicad_sym file:
    (kicad_symbol_lib
        (version 20211014)
        (generator kicad_symbol_editor)
        (symbol "R"
            (property "Reference" "R" ...)
            (property "Value" "R" ...)
            (symbol "R_0_1"              ← graphical sub-symbol (drawing)
                (rectangle ...)
            )
            (symbol "R_1_1"              ← pin sub-symbol (unit 1)
                (pin passive line (at 0 3.81 270) ... (number "1"))
                (pin passive line (at 0 -3.81 90) ... (number "2"))
            )
        )
    )

Migrated from kicad_agent/symbols/parser.py with preserved functionality.
"""

from __future__ import annotations

import os
import re
from typing import List

from .pins import PinInfo
from .symbol import SymbolInfo


class SymbolLibraryParser:
    """Parser for KiCad .kicad_sym symbol library files.

    Extracts SymbolInfo objects containing lib_id, pins, properties,
    and raw S-expression definitions.

    Usage:
        symbols = SymbolLibraryParser.parse_file("/path/to/Device.kicad_sym")
        for sym in symbols:
            print(sym.lib_id, sym.pin_count)
    """

    @staticmethod
    def parse_file(filepath: str) -> List[SymbolInfo]:
        """Parse a .kicad_sym file and return all symbol definitions.

        Args:
            filepath: Path to a .kicad_sym file.

        Returns:
            List of SymbolInfo objects, one per top-level symbol.
        """
        if not os.path.exists(filepath):
            return []

        library_name = os.path.splitext(os.path.basename(filepath))[0]
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return SymbolLibraryParser.parse_string(content, library_name=library_name)

    @staticmethod
    def parse_string(content: str, library_name: str = "Device") -> List[SymbolInfo]:
        """Parse .kicad_sym content from a string.

        Args:
            content: Raw text content of a .kicad_sym file.
            library_name: Library name to use as prefix (e.g., "Device").

        Returns:
            List of SymbolInfo objects.
        """
        symbols: List[SymbolInfo] = []

        # Find top-level (symbol "SymbolName" ...) blocks inside kicad_symbol_lib
        pattern = re.compile(
            r'\(symbol\s+"([^"]+)"\s*(.*?)(?=\n\t\(symbol|\n\)$|\Z)',
            re.DOTALL,
        )
        matches = pattern.findall(content)

        for name, body in matches:
            # Skip sub-symbols like R_0_1 or R_1_1 (graphical/pin sub-units)
            if "_" in name and name.split("_")[-1].isdigit():
                continue

            lib_id = f"{library_name}:{name}"
            raw_sexpr = f'\t\t(symbol "{lib_id}"\n{body.strip()}\n\t\t)'

            # Extract properties: (property "Name" "Value" ...)
            properties = {}
            prop_pattern = re.compile(r'\(property\s+"([^"]+)"\s+"([^"]*)"')
            for prop_name, prop_val in prop_pattern.findall(body):
                properties[prop_name] = prop_val

            description = properties.get("Description", "")
            keywords_raw = properties.get("ki_keywords", "")
            keywords = [k.strip() for k in keywords_raw.split() if k.strip()]

            # Extract pins:
            # (pin <type> <shape> (at <x> <y> <angle>) ... (name "<name>") (number "<num>"))
            pins: List[PinInfo] = []
            pin_pattern = re.compile(
                r'\(pin\s+([^\s\()]+)\s+[^\s\()]+\s+\(at\s+([-\d.]+)\s+([-\d.]+)\s*([-\d.]*)\).*?'
                r'\(name\s+"([^"]*)"[^\)]*\).*?\(number\s+"([^"]+)"',
                re.DOTALL,
            )
            for ptype, px, py, pangle, pname, pnum in pin_pattern.findall(body):
                angle = int(float(pangle)) if pangle else 0
                pins.append(PinInfo(
                    number=pnum,
                    name=pname,
                    pin_type=ptype,
                    at_x=float(px),
                    at_y=float(py),
                    orientation=angle,
                ))

            symbols.append(SymbolInfo(
                lib_id=lib_id,
                name=name,
                library=library_name,
                description=description,
                keywords=keywords,
                pins=pins,
                properties=properties,
                raw_sexpr=raw_sexpr,
            ))

        return symbols
