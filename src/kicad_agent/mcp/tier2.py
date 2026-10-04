"""Tier 2 MCP tool: run a whole design task through the built-in agent.

For small models that should not plan individual steps: one tool call,
plain English in, finished design out. Needs an Anthropic API key on
the server for the agent's planner.
"""

from __future__ import annotations

import os
from typing import Any, Dict


def run_design_task(session: Any, task: str, domain: str = "schematic") -> Dict[str, Any]:
    """Plan, execute, verify, and repair one design job via KiCadAgent."""
    from ..agent.agent import KiCadAgent

    if not task.strip():
        return {"status": "error", "code": "MISSING_ARGUMENT",
                "message": "run_design_task requires a non-empty 'task'"}
    domain = (domain or "schematic").lower()
    if domain not in ("schematic", "pcb"):
        return {"status": "error", "code": "BAD_DOMAIN",
                "message": f"Unknown domain '{domain}': use 'schematic' or 'pcb'"}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"status": "error", "code": "NO_API_KEY",
                "message": "run_design_task needs an Anthropic API key: "
                           "set ANTHROPIC_API_KEY in the server environment. "
                           "Tier 1 primitive tools work without one."}
    if domain == "schematic" and not session.sch_path:
        return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                "message": "No schematic open. Call open_schematic first."}
    if domain == "pcb" and not session.pcb_path:
        return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                "message": "No board open. Call open_pcb first."}
    backend = session.sch_backend if domain == "schematic" else session.pcb_backend
    try:
        agent = KiCadAgent(backend=backend)
        result = agent.run(task, domain=domain)
    except Exception as e:
        return {"status": "error", "code": "AGENT_FAILED",
                "message": f"Design task failed: {e}"}
    ok = bool(result.get("success", False)) if isinstance(result, dict) else False
    return {"status": "success" if ok else "error", "result": result}
