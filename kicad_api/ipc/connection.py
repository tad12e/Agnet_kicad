"""KiCad IPC Connection Management.

Handles socket path discovery across platforms.
Separated from the client so the transport logic stays focused on
send/receive, while connection concerns live here.
"""

import os
import platform
import random
import string
from tempfile import gettempdir


def default_socket_path() -> str:
    """Determine the platform-appropriate socket URI for KiCad IPC.

    KiCad's KICAD_API_SERVER (defined in common/api/api_server.cpp) listens
    on a Nanomsg Next Gen (NNG) socket. The path depends on the platform:

    - Windows:  ipc://C:\\Users\\hp\\AppData\\Local\\Temp\\kicad\\api.sock (or dynamic TEMP)
    - macOS:    ipc:///tmp/kicad/api.sock
    - Linux:    ipc:///tmp/kicad/api.sock  (or Flatpak variant)

    The KICAD_API_SOCKET environment variable overrides all defaults.
    """
    env_path = os.environ.get("KICAD_API_SOCKET")
    if env_path is not None:
        return env_path

    if platform.system() == "Windows":
        # Resolve user Local\Temp directory or fallback to gettempdir()
        temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or gettempdir()
        return f"ipc://{temp_dir}\\kicad\\api.sock"
    elif platform.system() == "Darwin":
        return "ipc:///tmp/kicad/api.sock"
    else:
        # Linux / Unix — check for Flatpak install first
        home = os.environ.get("HOME")
        if home:
            flatpak_socket = (
                f"{home}/.var/app/org.kicad.KiCad/cache/tmp/kicad/api.sock"
            )
            if os.path.exists(flatpak_socket):
                return f"ipc://{flatpak_socket}"
        return "ipc:///tmp/kicad/api.sock"


def generate_client_name(prefix: str = "kicad-ai-agent") -> str:
    """Generate a unique client name for commit tracking in KiCad.

    KiCad's API server logs the client_name in commit messages
    (e.g., "Created items via API" includes the client name).
    Each session should have a unique suffix to distinguish concurrent clients.
    """
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}-{suffix}"
