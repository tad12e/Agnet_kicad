"""KiCad IPC diagnostic and connection verification script (Part 1 probe).

READ-ONLY: opens a socket, sends GetOpenDocuments for SCHEMATIC and PCB,
prints environment/socket/version/status evidence. Sends NO mutating commands
(no CreateItems/UpdateItems/DeleteItems, no commits, no save).
"""

import glob
import os
import sys

# Ensure src is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".site-packages")))


def _mask(value: str, keep: int = 4) -> str:
    if not value:
        return "<unset>"
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> int:
    print("=" * 60)
    print("KiCad Agent IPC Diagnostic (Part 1 probe, read-only)")
    print("=" * 60)

    from kicad_agent.kicad.version import detect_kicad_version, is_kicad_running

    # Section 0: environment evidence (Reason 7b)
    section("0. Environment")
    for var in ("KICAD_API_SOCKET", "KICAD_API_TOKEN", "KICAD_API_TIMEOUT_MS"):
        raw = os.environ.get(var, "")
        shown = raw if var != "KICAD_API_TOKEN" else _mask(raw)
        print(f"{var} = {shown if raw else '<unset>'}")

    # Section 1: version, process, socket path, multi-instance scan (Reason 7a)
    section("1. KiCad installation & socket")
    ver = detect_kicad_version()
    running = is_kicad_running()
    print(f"Detected KiCad Version: {ver}")
    print(f"KiCad Process Running: {running}")
    try:
        from kicad_agent.kicad.capabilities import KiCadCapabilities

        caps = KiCadCapabilities.detect().describe()
        print(f"Schematic IPC reads: {caps['supports_live_schematic_reads']}, "
              f"writes: {caps['supports_live_schematic_writes']}, "
              f"sexpr fallback required: {caps['requires_sexpr_schematic_fallback']}")
    except Exception as e:  # pragma: no cover - defensive
        print(f"Capability matrix unavailable: {e}")

    # Multi-instance check: a zombie kicad.exe keeps ownership of api.sock
    # while the visible instance listens on a PID-suffixed pipe, so all
    # requests either refuse or go to the corpse (NOT_READY forever).
    try:
        import subprocess as _sp

        if os.name == "nt":
            _out = _sp.check_output("tasklist", shell=True, text=True,
                                    stderr=_sp.DEVNULL)
            _pids = [
                line.split()[1]
                for line in _out.splitlines()
                if line.lower().startswith("kicad.exe")
            ]
        else:
            _out = _sp.check_output(["pgrep", "-f", "kicad"],
                                    text=True, stderr=_sp.DEVNULL)
            _pids = [p for p in _out.split() if p.strip()]
        print(f"KiCad processes: {len(_pids)}" + (
            f" (PIDs {', '.join(_pids)})" if _pids else ""))
        if len(_pids) > 1:
            print("[WARN] Multiple KiCad processes: only the FIRST owns api.sock.")
            print("       stale ones answer NOT_READY forever. Quit KiCad fully")
            print("       (taskkill /IM kicad.exe /F) and start exactly one instance.")
    except Exception:
        pass

    try:
        from kicad_agent.ipc.connection import default_socket_path

        resolved = default_socket_path()
    except Exception as e:  # pragma: no cover - defensive
        resolved = f"<resolution failed: {e}>"
    print(f"Resolved socket path: {resolved}")

    # Scan for sibling api sockets (multi-instance PID-suffix trap).
    # NOTE: on Windows the socket is a named pipe, not a filesystem file,
    # so a zero-result glob is expected even when the pipe is live.
    if os.name == "nt":
        print("Socket type: Windows named pipe (no on-disk file expected).")
        print("If multiple KiCad instances run, extra pipes get PID-suffixed")
        print("names: set KICAD_API_SOCKET explicitly to target one instance.")
    else:
        temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
        candidates = sorted(glob.glob(os.path.join(temp_dir, "kicad", "api*.sock")))
        candidates += sorted(glob.glob("/tmp/kicad/api*.sock"))
        seen = []
        for c in candidates:
            if c not in seen:
                seen.append(c)
        print(f"api.sock candidates on disk ({len(seen)}):")
        for c in seen:
            marker = "  <-- resolved path" if c in resolved else ""
            print(f"  - {c}{marker}")
        if len(seen) > 1:
            print("[WARN] Multiple api.sock files: KiCad appends PID for extra instances.")
            print("       Set KICAD_API_SOCKET explicitly to target one instance.")
    if not running:
        print("[HINT] KiCad is not running: IPC requires a live GUI with")
        print("       Preferences > Plugins > Enable IPC API Server (KiCad 9/10).")

    # Section 2: kipy availability (Reason 1 readiness)
    section("2. Client libraries")
    try:
        import pynng  # noqa: F401

        print("pynng: installed")
    except ImportError:
        print("pynng: MISSING (pip install pynng) - IPC transport unavailable")
    try:
        import google.protobuf  # noqa: F401

        print("protobuf: installed")
    except ImportError:
        print("protobuf: MISSING (pip install protobuf)")
    try:
        # Subprocess isolation: kipy's bundled _pb2 files collide with our
        # vendored proto/ in one process (duplicate descriptor names), so the
        # kipy health check runs isolated and reports back as JSON.
        import json
        import subprocess

        probe_code = (
            "import json, sys; sys.path.insert(0, 'src'); "
            "from kicad_agent.ipc.kipy_client import describe_kipy; "
            "print(json.dumps(describe_kipy()))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe_code],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            raise RuntimeError(
                (completed.stderr.strip() or "kipy subprocess failed")[-500:]
            )
        info = json.loads(completed.stdout.strip())
        print(
            f"kicad-python (kipy): installed version {info.get('version')}"
            if info.get("installed")
            else "kicad-python (kipy): not installed"
        )
        print(f"  board wrapper: {'OK' if info.get('board_wrapper') else 'unavailable'}")
        print(
            f"  schematic wrapper: {'OK' if info.get('schematic_wrapper') else 'BROKEN upstream'}"
        )
        if info.get("schematic_wrapper_error"):
            print(f"    reason: {info['schematic_wrapper_error']}")
        print(
            f"  editor commit protos: {'OK' if info.get('editor_commit_protos') else 'unavailable'}"
        )
    except Exception as e:  # pragma: no cover - defensive
        print(f"kicad-python (kipy): status check failed: {e}")

    # Section 3: live GetOpenDocuments for BOTH doc types (Reasons 2/4/5)
    section("3. Live GetOpenDocuments (read-only)")
    try:
        from kicad_agent.ipc.client import KiCadIPCClient
        from kicad_agent.ipc.messages import (
            DocumentType,
            get_editor_command_protos,
        )
    except Exception as e:
        print(f"[FAIL] Cannot load IPC modules: {e}")
        return 1

    client = KiCadIPCClient(timeout_ms=5000)
    try:
        client.connect()
        print("[OK] Socket dial succeeded.")
    except Exception as e:
        print(f"[FAIL] Socket dial failed: {e}")
        print("[HINT] Is KiCad running with the API server enabled?")
        print("       Preferences > Plugins > Enable IPC API Server, then retry.")
        return 1

    try:
        _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
    except Exception as e:
        print(f"[FAIL] Cannot load editor protos: {e}")
        return 1

    overall_empty = True
    for label, dtype in (
        ("SCHEMATIC", DocumentType.DOCTYPE_SCHEMATIC),
        ("PCB", DocumentType.DOCTYPE_PCB),
    ):
        try:
            cmd = GetOpenDocuments()
            cmd.type = dtype
            resp = client.send(cmd, GetOpenDocumentsResponse)
        except Exception as e:
            # Surface status-code errors verbatim (Reason 2/6 evidence).
            print(f"[{label}] request failed: {type(e).__name__}: {e}")
            continue
        docs = list(resp.documents)
        if docs:
            overall_empty = False
        print(f"[{label}] open documents: {len(docs)}")
        for doc in docs:
            proj = getattr(doc, "project", None)
            proj_name = getattr(proj, "name", "") if proj is not None else ""
            proj_path = getattr(proj, "path", "") if proj is not None else ""
            print(
                f"  - type={getattr(doc, 'type', '?')} "
                f"board_filename={getattr(doc, 'board_filename', '')!r} "
                f"project_name={proj_name!r} project_path={proj_path!r}"
            )
    try:
        client.close()
    except Exception:
        pass

    # Section 4: interpretation hints (maps to the 7 reasons)
    section("4. Interpretation")
    if overall_empty:
        print("[HINT] Connected but zero documents: open a project with a")
        print("       schematic + PCB in KiCad and re-run. (Old code masked this")
        print("       with a dummy document - Part 3 removes that fallback.)")
    else:
        print("[OK] Live documents visible. Next: Part 2 (kipy transport) and")
        print("     Part 4 (commit protocol) turn these reads into safe writes.")
    print("\nProbe complete. No mutating commands were sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
