"""KiCad plugin agent loop adapter using kicad_agent core."""

import os
import sys
from typing import Callable, Optional

# Ensure src/ is on path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_dir = os.path.join(_repo_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from kicad_agent.mcp.session import MCPSession
from kicad_agent.providers.llm import AnthropicProvider, GeminiProvider
from .config import load_config


def get_active_files() -> tuple[str, str]:
    """Detect current board and schematic file paths from KiCad pcbnew if available."""
    pcb_path = ""
    sch_path = ""
    try:
        import pcbnew
        board = pcbnew.GetBoard()
        if board:
            fname = board.GetFileName()
            if fname and os.path.exists(fname):
                pcb_path = os.path.abspath(fname)
                candidate_sch = os.path.splitext(pcb_path)[0] + ".kicad_sch"
                if os.path.exists(candidate_sch):
                    sch_path = candidate_sch
    except Exception:
        pass
    return pcb_path, sch_path


def create_plugin_session(provider_override=None, sch_path: str = "", pcb_path: str = "") -> MCPSession:
    cfg = load_config()
    provider_name = cfg.get("provider", "gemini").lower()

    if provider_override:
        provider = provider_override
    elif provider_name in ("gemini", "google"):
        key = cfg.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
        provider = GeminiProvider(api_key=key, model=cfg.get("model", "gemini-2.5-flash"))
    else:
        key = cfg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
        provider = AnthropicProvider(api_key=key, model=cfg.get("model", "claude-3-7-sonnet-20250219"))

    session = MCPSession(mode="sexpr", provider=provider)

    detected_pcb, detected_sch = get_active_files()
    active_sch = sch_path or detected_sch
    active_pcb = pcb_path or detected_pcb

    if active_sch and os.path.exists(active_sch):
        session.open_schematic(active_sch)
    if active_pcb and os.path.exists(active_pcb):
        session.open_pcb(active_pcb)

    return session


def run_agent(
    user_message: str,
    domain: str = "schematic",
    on_tool_call: Optional[Callable] = None,
    on_response: Optional[Callable] = None,
    sch_path: str = "",
    pcb_path: str = "",
):
    """Run an iterative AI agent task from inside the KiCad plugin."""
    session = create_plugin_session(sch_path=sch_path, pcb_path=pcb_path)

    # If domain requires schematic and none open, create one in cwd
    if domain == "schematic" and not session.sch_path:
        default_sch = os.path.abspath("new_schematic.kicad_sch")
        session.open_schematic(default_sch)

    res = session.start_llm_task(task=user_message, domain=domain, max_steps=15)

    if res.get("status") == "success":
        # Report summary
        reply = res.get("result", {}).get("summary", "Task completed.")
        if on_response:
            on_response(reply)
        return reply
    else:
        err = res.get("message") or res.get("error") or "Task encountered an error."
        if on_response:
            on_response(f"❌ Error: {err}")
        return err
