"""Configuration storage for KiCad AI Agent plugin."""

import json
import os
from typing import Any, Dict


def get_config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    cfg_dir = os.path.join(base, "kicad_ai_agent")
    os.makedirs(cfg_dir, exist_ok=True)
    return cfg_dir


def get_config_file() -> str:
    return os.path.join(get_config_dir(), "config.json")


def load_config() -> Dict[str, Any]:
    fpath = get_config_file()
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "provider": "gemini",
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "model": "gemini-2.5-flash",
    }


def save_config(cfg: Dict[str, Any]) -> None:
    fpath = get_config_file()
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
