"""KiCad version detection and environment discovery."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Optional, Tuple


def detect_kicad_version() -> Optional[str]:
    """Detect the installed KiCad major/minor version (e.g., '10.0', '8.0').
    
    Checks environment variables, installed paths, or CLI executables.
    """
    for env in ["KICAD_VERSION", "KICAD10_PATH", "KICAD9_PATH", "KICAD8_PATH"]:
        val = os.environ.get(env)
        if val:
            m = re.search(r"(\d+\.\d+)", val)
            if m:
                return m.group(1)

    # Check common install directories
    candidates = [
        r"C:\Program Files\KiCad\10.0",
        r"C:\Program Files\KiCad\9.0",
        r"C:\Program Files\KiCad\8.0",
        r"C:\Program Files\KiCad\7.0",
        "/usr/share/kicad",
        "/Applications/KiCad/KiCad.app",
    ]
    for c in candidates:
        if os.path.exists(c):
            m = re.search(r"(\d+\.\d+)", c)
            if m:
                return m.group(1)
            return "8.0"

    return "8.0"


def is_kicad_running() -> bool:
    """Check if a KiCad process is currently running on the system."""
    try:
        if os.name == "nt":
            output = subprocess.check_output("tasklist", shell=True, text=True, stderr=subprocess.DEVNULL)
            return "kicad.exe" in output.lower() or "eeschema.exe" in output.lower() or "pcbnew.exe" in output.lower()
        else:
            output = subprocess.check_output(["pgrep", "-f", "kicad"], text=True, stderr=subprocess.DEVNULL)
            return bool(output.strip())
    except Exception:
        return False
