# KiCad AI Agent & Automation Platform

An autonomous pair-programming and design automation platform for **KiCad PCBNew** and **KiCad Schematic (Eeschema)** with a decoupled domain model, deterministic Action Intermediate Representation (IR), independent verifiers, and multi-tiered execution backends.

---

## 🏛️ Architecture Overview

The system strictly enforces separation of concerns: **the LLM decides WHAT should happen; the deterministic execution layer decides HOW it happens; the verifiers determine WHETHER it actually happened correctly.**

```
                           USER / PROMPT
                                 │
                                 ▼
                           AI AGENT
                                 │
                                 ▼
                          INTENT / PLANNER
                                 │
                                 ▼
                     ACTION IR / TRANSACTION
                                 │
                                 ▼
                             EXECUTOR
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
              PCB DOMAIN               SCHEMATIC DOMAIN
         (Board, Footprints,         (Symbols, Pins, Wires,
           Tracks, Vias, etc.)         Junctions, Buses)
                   │                           │
                   └─────────────┬─────────────┘
                                 ▼
                         BACKEND INTERFACE
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
            IPCBackend     PcbnewBackend    SexprBackend
            (Live IPC)      (in-process)     (Fallback)
                 └───────────────┬───────────────┘
                                 ▼
                            KICAD CANVAS
                                 │
                                 ▼
                        INDEPENDENT VERIFIER
         ┌───────────────────────┴───────────────────────┐
         ▼                       ▼                       ▼
 PlacementVerifier       DRC / NetVerifier        IntentVerifier
         └───────────────────────┬───────────────────────┘
                                 ▼
                           PASS / FAIL
                                 │
                 ┌───────────────┴───────────────┐
                 ▼ (Pass)                        ▼ (Fail)
             COMMIT                          ERROR ANALYZER
                                                 │
                                                 ▼
                                           REPAIR ENGINE
                                                 │
                                                 ▼
                                            RETRY / PLAN
```

---

## 📁 Repository Structure

```
.
├── src/
│   └── kicad_agent/
│       ├── __init__.py
│       ├── agent/                  # High-level AI agent orchestrator
│       │   ├── agent.py            # KiCadAgent orchestrator
│       │   ├── planner.py          # Request -> Goal & Action IR translator
│       │   ├── executor.py         # Deterministic action dispatcher
│       │   ├── verifier.py         # Verification coordinator
│       │   ├── error_analyzer.py   # Exception -> Structured AgentError classifier
│       │   ├── repair.py           # Multi-tiered repair & replanning engine
│       │   ├── state.py            # AgentState runtime model
│       │   └── context.py          # Design constraints & session context
│       │
│       ├── core/                   # Domain-neutral Action IR & Transactions
│       │   ├── actions.py          # Action, ActionType, ActionDomain
│       │   ├── goals.py            # Goal, GoalType
│       │   ├── plans.py            # Plan graph with dependencies
│       │   ├── results.py          # ActionResult, VerificationResult
│       │   ├── errors.py           # AgentError, ErrorCategory, ErrorSeverity
│       │   └── transactions.py     # Transaction rollback staging
│       │
│       ├── backends/               # Execution adapters
│       │   ├── base.py             # KiCadBackend abstract base class
│       │   ├── ipc.py              # Live socket IPC backend (KiCad 8+)
│       │   ├── pcbnew.py           # In-process native pcbnew Python module backend
│       │   └── sexpr.py            # S-expression parser/writer fallback backend
│       │
│       ├── pcb/                    # Pure PCB Domain Package
│       │   ├── board.py            # Board coordinator
│       │   ├── footprints.py       # Footprint & FootprintManager
│       │   ├── tracks.py           # Track & TrackManager
│       │   ├── vias.py             # Via & ViaManager
│       │   ├── zones.py            # Zone & ZoneManager
│       │   ├── nets.py             # PcbNet & PcbNetManager
│       │   ├── pads.py             # Pad definitions
│       │   ├── geometry.py         # Points, BoundingBox, mm/nm transformations
│       │   ├── operations.py       # High-level PCB domain operations
│       │   └── state.py            # PCBState snapshot
│       │
│       ├── schematic/              # Pure Schematic Domain Package
│       │   ├── schematic.py        # Schematic coordinator
│       │   ├── symbols.py          # Component, SymbolLibraryParser, SymbolResolver
│       │   ├── wires.py            # Wire & WireManager
│       │   ├── junctions.py        # Junction & JunctionManager
│       │   ├── labels.py           # Label & LabelManager
│       │   ├── buses.py            # Bus & BusManager
│       │   ├── operations.py       # SchematicOperations dispatcher
│       │   └── state.py            # SchematicState snapshot
│       │
│       ├── verification/           # Independent Verification Engine
│       │   ├── base.py             # BaseVerifier abstract class
│       │   ├── placement.py        # PlacementVerifier
│       │   ├── connectivity.py     # ConnectivityVerifier
│       │   ├── geometry.py         # GeometryVerifier
│       │   ├── routing.py          # RoutingVerifier
│       │   ├── drc.py              # DRCVerifier
│       │   ├── intent.py           # IntentVerifier
│       │   ├── structural.py       # StructuralVerifier
│       │   └── simulation.py       # SPICE / ngspice verification runner
│       │
│       ├── kicad/                  # KiCad discovery and capability detection
│       │   ├── client.py           # KiCadClient
│       │   ├── capabilities.py     # KiCadCapabilities matrix
│       │   ├── version.py          # Version discovery
│       │   ├── connection.py       # Connection endpoints
│       │   ├── messages.py         # Protobuf message exports
│       │   └── exceptions.py       # Domain exceptions
│       │
│       ├── ipc/                    # Low-level NNG & Protobuf transport
│       │   ├── client.py           # KiCadIPCClient with retry/backoff
│       │   ├── protocol.py         # Envelope serialization & unpacking
│       │   ├── messages.py         # Protobuf dynamic module loaders
│       │   ├── connection.py       # Default socket paths & client naming
│       │   └── exceptions.py       # Transport exceptions
│       │
│       ├── providers/              # LLM Reasoning Providers
│       │   ├── llm.py              # AnthropicProvider & LLMProvider base
│       │   └── __init__.py
│       │
│       ├── schemas/                # Pydantic validation schemas
│       │   ├── action.py           # ActionSchema
│       │   ├── plan.py             # PlanSchema & GoalSchema
│       │   ├── pcb.py              # FootprintSchema & TrackSchema
│       │   ├── schematic.py        # SymbolSchema & WireSchema
│       │   └── errors.py           # AgentErrorSchema
│       │
│       └── utils/                  # Shared utilities
│           ├── logging.py          # Centralized logger
│           └── paths.py            # KiCad system library path discovery
│
├── tests/
│   ├── unit/                       # Unit tests by subsystem
│   │   ├── agent/                  # Agent, planner, repair tests
│   │   ├── core/                   # Actions, plans, transactions tests
│   │   ├── pcb/                    # PCB operations & geometry tests
│   │   ├── schematic/              # Schematic symbols & models tests
│   │   ├── ipc/                    # IPC protocol & socket tests
│   │   ├── backends/               # Backend adapter tests
│   │   └── verification/           # Independent verifiers tests
│   ├── integration/                # End-to-end integration tests
│   │   ├── test_agent.py
│   │   ├── test_pcb.py
│   │   └── test_schematic.py
│   ├── fixtures/                   # Test fixtures
│   │   ├── pcb/                    # Sample .kicad_pcb files
│   │   └── schematic/              # Sample .kicad_sch files
│   ├── mock_pcbnew.py              # Offline test double for pcbnew
│   └── conftest.py                 # Global pytest configuration
│
├── scripts/
│   ├── run_tests.py                # Full test suite runner
│   ├── diagnostic_ipc.py           # Live IPC socket diagnostic
│   └── place_circuit.py            # Schematic placement demonstration
│
├── plugin/                         # KiCad ActionPlugin wrapper
│   ├── agent.py
│   ├── tools.py
│   └── ui.py
│
├── proto/                          # Compiled KiCad Protobuf definitions
├── requirements.txt                # Python dependencies
└── pyproject.toml                  # Package configuration (src layout)
```

---

## 🚀 Quickstart

### Running the Test Suite

Run the full test suite with KiCad's bundled Python interpreter:

```powershell
& "C:\Program Files\KiCad\10.0\bin\python.exe" scripts/run_tests.py
```

### Running with the Agent

```python
from kicad_agent.agent import KiCadAgent

agent = KiCadAgent()
result = agent.run("Place resistor R1 (10k) at (100, 100)", domain="pcb")
print("Result:", result["success"])
```

### Running Diagnostic IPC Check

```powershell
& "C:\Program Files\KiCad\10.0\bin\python.exe" scripts/diagnostic_ipc.py
```

---

## 🛡️ Key Architectural Principles

1. **Deterministic Execution**: The AI planner generates structured `Action` IR objects rather than executing arbitrary code on the canvas.
2. **Multi-Tiered Backends**: Primary automation uses live IPC or native `pcbnew` module, with a robust S-expression engine as a controlled fallback.
3. **Independent Verifiers**: Actions are verified by specialized domain checkers (`PlacementVerifier`, `ConnectivityVerifier`, `DRCVerifier`, `GeometryVerifier`, `IntentVerifier`).
4. **Structured Error Recovery**: Low-level exceptions are mapped to standardized `AgentError` instances and routed through a `RepairEngine` with rollback support via `Transaction`.
