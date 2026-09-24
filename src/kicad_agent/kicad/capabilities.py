"""KiCad capabilities and feature detection (Part 8 matrix).

Evidence basis (live-verified 2026-09 on KiCad 10.0.4, Windows):
- Schematic GetOpenDocuments/GetItems-style reads: WORK while server fresh.
- Schematic BeginCommit writes: REFUSED (persistent AS_NOT_READY), and the
  failed attempt wedges the server until restart.
- kicad-python schematic wrappers: broken on 0.7.1 and 0.8.0.
- PCB over IPC: out of scope here (PcbnewBackend owns PCB).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict
from .version import detect_kicad_version


@dataclass
class KiCadCapabilities:
    """Capability matrix for the current KiCad environment.

    Attributes:
        version: Detected KiCad version string.
        supports_ipc: Whether protobuf NNG IPC API is supported (KiCad 8+).
        supports_pcbnew_python: Whether embedded pcbnew Python module is available.
        supports_live_schematic_ipc: Legacy flag; True only where schematic
            WRITES were verified (none yet). Kept for backward compatibility.
        requires_sexpr_schematic_fallback: Whether S-expression fallback is
            needed for schematic writes.
        supports_live_schematic_reads: Schematic reads (documents/items/
            hierarchy/netlist) expected to work while the server is fresh.
        supports_live_schematic_writes: Schematic commit writes verified.
            False everywhere until a version proves otherwise live.
        notes: Human-readable evidence notes keyed by topic.
    """
    version: str = "8.0"
    supports_ipc: bool = True
    supports_pcbnew_python: bool = False
    supports_live_schematic_ipc: bool = False
    requires_sexpr_schematic_fallback: bool = True
    supports_live_schematic_reads: bool = False
    supports_live_schematic_writes: bool = False
    notes: Dict[str, str] = field(default_factory=dict)

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

        notes: Dict[str, str] = {}
        is_9 = ver.startswith("9.")
        is_10 = ver.startswith("10.")
        is_11_plus = ver.split(".")[0].isdigit() and int(ver.split(".")[0]) >= 11

        if is_9 or is_10:
            # Live-verified on 10.0.4: reads work fresh; BeginCommit refused
            # (persistent AS_NOT_READY); failed commit wedges server.
            reads, writes, fallback = True, False, True
            notes["schematic_writes"] = (
                f"KiCad {ver}: schematic BeginCommit refused live "
                "(AS_NOT_READY); failed attempts wedge the API server until "
                "restart. Writes go through SexprBackend fallback."
            )
            if is_10:
                notes["schematic_writes"] += (
                    " Upstream 10.0.x eeschema API-handler instability "
                    "(null-deref reports) is consistent with this."
                )
        elif is_11_plus:
            # Untested here: 11 expanded IPC (headless api-server, exports).
            # Optimistic on reads, conservative on writes until proven live.
            reads, writes, fallback = True, False, True
            notes["schematic_writes"] = (
                f"KiCad {ver}: schematic writes UNVERIFIED. Re-run the "
                "begin→drop dry run and a scratch-file failover test before "
                "trusting live commits; fallback stays on until then."
            )
        else:
            reads, writes, fallback = False, False, True
            notes["schematic_writes"] = (
                f"KiCad {ver}: pre-9 IPC API unsupported; file backends only."
            )

        return cls(
            version=ver,
            supports_ipc=not ver.startswith("7."),
            supports_pcbnew_python=has_pcbnew,
            supports_live_schematic_ipc=writes,
            requires_sexpr_schematic_fallback=fallback,
            supports_live_schematic_reads=reads,
            supports_live_schematic_writes=writes,
            notes=notes,
        )

    def describe(self) -> Dict[str, object]:
        """Plain-dict summary for diagnostics and traces."""
        return {
            "version": self.version,
            "supports_ipc": self.supports_ipc,
            "supports_pcbnew_python": self.supports_pcbnew_python,
            "supports_live_schematic_reads": self.supports_live_schematic_reads,
            "supports_live_schematic_writes": self.supports_live_schematic_writes,
            "requires_sexpr_schematic_fallback": self.requires_sexpr_schematic_fallback,
            "notes": dict(self.notes),
        }
