"""Integration tests for KiCad AI Agent."""

import os
from kicad_agent.agent.agent import KiCadAgent
from kicad_agent.backends.sexpr import SexprBackend


def test_agent_integration_with_sexpr(tmp_path):
    pcb_file = os.path.join(tmp_path, "integration.kicad_pcb")
    with open(pcb_file, "w", encoding="utf-8") as f:
        f.write('(kicad_pcb (version 20260206) (generator "pcbnew")\n)\n')

    backend = SexprBackend(pcb_filepath=pcb_file)
    agent = KiCadAgent(backend=backend)

    res = agent.run("Place resistor R1 (10k) at (100, 100)", domain="pcb")
    assert res["success"]
    assert res["transaction_state"] == "committed"

    with open(pcb_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "R1" in content
