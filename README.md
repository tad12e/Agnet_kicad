# KiCad AI Agent

An AI-powered KiCad plugin that allows electronics engineers to design PCBs and schematics using natural language prompts powered by Claude 3.5 / 3.7 Sonnet.

## Overview

- **Live Board Manipulation:** Integrates with KiCad 8's `pcbnew` Python API.
- **Agent Reasoning:** Driven by Anthropic Claude API with tool use.
- **Embedded UI:** Built with wxPython, seamless integration in KiCad.
- **Simulation & Verification:** ngspice CLI integration & automated DRC error fixing.

## Project Structure

```
kicad-ai-agent/
├── plugin/
│   ├── __init__.py          # KiCad plugin entry point (ActionPlugin)
│   ├── agent.py             # Claude tool-use agent loop
│   ├── tools.py             # pcbnew board manipulation & DRC tools
│   ├── ui.py                # wxPython chat sidebar interface
│   └── simulation.py        # ngspice integration helpers
├── data/
│   └── training/            # Dataset for future fine-tuning
├── tests/
│   ├── mock_pcbnew.py       # Mock pcbnew module for testing outside KiCad
│   └── test_agent.py        # Agent loop & tool dispatch tests
├── README.md
└── requirements.txt
```

## Installation

### 1. KiCad Plugin Directory

Copy or link the `plugin/` directory to your KiCad 8 scripting plugins folder:

- **Windows:** `C:\Users\<USER>\Documents\KiCad\8.0\scripting\plugins\kicad-ai-agent\`
- **Linux:** `~/.local/share/kicad/8.0/scripting/plugins/kicad-ai-agent/`
- **macOS:** `~/Library/Preferences/KiCad/8.0/scripting/plugins/kicad-ai-agent/`

### 2. Dependencies

Install required Python dependencies:

```bash
pip install -r requirements.txt
```

Set your Anthropic API key in your environment variables:

```bash
# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="your-api-key-here"

# Linux / macOS
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Usage

1. Open **KiCad 8 PCB Editor**.
2. Navigate to **Tools → External Plugins → AI Agent** (or click the toolbar button).
3. Type commands in the chat sidebar, e.g.:
   - *"Place a 10k resistor R1 and a 100nF capacitor C1."*
   - *"Check the board for DRC errors and report."*
