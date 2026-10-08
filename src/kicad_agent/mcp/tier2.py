"""Tier 2 MCP tool: run a whole design task through the iterative agent."""

from __future__ import annotations

import os
from typing import Any, Dict


def run_design_task(session: Any, task: str, domain: str = "schematic") -> Dict[str, Any]:
    """Run one design job through the same provider-driven loop as Tier 3."""
    if not task.strip():
        return {"status": "error", "code": "MISSING_ARGUMENT",
                "message": "run_design_task requires a non-empty 'task'"}
    domain = (domain or "schematic").lower()
    if domain not in ("schematic", "pcb"):
        return {"status": "error", "code": "BAD_DOMAIN",
                "message": f"Unknown domain '{domain}': use 'schematic' or 'pcb'"}
    if (
        getattr(session, "llm_provider", None) is None
        and not os.environ.get("ANTHROPIC_API_KEY")
    ):
        return {"status": "error", "code": "NO_API_KEY",
                "message": (
                    "run_design_task requires a configured LLM provider or "
                    "ANTHROPIC_API_KEY."
                )}
    if domain == "schematic" and not session.sch_path:
        return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                "message": "No schematic open. Call open_schematic first."}
    if domain == "pcb" and not session.pcb_path:
        return {"status": "error", "code": "NO_ACTIVE_DOCUMENT",
                "message": "No board open. Call open_pcb first."}
    try:
        result = session.start_llm_task(task, domain=domain)
    except Exception as e:
        return {"status": "error", "code": "AGENT_FAILED",
                "message": f"Design task failed: {e}"}
    if result.get("code") in ("NO_PROVIDER", "NO_API_KEY"):
        return {
            "status": "error",
            "code": "NO_API_KEY",
            "message": (
                "run_design_task requires a configured LLM provider or "
                "ANTHROPIC_API_KEY."
            ),
        }
    if result.get("status") in {
        "completed",
        "waiting_approval",
        "cancelled",
        "max_steps",
        "recovery_exhausted",
        "final_verification_failed",
    }:
        return {"status": "success", "result": result}
    return {"status": "error", "result": result}
