"""KiCad PCB AI Agent CLI entry point.

Usage:
  python main.py "Create a PCB with an Arduino Leonardo, LED, resistor and connector"
  python main.py "Move R1 to (30, 20)"
  python main.py --board my_board.kicad_pcb "Rotate R1 by 90 degrees"
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure paths
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, "src")
_SITE = os.path.join(_ROOT, ".site-packages")
for p in [_SITE, _SRC, _ROOT]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

# Inject mock_pcbnew if native pcbnew is not accessible in standalone cli
try:
    import pcbnew
except ImportError:
    from tests import mock_pcbnew
    sys.modules["pcbnew"] = mock_pcbnew

from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.backends.sexpr import SexprBackend


def main():
    parser = argparse.ArgumentParser(description="KiCad PCB AI Agent")
    parser.add_argument("request", nargs="?", default="Create a PCB with an Arduino Leonardo, LED, resistor and connector", help="Natural language PCB design prompt")
    parser.add_argument("--board", default="", help="Path to .kicad_pcb board file to load")
    parser.add_argument("--backend", choices=["pcbnew", "sexpr", "auto"], default="auto", help="Execution backend adapter")
    parser.add_argument("--verbose", action="store_true", default=True, help="Print detailed trace log")
    args = parser.parse_args()

    # Select backend
    if args.backend == "pcbnew":
        backend = PcbnewBackend()
    elif args.backend == "sexpr":
        backend = SexprBackend(pcb_filepath=args.board or "board.kicad_pcb")
    else:
        pcb_be = PcbnewBackend()
        backend = pcb_be if pcb_be.is_available() else SexprBackend(pcb_filepath=args.board or "board.kicad_pcb")

    if args.board and hasattr(backend, "load_board"):
        try:
            backend.load_board(args.board)
        except Exception as e:
            print(f"[WARN] Could not load board '{args.board}': {e}")

    print("=" * 70)
    print("KiCad PCB AI Agent")
    print(f"Backend: {backend.name}")
    print(f"Request: {args.request}")
    print("=" * 70)

    agent = KiCadAgent(backend=backend)
    result = agent.run(args.request, domain="pcb")

    print("\n--- EXECUTION TRACE ---")
    trace_events = result.get("trace", {}).get("events", [])
    for ev in trace_events:
        print(f"[{ev.get('time', '')}] {ev.get('event_type', ''):<22} {ev.get('message', '')}")

    print("\n--- FINAL SUMMARY ---")
    status = "SUCCESS" if result.get("success") else "FAILED"
    print(f"Overall Status: {status}")
    print(f"Plan ID:        {result.get('plan_id')}")
    print(f"Actions Count:  {len(result.get('results', []))}")
    print(f"Transaction:    {result.get('transaction_state')}")
    final_components = result.get("final_state", {}).get("components", [])
    print(f"Board Footprints ({len(final_components)}):")
    for c in final_components:
        if isinstance(c, dict):
            print(f"  - {c.get('ref', c.get('reference'))} ({c.get('value', '')}) at ({c.get('x', 0)}, {c.get('y', 0)})")
    print("=" * 70)


if __name__ == "__main__":
    main()
