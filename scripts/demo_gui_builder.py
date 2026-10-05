"""Generate real KiCad 10 project files using the AI Agent and open in KiCad.

Usage:
  # Generate a 5V regulated LM7805 power supply circuit
  python scripts/demo_gui_builder.py "Build a 5V regulated power supply using an LM7805" --open

  # Generate an LED circuit schematic and open in Eeschema
  python scripts/demo_gui_builder.py "Build a simple LED circuit" --domain schematic --open

  # Generate a PCB board and open in Pcbnew
  python scripts/demo_gui_builder.py "Create a PCB with an Arduino Leonardo, LED, and resistor" --domain pcb --open
"""

import argparse
import json
import os
import subprocess
import sys

# Set up paths
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = os.path.join(_ROOT, "src")
_SITE = os.path.join(_ROOT, ".site-packages")
for p in [_SITE, _SRC, _ROOT]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.backends.pcbnew import PcbnewBackend
from kicad_agent.backends.sexpr import KiCad10SchematicWriter, SexprBackend
from kicad_agent.pcb.board import Board
from kicad_agent.providers.llm import MockLLMProvider


KICAD_BIN_DIR = r"C:\Program Files\KiCad\10.0\bin"
KICAD_EXE = os.path.join(KICAD_BIN_DIR, "kicad.exe")
EESCHEMA_EXE = os.path.join(KICAD_BIN_DIR, "eeschema.exe")
PCBNEW_EXE = os.path.join(KICAD_BIN_DIR, "pcbnew.exe")


def create_kicad_pro(pro_path: str, project_name: str):
    """Create a standard KiCad 10 project definition file (.kicad_pro)."""
    pro_data = {
        "board": {
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.1,
                    "copper_line_width": 0.25,
                }
            }
        },
        "meta": {
            "filename": f"{project_name}.kicad_pro",
            "version": 1
        },
        "net_settings": {},
        "schematic": {
            "drawing": {}
        },
        "sheets": [
            ["", f"{project_name}.kicad_sch"]
        ]
    }
    with open(pro_path, "w", encoding="utf-8") as f:
        json.dump(pro_data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="KiCad AI Agent Project Builder & Visualizer")
    parser.add_argument(
        "request",
        nargs="?",
        default="Build a 5V regulated power supply using an LM7805",
        help="Natural language prompt for the agent",
    )
    parser.add_argument(
        "--domain",
        choices=["schematic", "pcb"],
        default="schematic",
        help="Target domain (schematic or pcb)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(_ROOT, "data", "generated_projects"),
        help="Directory to save the generated KiCad project",
    )
    parser.add_argument(
        "--project-name",
        default="agent_demo",
        help="Name of the generated project",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Automatically launch KiCad GUI after building",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    proj_dir = os.path.join(args.output_dir, args.project_name)
    os.makedirs(proj_dir, exist_ok=True)

    pro_file = os.path.join(proj_dir, f"{args.project_name}.kicad_pro")
    sch_file = os.path.join(proj_dir, f"{args.project_name}.kicad_sch")
    pcb_file = os.path.join(proj_dir, f"{args.project_name}.kicad_pcb")

    print("\n" + "=" * 70)
    print("🤖 KiCad AI Agent - Visual Project Generator")
    print("=" * 70)
    print(f"Request:      {args.request}")
    print(f"Domain:       {args.domain}")
    print(f"Project Dir:  {proj_dir}")
    print("=" * 70)

    # 1. Run the iterative Agent Controller loop
    backend = PcbnewBackend() if args.domain == "pcb" else SexprBackend(sch_filepath=sch_file)
    agent = KiCadAgent(backend=backend)

    print("\n[1/4] Executing AI agent multi-turn control loop...")
    result = agent.run(args.request, domain=args.domain)

    print(f"  Status:       {result['status'].upper()} (Success: {result['success']})")
    print(f"  Iterations:   {result['iterations']}")
    print(f"  Actions Done: {len(result['completed_actions'])}")
    print(f"  Transaction:  {result['transaction_state'].upper()}")

    print("\n--- AGENT ACTIONS EXECUTED ---")
    for idx, act in enumerate(result["completed_actions"], start=1):
        print(f"  {idx}. {act['action_type']}: {act['parameters']}")

    # 2. Check & Enhance KiCad 10 Schematic file
    print("\n[2/4] Verifying KiCad 10 schematic (.kicad_sch)...")
    symbols_placed = {}

    # Extract placed components from backend state or completed actions
    final_sch_state = backend.get_state("schematic")
    for s in final_sch_state.get("components", final_sch_state.get("symbols", [])):
        ref = s.get("ref", s.get("reference", ""))
        symbols_placed[ref] = (s.get("x", 100.0), s.get("y", 100.0))

    if not symbols_placed:
        for act in result["completed_actions"]:
            t = act["action_type"]
            p = act["parameters"]
            if t in ("add_symbol", "add_footprint"):
                ref = p.get("reference", "")
                symbols_placed[ref] = (p.get("x", 100.0), p.get("y", 100.0))

    # If schematic file wasn't written directly, generate it via writer
    if not os.path.exists(sch_file) or os.path.getsize(sch_file) < 100:
        sch_writer = KiCad10SchematicWriter(sch_file, project_name=args.project_name)
        for act in result["completed_actions"]:
            t = act["action_type"]
            p = act["parameters"]
            if t in ("add_symbol", "add_footprint"):
                ref = p.get("reference", "")
                val = p.get("value", "")
                pos = (p.get("x", 100.0), p.get("y", 100.0))
                lib_id = p.get("lib_id", "Device:R")
                sch_writer.add_symbol(lib_id=lib_id, reference=ref, value=val, position_mm=pos)
            elif t in ("add_wire", "add_track"):
                start = p.get("start", (100.0, 80.0))
                end = p.get("end", (100.0, 100.0))
                sch_writer.add_wire(start_mm=tuple(start), end_mm=tuple(end))
        sch_writer.save()

    print(f"  [OK] Schematic ready at {sch_file}")

    # 3. Generate clean KiCad 10 PCB file
    print("\n[3/4] Generating KiCad 10 PCB board (.kicad_pcb)...")
    with open(pcb_file, "w", encoding="utf-8") as f:
        f.write('(kicad_pcb (version 20260206) (generator "pcbnew")\n')
        f.write('  (general (thickness 1.6))\n')
        f.write('  (paper "A4")\n')
        f.write('  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (36 "B.SilkS" user "B.Silkscreen") (37 "F.SilkS" user "F.Silkscreen") (44 "Edge.Cuts" user))\n')
        f.write('  (setup (pad_to_mask_clearance 0))\n')
        f.write(')\n')

    board = Board(filepath=pcb_file)
    for ref, pos in symbols_placed.items():
        val = "10k"
        if ref.startswith("D"): comp_type, val = "led", "LED"
        elif ref.startswith("C"): comp_type, val = "capacitor", "0.1uF"
        elif ref.startswith("U"): comp_type, val = "ic", "LM7805"
        board.footprints.add(
            footprint_id="Resistor_SMD:R_0402_1005Metric",
            reference=ref,
            value=val,
            position=pos,
        )
    print(f"  [OK] Saved {pcb_file}")

    # 4. Generate .kicad_pro project file
    print("\n[4/4] Generating KiCad 10 Project file (.kicad_pro)...")
    create_kicad_pro(pro_file, args.project_name)
    print(f"  [OK] Saved {pro_file}")

    print("\n" + "=" * 70)
    print("🎉 KiCad Project Generated Successfully!")
    print("=" * 70)
    print(f"Project File:   {pro_file}")
    print(f"Schematic File: {sch_file}")
    print(f"PCB Board File: {pcb_file}")
    print("\nTo view your circuit visually, run any of the following:")
    print(f'  1. Open Entire Project in KiCad:')
    print(f'     & "{KICAD_EXE}" "{pro_file}"')
    print(f'  2. Open Schematic Directly:')
    print(f'     & "{EESCHEMA_EXE}" "{sch_file}"')
    print(f'  3. Open PCB Board Directly:')
    print(f'     & "{PCBNEW_EXE}" "{pcb_file}"')
    print("=" * 70)

    if args.open:
        target_app = EESCHEMA_EXE if args.domain == "schematic" else PCBNEW_EXE
        target_doc = sch_file if args.domain == "schematic" else pcb_file
        print(f"\n🚀 Launching {os.path.basename(target_app)} with {os.path.basename(target_doc)}...")
        try:
            subprocess.Popen([target_app, target_doc], shell=False)
            print("KiCad GUI opened in background!")
        except Exception as e:
            print(f"Could not automatically launch KiCad: {e}")


if __name__ == "__main__":
    main()
