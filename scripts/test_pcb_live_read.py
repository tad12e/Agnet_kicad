"""Live PCB read test against open KiCad PCB window (read-only, no changes)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".site-packages"))

from kicad_agent.ipc.client import KiCadIPCClient
from kicad_agent.ipc.pcb.snapshot import PCBSnapshotReader


def main():
    print("=" * 60)
    print("Live PCB Read Test (read-only)")
    print("=" * 60)

    client = KiCadIPCClient(timeout_ms=5000)
    try:
        client.connect()
        print("[OK] Connected to KiCad IPC socket")
    except Exception as e:
        print(f"[FAIL] Socket connect failed: {e}")
        print("       Make sure KiCad is running with PCB window open")
        print("       and Preferences > Plugins > Enable IPC API Server is checked")
        return 1

    reader = PCBSnapshotReader(client)

    try:
        # 1. Board info
        print("\n--- Board Info ---")
        info = reader.get_board_info()
        print(f"Board file: {info['board_filename']}")
        print(f"Project:    {info['project_name']} ({info['project_path']})")

        # 2. Nets
        print("\n--- Nets ---")
        nets = reader.get_nets()
        print(f"Found {len(nets)} nets:")
        for n in nets[:20]:
            print(f"  {n['name']} (code={n['code']})")
        if len(nets) > 20:
            print(f"  ... and {len(nets) - 20} more")

        # 3. Footprints
        print("\n--- Footprints ---")
        fps = reader.get_footprints()
        print(f"Found {len(fps)} footprints:")
        for fp in fps:
            ref = fp.reference_field.text.text.text if fp.reference_field.text.text.text else ""
            val = fp.value_field.text.text.text if fp.value_field.text.text.text else ""
            pos = (fp.position.x_nm / 1_000_000.0, fp.position.y_nm / 1_000_000.0)
            print(f"  {ref}: {val} at ({pos[0]:.2f}, {pos[1]:.2f}) mm layer={fp.layer}")

        # 4. Tracks
        print("\n--- Tracks ---")
        tracks = reader.get_tracks()
        print(f"Found {len(tracks)} track segments + arcs:")
        for t in tracks[:10]:
            start = (t.start.x_nm / 1_000_000.0, t.start.y_nm / 1_000_000.0)
            end = (t.end.x_nm / 1_000_000.0, t.end.y_nm / 1_000_000.0)
            width = t.width.value_nm / 1_000_000.0
            print(f"  ({start[0]:.2f}, {start[1]:.2f}) -> ({end[0]:.2f}, {end[1]:.2f}) w={width:.3f}mm layer={t.layer}")
        if len(tracks) > 10:
            print(f"  ... and {len(tracks) - 10} more")

        # 5. Vias
        print("\n--- Vias ---")
        vias = reader.get_vias()
        print(f"Found {len(vias)} vias:")
        for v in vias[:10]:
            pos = (v.position.x_nm / 1_000_000.0, v.position.y_nm / 1_000_000.0)
            size = 0
            if v.pad_stack.copper_layers:
                size = v.pad_stack.copper_layers[0].size.x_nm / 1_000_000.0
            print(f"  ({pos[0]:.2f}, {pos[1]:.2f}) size={size:.3f}mm net={v.net.name if v.net else ''}")

        # 6. Zones
        print("\n--- Zones ---")
        zones = reader.get_zones()
        print(f"Found {len(zones)} zones:")
        for z in zones:
            print(f"  '{z.name}' net={z.copper_settings.net.name if z.copper_settings.net else ''} layers={list(z.layers)} filled={z.filled}")

        # 7. Stackup
        print("\n--- Stackup ---")
        stack = reader.get_board_stackup()
        print(f"Finish: {stack['finish']}")
        print(f"Copper layers: {stack['copper_layer_count']}")
        for l in stack['layers'][:5]:
            print(f"  {l['layer']} type={l['type']} enabled={l['enabled']} thick={l['thickness_mm']:.4f}mm name={l['user_name']}")

        # 8. Full snapshot (all in one)
        print("\n--- Full Snapshot (counts) ---")
        snap = reader.get_full_snapshot()
        for k, v in snap['counts'].items():
            print(f"  {k}: {v}")

    except Exception as e:
        print(f"\n[ERROR] Read failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        try:
            client.close()
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("Read test complete - no changes made to board")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())