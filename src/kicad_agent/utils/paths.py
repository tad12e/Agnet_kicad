"""Path resolution and KiCad environment directory discovery."""

from __future__ import annotations

import os


def get_kicad_footprints_dir() -> str:
    """Return the KiCad system footprint libraries directory."""
    for env in ["KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD8_FOOTPRINT_DIR", "KICAD_FOOTPRINT_DIR"]:
        val = os.environ.get(env)
        if val and os.path.exists(val):
            return val

    candidates = [
        r"C:\Program Files\KiCad\10.0\share\kicad\footprints",
        r"C:\Program Files\KiCad\9.0\share\kicad\footprints",
        r"C:\Program Files\KiCad\8.0\share\kicad\footprints",
        r"C:\Program Files\KiCad\7.0\share\kicad\footprints",
        "/usr/share/kicad/footprints",
        "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints",
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0]


def get_kicad_symbols_dir() -> str:
    """Return the KiCad system symbol libraries directory."""
    for env in ["KICAD10_SYMBOL_DIR", "KICAD9_SYMBOL_DIR", "KICAD8_SYMBOL_DIR", "KICAD_SYMBOL_DIR"]:
        val = os.environ.get(env)
        if val and os.path.exists(val):
            return val

    candidates = [
        r"C:\Program Files\KiCad\10.0\share\kicad\symbols",
        r"C:\Program Files\KiCad\9.0\share\kicad\symbols",
        r"C:\Program Files\KiCad\8.0\share\kicad\symbols",
        r"C:\Program Files\KiCad\7.0\share\kicad\symbols",
        "/usr/share/kicad/symbols",
        "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols",
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0]
