"""KiCad Symbol Resolver (Registry).

Central index for discovering, loading, and looking up KiCad symbol
definitions from .kicad_sym library files.

This is used by the high-level API and the AI planner to understand
what pins/properties a symbol has BEFORE placing it via IPC.

Migrated from kicad_agent/symbols/registry.py with preserved functionality.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from .pins import PinInfo
from .symbol import SymbolInfo
from .library import SymbolLibraryParser


class SymbolResolver:
    """Central registry for KiCad symbol definitions.

    Allows:
    - Exact lookup by lib_id (e.g., "Device:R")
    - Fuzzy search by keyword/description
    - Auto-discovery of installed KiCad symbol libraries
    - Loading custom .kicad_sym files

    Usage:
        resolver = SymbolResolver.get_default()
        r_info = resolver.get("Device:R")
        print(r_info.pins)  # [PinInfo(num='1', ...), PinInfo(num='2', ...)]
    """

    _global_instance: Optional[SymbolResolver] = None

    def __init__(self) -> None:
        self._symbols: Dict[str, SymbolInfo] = {}
        self._load_builtins()

    @classmethod
    def get_default(cls) -> SymbolResolver:
        """Get or create the global singleton resolver.

        On first call, auto-discovers KiCad's installed symbol libraries.
        """
        if cls._global_instance is None:
            cls._global_instance = SymbolResolver()
            cls._global_instance.auto_discover_kicad_symbols()
        return cls._global_instance

    def register(self, symbol: SymbolInfo) -> None:
        """Register a symbol definition in the index."""
        self._symbols[symbol.lib_id] = symbol

    def get(self, lib_id: str) -> Optional[SymbolInfo]:
        """Look up a symbol by exact lib_id (e.g., 'Device:R').

        Returns:
            SymbolInfo if found, None otherwise.
        """
        return self._symbols.get(lib_id)

    def search(self, query: str = "", family: Optional[str] = None) -> List[SymbolInfo]:
        """Search symbols by keyword, description, name, or family.

        Args:
            query: Search term to match against lib_id, name, description, keywords.
            family: Optional family filter (e.g., "resistor", "capacitor").

        Returns:
            List of matching SymbolInfo objects.
        """
        results: List[SymbolInfo] = []
        q = query.lower().strip()
        fam = family.lower().strip() if family else None

        for sym in self._symbols.values():
            # Match query
            if q:
                search_space = (
                    f"{sym.lib_id} {sym.name} {sym.description} "
                    f"{' '.join(sym.keywords)}"
                ).lower()
                if q not in search_space:
                    continue

            # Match family
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
        """Number of registered symbols."""
        return len(self._symbols)

    def load_library_file(self, filepath: str) -> int:
        """Load symbols from a single .kicad_sym file.

        Returns:
            Number of symbols loaded.
        """
        symbols = SymbolLibraryParser.parse_file(filepath)
        for s in symbols:
            self.register(s)
        return len(symbols)

    def load_library_directory(self, dirpath: str) -> int:
        """Recursively load all .kicad_sym files from a directory.

        Returns:
            Total number of symbols loaded.
        """
        if not os.path.exists(dirpath):
            return 0

        count = 0
        for root, _, files in os.walk(dirpath):
            for f in files:
                if f.endswith(".kicad_sym"):
                    full_path = os.path.join(root, f)
                    count += self.load_library_file(full_path)
        return count

    def auto_discover_kicad_symbols(self) -> None:
        """Auto-discover KiCad's installed symbol libraries.

        Checks environment variables and well-known installation paths
        across KiCad versions 10.0, 9.0, 8.0, 7.0.
        """
        # Check environment variables first
        for env_var in [
            "KICAD10_SYMBOL_DIR",
            "KICAD9_SYMBOL_DIR",
            "KICAD8_SYMBOL_DIR",
            "KICAD_SYMBOL_DIR",
        ]:
            val = os.environ.get(env_var)
            if val and os.path.exists(val):
                self.load_library_directory(val)
                return

        # Check well-known paths
        for ver in ["10.0", "9.0", "8.0", "7.0"]:
            candidate = f"C:\\Program Files\\KiCad\\{ver}\\share\\kicad\\symbols"
            if os.path.exists(candidate):
                self.load_library_directory(candidate)
                return

    def _load_builtins(self) -> None:
        """Load minimal built-in fallback symbol definitions.

        These provide basic symbol info (pin count, pin types) for the most
        common components, so the resolver works even without KiCad installed.
        """
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
