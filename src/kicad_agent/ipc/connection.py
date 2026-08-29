"""KiCad IPC Connection Management.

Handles socket path discovery across platforms and unique client naming.
"""

from __future__ import annotations

import os
import platform
import random
import string
from tempfile import gettempdir


def default_socket_path() -> str:
    """Determine the platform-appropriate socket URI for KiCad IPC.

    KiCad's KICAD_API_SERVER listens on an NNG socket. The path depends on the platform:
    - Windows:  ipc://<TEMP>\\kicad\\api.sock
    - macOS:    ipc:///tmp/kicad/api.sock
    - Linux:    ipc:///tmp/kicad/api.sock (or Flatpak variant)

    The KICAD_API_SOCKET environment variable overrides all defaults.
    """
    env_path = os.environ.get("KICAD_API_SOCKET")
    if env_path is not None:
        return env_path

    if platform.system() == "Windows":
        temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or gettempdir()
        return f"ipc://{temp_dir}\\kicad\\api.sock"
    elif platform.system() == "Darwin":
        return "ipc:///tmp/kicad/api.sock"
    else:
        home = os.environ.get("HOME")
        if home:
            flatpak_socket = f"{home}/.var/app/org.kicad.KiCad/cache/tmp/kicad/api.sock"
            if os.path.exists(flatpak_socket):
                return f"ipc://{flatpak_socket}"
        return "ipc:///tmp/kicad/api.sock"


def generate_client_name(prefix: str = "kicad-ai-agent") -> str:
    """Generate a unique client name for commit tracking in KiCad."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}-{suffix}"
