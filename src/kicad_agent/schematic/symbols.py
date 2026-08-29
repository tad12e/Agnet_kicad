"""Symbol models, library parsers, and registry for KiCad Schematics."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

from ..utils.paths import get_kicad_symbols_dir


class Pin:
    """Represents a pin on a placed schematic component."""

    def __init__(
        self,
        number: str,
        name: str = "",
        position_mm: Optional[Tuple[float, float]] = None,
        pin_type: str = "passive",
        parent_ref: str = "",
    ):
        self.number = str(number)
        self.name = str(name)
        self.position_mm = position_mm
        self.pin_type = str(pin_type)
        self.parent_ref = parent_ref

    def __repr__(self) -> str:
        return (
            f"Pin(num={self.number!r}, name={self.name!r}, "
            f"type={self.pin_type!r}, parent={self.parent_ref!r})"
        )


class Component:
    """Represents a placed schematic symbol instance."""

    def __init__(
        self,
        id: str,
        lib_id: str,
        reference: str,
        value: str,
        position_mm: Tuple[float, float],
        unit: int = 1,
        raw_proto: Optional[object] = None,
    ):
        self.id = id
        self.lib_id = lib_id
        self.reference = reference
        self.value = value
        self.position_mm = position_mm
        self.unit = unit
        self._raw_proto = raw_proto

    def __repr__(self) -> str:
        return (
            f"Component(ref={self.reference!r}, val={self.value!r}, "
            f"lib={self.lib_id!r}, pos={self.position_mm}, id={self.id!r})"
        )


class PinInfo:
    """Metadata for a pin on a library symbol definition (.kicad_sym)."""

    def __init__(
        self,
        number: str,
        name: str,
        pin_type: str = "passive",
        at_x: float = 0.0,
        at_y: float = 0.0,
        orientation: int = 0,
    ) -> None:
        self.number = str(number)
        self.name = str(name)
        self.pin_type = str(pin_type)
        self.at_x = float(at_x)
        self.at_y = float(at_y)
        self.orientation = int(orientation)

    def __repr__(self) -> str:
        return f"PinInfo(num={self.number!r}, name={self.name!r}, type={self.pin_type!r})"


class SymbolInfo:
    """Metadata for a KiCad symbol definition from a library file."""

    def __init__(
        self,
        lib_id: str,
        name: str,
        library: str,
        description: str = "",
        keywords: Optional[List[str]] = None,
        pins: Optional[List[PinInfo]] = None,
        properties: Optional[Dict[str, str]] = None,
        raw_sexpr: str = "",
    ) -> None:
        self.lib_id = lib_id
        self.name = name
        self.library = library
        self.description = description
        self.keywords = keywords or []
        self.pins = pins or []
        self.properties = properties or {}
        self.raw_sexpr = raw_sexpr

    def get_pin(self, number_or_name: str) -> Optional[PinInfo]:
        query = str(number_or_name)
        for p in self.pins:
            if p.number == query or p.name == query:
                return p
        return None

    @property
    def pin_count(self) -> int:
        return len(self.pins)

    def __repr__(self) -> str:
        return f"SymbolInfo(lib_id={self.lib_id!r}, pins={self.pin_count})"


class SymbolLibraryParser:
    """Parser for KiCad .kicad_sym symbol library files."""

    @staticmethod
    def parse_file(filepath: str) -> List[SymbolInfo]:
        if not os.path.exists(filepath):
            return []

        library_name = os.path.splitext(os.path.basename(filepath))[0]
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return SymbolLibraryParser.parse_string(content, library_name=library_name)

    @staticmethod
    def parse_string(content: str, library_name: str = "Device") -> List[SymbolInfo]:
        symbols: List[SymbolInfo] = []

        pattern = re.compile(
            r'\(symbol\s+"([^"]+)"\s*(.*?)(?=\n\t\(symbol|\n\)$|\Z)',
            re.DOTALL,
        )
        matches = pattern.findall(content)

        for name, body in matches:
            if "_" in name and name.split("_")[-1].isdigit():
                continue

            lib_id = f"{library_name}:{name}"
            raw_sexpr = f'\t\t(symbol "{lib_id}"\n{body.strip()}\n\t\t)'

            properties = {}
            prop_pattern = re.compile(r'\(property\s+"([^"]+)"\s+"([^"]*)"')
            for prop_name, prop_val in prop_pattern.findall(body):
                properties[prop_name] = prop_val

            description = properties.get("Description", "")
            keywords_raw = properties.get("ki_keywords", "")
            keywords = [k.strip() for k in keywords_raw.split() if k.strip()]

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


class SymbolResolver:
    """Central registry and search index for KiCad symbol definitions."""

    _global_instance: Optional[SymbolResolver] = None

    def __init__(self) -> None:
        self._symbols: Dict[str, SymbolInfo] = {}
        self._load_builtins()

    @classmethod
    def get_default(cls) -> SymbolResolver:
        if cls._global_instance is None:
            cls._global_instance = SymbolResolver()
            cls._global_instance.auto_discover_kicad_symbols()
        return cls._global_instance

    def register(self, symbol: SymbolInfo) -> None:
        self._symbols[symbol.lib_id] = symbol

    def get(self, lib_id: str) -> Optional[SymbolInfo]:
        return self._symbols.get(lib_id)

    def search(self, query: str = "", family: Optional[str] = None) -> List[SymbolInfo]:
        results: List[SymbolInfo] = []
        q = query.lower().strip()
        fam = family.lower().strip() if family else None

        for sym in self._symbols.values():
            if q:
                search_space = (
                    f"{sym.lib_id} {sym.name} {sym.description} "
                    f"{' '.join(sym.keywords)}"
                ).lower()
                if q not in search_space:
                    continue

            if fam:
                fam_space = (
                    f"{sym.lib_id} {sym.name} {sym.description} "
                    f"{' '.join(sym.keywords)}"
                ).lower()
                if fam not in fam_space:
                    continue

            results.append(sym)

        return results

    @property
    def count(self) -> int:
        return len(self._symbols)

    def load_library_file(self, filepath: str) -> int:
        symbols = SymbolLibraryParser.parse_file(filepath)
        for s in symbols:
            self.register(s)
        return len(symbols)

    def load_library_directory(self, dirpath: str) -> int:
        if not os.path.exists(dirpath):
            return 0

        count = 0
        for root, _, files in os.walk(dirpath):
            for f in files:
                if f.endswith(".kicad_sym"):
                    count += self.load_library_file(os.path.join(root, f))
        return count

    def auto_discover_kicad_symbols(self) -> None:
        symbols_dir = get_kicad_symbols_dir()
        if os.path.exists(symbols_dir):
            self.load_library_directory(symbols_dir)

    def _load_builtins(self) -> None:
        builtins = [
            ("Device:R", "R", "Device", "Resistor", ["resistor"],
             [PinInfo("1", "", "passive", 0, 3.81, 270),
              PinInfo("2", "", "passive", 0, -3.81, 90)]),
            ("Device:C", "C", "Device", "Unpolarized capacitor", ["capacitor"],
             [PinInfo("1", "", "passive", 0, 3.81, 270),
              PinInfo("2", "", "passive", 0, -3.81, 90)]),
            ("Device:LED", "LED", "Device", "Light emitting diode", ["led", "diode"],
             [PinInfo("1", "K", "passive", -3.81, 0, 0),
              PinInfo("2", "A", "passive", 3.81, 0, 180)]),
            ("power:+5V", "+5V", "power", "Power symbol +5V", ["power"],
             [PinInfo("1", "+5V", "power_in", 0, 0, 90)]),
            ("power:GND", "GND", "power", "Power symbol GND", ["power", "ground"],
             [PinInfo("1", "GND", "power_in", 0, 0, 270)]),
        ]

        for lib_id, name, library, desc, keywords, pins in builtins:
            self.register(SymbolInfo(
                lib_id=lib_id,
                name=name,
                library=library,
                description=desc,
                keywords=keywords,
                pins=pins,
            ))
