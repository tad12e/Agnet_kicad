"""KiCad capabilities and feature detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from .version import detect_kicad_version


@dataclass
class KiCadCapabilities:
    """Capability matrix for the current KiCad environment.
    
    Attributes:
        version: Detected KiCad version string.
        supports_ipc: Whether protobuf NNG IPC API is supported (KiCad 8+).
        supports_pcbnew_python: Whether embedded pcbnew Python module is available.
        supports_live_schematic_ipc: Whether live schematic CreateItems is supported.
        requires_sexpr_schematic_fallback: Whether S-expression fallback is needed for schematic symbols.
    """
    version: str = "8.0"
    supports_ipc: bool = True
    supports_pcbnew_python: bool = False
    supports_live_schematic_ipc: bool = True
    requires_sexpr_schematic_fallback: bool = False

    @classmethod
    def detect(cls) -> KiCadCapabilities:
        """Detect capabilities based on version and python environment."""
        ver = detect_kicad_version() or "8.0"
        
        has_pcbnew = False
        try:
            import pcbnew  # type: ignore[import]
            has_pcbnew = True
        except ImportError:
            has_pcbnew = False

        # In KiCad 10.0.x, live IPC CreateItems for symbols has a known C++ nullptr issue,
        # so S-expression manipulation fallback is used when editing local files on disk.
        is_kicad_10 = ver.startswith("10.")
        
        return cls(
            version=ver,
            supports_ipc=True,
            supports_pcbnew_python=has_pcbnew,
            supports_live_schematic_ipc=not is_kicad_10,
            requires_sexpr_schematic_fallback=is_kicad_10,
        )
