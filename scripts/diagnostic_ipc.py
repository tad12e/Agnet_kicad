"""KiCad IPC diagnostic and connection verification script."""

import os
import sys

# Ensure src is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".site-packages")))

from kicad_agent.ipc.client import KiCadIPCClient
from kicad_agent.ipc.messages import get_editor_command_protos, DocumentType
from kicad_agent.kicad.version import detect_kicad_version, is_kicad_running


def main():
    print("=" * 60)
    print("KiCad Agent IPC Diagnostic")
    print("=" * 60)

    ver = detect_kicad_version()
    running = is_kicad_running()
    print(f"Detected KiCad Version: {ver}")
    print(f"KiCad Process Running: {running}")

    print("\nAttempting IPC socket connection...")
    client = KiCadIPCClient(timeout_ms=5000)
    try:
        client.connect()
        print("[OK] Connected to KiCad socket successfully!")

        _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
        cmd = GetOpenDocuments()
        cmd.type = DocumentType.DOCTYPE_SCHEMATIC
        resp = client.send(cmd, GetOpenDocumentsResponse)
        print(f"[OK] Open Schematic Documents: {len(resp.documents)}")
        for doc in resp.documents:
            print(f"  - {doc.board_filename}")
    except Exception as e:
        print(f"[INFO] IPC connection status: {e}")


if __name__ == "__main__":
    main()
