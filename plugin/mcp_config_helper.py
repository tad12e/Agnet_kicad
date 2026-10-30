import json
import os
import sys
from typing import Dict, List, Tuple


def get_repo_root() -> str:
    """Return the absolute path to the repository root directory."""
    current = os.path.abspath(os.path.dirname(__file__))
    # If this file is in <repo>/plugin, repo_root is parent
    parent = os.path.dirname(current)
    if os.path.exists(os.path.join(parent, "src", "kicad_agent")):
        return parent
    if os.path.exists(os.path.join(current, "src", "kicad_agent")):
        return current
    return parent


def get_claude_config_path() -> str:
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude_desktop_config.json")
    elif sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    else:
        return os.path.expanduser("~/.config/Claude/claude_desktop_config.json")


def get_cursor_config_path() -> str:
    if sys.platform == "win32":
        return os.path.join(os.environ.get("USERPROFILE", ""), ".cursor", "mcp.json")
    else:
        return os.path.expanduser("~/.cursor/mcp.json")


def get_antigravity_config_path() -> str:
    return os.path.expanduser("~/.gemini/config/mcp_config.json")


def configure_client(config_path: str, server_name: str, command: str, args: List[str], cwd: str, env: Dict[str, str]) -> bool:
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    if "mcpServers" not in data:
        data["mcpServers"] = {}

    server_entry = {
        "command": command,
        "args": args,
        "cwd": cwd,
    }
    if env:
        server_entry["env"] = env

    data["mcpServers"][server_name] = server_entry

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True


def auto_configure_all(repo_path: str = "") -> List[Tuple[str, bool, str]]:
    repo_root = repo_path or get_repo_root()
    src_dir = os.path.join(repo_root, "src")
    command = sys.executable
    args = ["-m", "kicad_agent.mcp.server", "--backend", "sexpr"]
    env = {"PYTHONPATH": src_dir}

    results = []
    targets = [
        ("Claude Desktop", get_claude_config_path()),
        ("Cursor", get_cursor_config_path()),
        ("Antigravity", get_antigravity_config_path()),
    ]

    for name, path in targets:
        try:
            configured = configure_client(path, "kicad", command, args, repo_root, env)
            results.append((name, configured, path))
        except Exception as e:
            results.append((name, False, str(e)))

    return results


if __name__ == "__main__":
    res = auto_configure_all()
    for name, ok, path in res:
        print(f"{name}: {'Configured' if ok else 'Failed'} ({path})")
