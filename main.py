"""KiCad AI Agent CLI entry point.

Usage:
  # Schematic design (auto-detects open file in KiCad or creates one):
  python main.py "Place resistor R1 (10k) at (100, 100)"
  python main.py --domain schematic "Add a 10k resistor R1 and a red LED D1"
  python main.py --sch my_circuit.kicad_sch "Add resistor R2 (4.7k) at (120, 100)"

  # PCB design:
  python main.py --domain pcb "Create a PCB with an Arduino Leonardo, LED, resistor and connector"
  python main.py --board my_board.kicad_pcb "Move R1 to (30, 20)"
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure paths
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, "src")
_SITE = os.path.join(_ROOT, ".site-packages")
for p in [_SRC, _ROOT]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)
if os.path.exists(_SITE) and _SITE not in sys.path:
    sys.path.append(_SITE)

# Inject mock_pcbnew if native pcbnew is not accessible in standalone cli
try:
    import pcbnew
except ImportError:
    from tests import mock_pcbnew
    sys.modules["pcbnew"] = mock_pcbnew

from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.backends.ipc import IPCBackend
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.backends.sexpr import KiCad10SchematicWriter, SexprBackend
from kicad_agent.kicad.version import is_kicad_running


def resolve_domain(request: str, domain_arg: str, has_sch: bool, has_board: bool) -> str:
    """Determine whether the target domain is 'schematic' or 'pcb'."""
    if domain_arg in ("schematic", "pcb"):
        return domain_arg
    if has_sch and not has_board:
        return "schematic"
    if has_board and not has_sch:
        return "pcb"

    req = request.lower()
    schematic_kw = [
        "schematic", "symbol", "wire", "junction", "pin", "net label",
        "resistor", "capacitor", "diode", "led", "transistor", "r1", "r2",
        "d1", "c1", "u1", "connect", "power", "filter", "divider", "regulator",
        "supply", "circuit"
    ]
    pcb_kw = [
        "pcb", "board", "footprint", "track", "trace", "route", "via",
        "zone", "copper", "outline", "drc"
    ]

    sch_score = sum(1 for kw in schematic_kw if kw in req)
    pcb_score = sum(1 for kw in pcb_kw if kw in req)

    if sch_score > pcb_score:
        return "schematic"
    if pcb_score > sch_score:
        return "pcb"
    return "schematic" if "sch" in req else "pcb"


def resolve_schematic_target(sch_arg: str = "", backend_choice: str = "auto") -> tuple[str, str]:
    """Resolve target schematic file.

    Returns (resolved_filepath, origin_description)
    Origin can be 'explicit', 'live_ipc', 'workspace_existing', or 'auto_created'.
    """
    if sch_arg:
        resolved = os.path.abspath(sch_arg)
        if not os.path.exists(resolved):
            KiCad10SchematicWriter(resolved).save()
            return resolved, "auto_created"
        return resolved, "explicit"

    # 1. Try to auto-detect open document in running KiCad instance
    if is_kicad_running() and backend_choice in ("auto", "ipc"):
        try:
            ipc = IPCBackend()
            discovered = ipc.discover_open_schematic_path()
            if discovered and os.path.exists(discovered):
                return discovered, "live_ipc"
        except Exception:
            pass

    # 2. If KiCad is not running or no schematic is open in KiCad:
    # Do NOT search existing files - create a fresh new schematic file directly.
    target = os.path.abspath(os.path.join(os.getcwd(), "new_schematic.kicad_sch"))
    KiCad10SchematicWriter(target).save()
    return target, "auto_created"


def main():
    parser = argparse.ArgumentParser(
        description="KiCad AI Agent CLI (Schematic & PCB pair-programmer)"
    )
    parser.add_argument(
        "request",
        nargs="?",
        default="Place resistor R1 (10k) at (100, 100)",
        help="Natural language design prompt",
    )
    parser.add_argument(
        "--domain",
        choices=["auto", "schematic", "pcb"],
        default="auto",
        help="Target design domain (default: auto-detected from prompt/files)",
    )
    parser.add_argument(
        "--sch",
        "--schematic",
        default="",
        help="Path to .kicad_sch schematic file (auto-detected if omitted)",
    )
    parser.add_argument(
        "--board",
        default="",
        help="Path to .kicad_pcb board file (for PCB domain)",
    )
    parser.add_argument(
        "--backend",
        choices=["pcbnew", "sexpr", "ipc", "auto"],
        default="auto",
        help="Execution backend adapter (auto: live IPC with file fallback)",
    )
    parser.add_argument(
        "--fallback-file",
        default="",
        help="Explicit schematic file override for IPC failover",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Print detailed execution trace",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        default=False,
        help="Run autonomous neural LLM reasoning loop instead of deterministic planner",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "gemini", "anthropic", "mock"],
        default="auto",
        help="LLM provider for --llm mode (default: auto)",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Model name override (e.g. gemini-2.5-flash, gemini-1.5-pro, claude-3-7-sonnet)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=20,
        help="Maximum iterations for LLM reasoning loop (default: 20)",
    )
    args = parser.parse_args()

    domain = resolve_domain(args.request, args.domain, bool(args.sch), bool(args.board))

    sch_file = ""
    sch_origin = ""
    if domain == "schematic":
        sch_file, sch_origin = resolve_schematic_target(
            args.sch or args.fallback_file, backend_choice=args.backend
        )

    # Backend configuration
    if domain == "schematic":
        if args.backend == "sexpr":
            backend = SexprBackend(sch_filepath=sch_file)
        elif args.backend == "ipc":
            backend = IPCBackend(fallback=SexprBackend(sch_filepath=sch_file))
        else:  # auto
            # If KiCad is running, engage live IPC with Sexpr failover
            if is_kicad_running():
                backend = IPCBackend(fallback=SexprBackend(sch_filepath=sch_file))
            else:
                backend = SexprBackend(sch_filepath=sch_file)
    else:  # pcb
        if args.backend == "pcbnew":
            backend = PcbnewBackend()
        elif args.backend == "sexpr":
            backend = SexprBackend(pcb_filepath=args.board or "board.kicad_pcb")
        elif args.backend == "ipc":
            backend = IPCBackend()
        else:
            pcb_be = PcbnewBackend()
            backend = pcb_be if pcb_be.is_available() else SexprBackend(pcb_filepath=args.board or "board.kicad_pcb")

        if args.board and hasattr(backend, "load_board"):
            try:
                backend.load_board(args.board)
            except Exception as e:
                print(f"[WARN] Could not load board '{args.board}': {e}")

    print("=" * 70)
    print("KiCad AI Agent")
    print(f"Domain:   {domain.upper()}")
    print(f"Backend:  {backend.name}")
    if domain == "schematic":
        origin_label = {
            "explicit": "user specified",
            "live_ipc": "auto-detected from live KiCad window",
            "auto_created": "auto-created new file (KiCad window not detected)",
        }.get(sch_origin, sch_origin)
        print(f"Target:   {sch_file} ({origin_label})")
    elif args.board:
        print(f"Board:    {args.board}")
    print(f"Request:  {args.request}")
    print("=" * 70)

    if args.llm:
        provider = None
        if args.provider == "gemini":
            from kicad_agent.providers import GeminiProvider
            provider = GeminiProvider(model=args.model or "gemini-2.5-flash")
        elif args.provider == "anthropic":
            from kicad_agent.providers import AnthropicProvider
            provider = AnthropicProvider(model=args.model or "claude-3-7-sonnet-20250219")
        elif args.provider == "mock":
            from kicad_agent.providers import MockLLMProvider
            provider = MockLLMProvider()
        else:  # auto
            from kicad_agent.providers import GeminiProvider
            provider = GeminiProvider(model=args.model or "gemini-3.5-flash")

        print(f"Mode:     NEURAL LLM LOOP ({provider.__class__.__name__})")
        print(f"Model:    {getattr(provider, 'model', 'default')}")
        print("=" * 70)
        print("Starting LLM reasoning loop...")

        agent = KiCadAgent(backend=backend, provider=provider)
        result = agent.run_llm(args.request, domain=domain, max_steps=args.max_steps)
    else:
        agent = KiCadAgent(backend=backend)
        result = agent.run(args.request, domain=domain)

    print("\n--- EXECUTION TRACE ---")
    trace_events = result.get("trace", {}).get("events", [])
    for ev in trace_events:
        print(f"[{ev.get('time', '')}] {ev.get('event_type', ''):<22} {ev.get('message', '')}")

    print("\n--- FINAL SUMMARY ---")
    status = "SUCCESS" if (result.get("success") or result.get("status") == "completed") else "FAILED"
    print(f"Overall Status: {status}")
    if args.llm:
        print(f"Steps Taken:    {result.get('steps', 0)}")
        if result.get("content"):
            print(f"LLM Response:   {result.get('content')}")
    else:
        print(f"Plan ID:        {result.get('plan_id')}")
        print(f"Actions Count:  {len(result.get('results', []))}")
        print(f"Transaction:    {result.get('transaction_state')}")

    results_list = result.get("results", [])
    backends_used = set()
    for r in results_list:
        be = r.get("result", {}).get("backend_used") if isinstance(r.get("result"), dict) else None
        if be:
            backends_used.add(be)
    if backends_used:
        print(f"Backend Used:   {', '.join(backends_used)}")

    final_state = result.get("final_state") or backend.get_state(domain)
    if domain == "schematic":
        symbols = final_state.get("symbols", [])
        wires = final_state.get("wires", [])
        print(f"Schematic Symbols ({len(symbols)}):")
        for s in symbols:
            if isinstance(s, dict):
                ref = s.get("reference", s.get("ref", "?"))
                val = s.get("value", "")
                x = s.get("x_mm", s.get("x", 0))
                y = s.get("y_mm", s.get("y", 0))
                print(f"  - {ref} ({val}) at ({x}, {y})")
        if wires:
            print(f"Schematic Wires ({len(wires)}):")
            for w in wires:
                if isinstance(w, dict):
                    print(f"  - Wire from {w.get('start_mm', w.get('start'))} to {w.get('end_mm', w.get('end'))}")
        target_file = final_state.get("file", sch_file)
        if target_file:
            print(f"Saved to: {target_file}")
    else:
        final_components = final_state.get("components", [])
        print(f"Board Footprints ({len(final_components)}):")
        for c in final_components:
            if isinstance(c, dict):
                print(f"  - {c.get('ref', c.get('reference'))} ({c.get('value', '')}) at ({c.get('x', 0)}, {c.get('y', 0)})")

    print("=" * 70)


if __name__ == "__main__":
    main()
