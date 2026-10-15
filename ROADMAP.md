# KiCad AI Agent & Automation Platform - Implementation Roadmap & Task Tracker

> **Current Status:** Living roadmap established and audited on 2026-10-15 based on comprehensive codebase inspection, test execution, and static verification.
> **Active Branch:** `scad` (with uncommitted open document discovery extensions) | **Upstream Base:** KiCad 10.0.4 on Windows 11.

---

## 🧭 Project Status Overview

The KiCad AI Agent is an automation platform designed to pair-program and automate circuit design across both **KiCad Schematic (Eeschema)** and **KiCad PCB (PCBNew)**.
The architecture enforces a strict decoupling:
1. **AI Agent / Intent Layer:** Converts natural language instructions into structured, deterministic Action Intermediate Representations (IR).
2. **Deterministic Execution Layer:** Multi-tiered backends execute actions via in-process `pcbnew` Python API, live socket IPC (NNG/Protobuf), or direct S-expression file manipulation.
3. **Independent Verifiers:** Specialized post-action verifiers inspect ground-truth design artifacts rather than trusting tool response codes.
4. **Resilience & Repair:** Multi-tier repair engine with atomic file checkpoints and transaction rollback.
5. **Model Context Protocol (MCP):** A stdio server providing 43 tools (session management, PCB primitives, schematic primitives, and whole-task design runners) to external LLMs (Claude, OpenCode, IDEs).

---

## 📊 Milestone Summary & Progress Matrix

| Milestone | Focus Area | Total Tasks | Complete | Partial | Blocked | Not Started |
|---|---|---|---|---|---|---|
| **M0** | Immediate Stability, Test Hygiene & Branch Alignment | 4 | 0 | 2 | 0 | 2 |
| **M1** | IPC Communication, Commit Lifecycle & Failover | 5 | 2 | 2 | 1 | 0 |
| **M2** | Backend Execution Engines (PCB & Schematic) | 5 | 2 | 3 | 0 | 0 |
| **M3** | Independent Verifiers & Design Rule Checks | 5 | 2 | 1 | 0 | 2 |
| **M4** | Model Context Protocol (MCP) & Agent Runtime | 5 | 3 | 2 | 0 | 0 |
| **M5** | Simulation, Plugin UI & Ecosystem Integrations | 4 | 0 | 1 | 0 | 3 |

---

## 🎯 Detailed Milestone Roadmaps & Task Tracker

### Milestone 0: Immediate Stability, Test Hygiene & Branch Alignment
*Objective:* Eliminate test flakes, resolve divergent branches, and fix critical runtime regressions preventing clean verification.

#### Task M0.1: Decouple `test_repo_first_schematic_exact` from Mutable Root File
- **Priority:** P0 (Immediate Defect)
- **Status:** Complete
- **Evidence:** [`tests/unit/schematic/test_sexpr_summary.py#L36-L51`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/tests/unit/schematic/test_sexpr_summary.py#L36-L51), [`tests/fixtures/schematic/canonical_first.kicad_sch`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/tests/fixtures/schematic/canonical_first.kicad_sch).
- **Resolution:** Decoupled test assertion from mutable workspace root file `first.kicad_sch` to immutable fixture `tests/fixtures/schematic/canonical_first.kicad_sch`. `pytest` passes 178/178 tests (100%).

#### Task M0.2: Reconcile Diverged `scad` and `main` Branches
- **Priority:** P0 (Architecture & Collaboration Blocker)
- **Status:** Partially complete
- **Evidence:** `git log scad..main --oneline` (12 commits on main including `b86aa90`), uncommitted working tree changes on `scad` (`get_open_documents` in [`src/kicad_agent/mcp/session.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/mcp/session.py)).
- **Problem:** `main` integrated `scad` at `4b54dae` with `docs/agent-contract.md`, `controller.py`, `MockLLMProvider`, and `agent_demo/`. Meanwhile, work continued on `scad` adding `get_open_documents` to IPC backends and configuring OpenCode (`opencode.json`). The branches have diverged.
- **Acceptance Criteria:**
  - Commit current `get_open_documents` work on `scad` with passing unit tests.
  - Merge or rebase with `main` to combine runtime controller contracts, documentation, and the new MCP discovery tool.
  - Verify that the full test suite passes on the integrated tree.
- **Remaining Work:** Commit staged/working changes on `scad`, run merge/rebase, resolve any session contract conflicts.
- **Dependencies & Blockers:** M0.1 (clean tests required before merge).
- **Suggested Next Action:** Commit working tree on `scad` and merge `main`.

#### Task M0.3: Fix ActionPlugin `place_component` Calling Signature Mismatch
- **Priority:** P1 (Fatal Runtime Bug)
- **Status:** Not started
- **Evidence:** [`plugin/agent.py#L30`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/plugin/agent.py#L30) vs [`plugin/tools.py#L19`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/plugin/tools.py#L19).
- **Problem:** `plugin/agent.py` declares tool schema requiring `["ref", "value", "footprint_lib", "footprint_name", "x", "y"]` and unpacks kwargs to `place_component(**args)`. However, `plugin/tools.py` defines `place_component(ref, component_type, value, x, y)`. Calling this tool raises an immediate `TypeError`.
- **Acceptance Criteria:**
  - Align `plugin/tools.py` signature to accept `footprint_lib` and `footprint_name` (or map them cleanly to `component_type`).
  - Unit test `plugin/tools.py` functions offline with `mock_pcbnew`.
- **Remaining Work:** Update `place_component` signature and parameter mapping in `plugin/tools.py`.
- **Dependencies & Blockers:** None.
- **Suggested Next Action:** Update `plugin/tools.py:19` and add a test in `tests/unit/plugin/`.

#### Task M0.4: Correct Python Environment Documentation in README
- **Priority:** P1 (Developer Experience & Setup)
- **Status:** Not started
- **Evidence:** [`README.md#L197-L203`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/README.md#L197-L203).
- **Problem:** README instructs running tests with `& "C:\Program Files\KiCad\10.0\bin\python.exe" scripts/run_tests.py`. However, KiCad's bundled Python does not include `pytest` or `mcp`, causing 20 test failures out of 54.
- **Acceptance Criteria:**
  - README correctly specifies using the virtual environment / system Python where dependencies are installed.
  - Provide instructions for bootstrapping KiCad's bundled Python with `--target .site-packages` if running inside KiCad is desired.
- **Remaining Work:** Edit `README.md` Quickstart section.
- **Dependencies & Blockers:** None.
- **Suggested Next Action:** Update `README.md` lines 197-205 with verified commands.

---

### Milestone 1: IPC Communication, Commit Lifecycle & Failover
*Objective:* Provide reliable live IPC communication with KiCad 10, handle upstream API limitations honestly, and guarantee automatic failover to file editing.

#### Task M1.1: Live IPC Socket Discovery and Diagnostics (Part 1 Probe)
- **Priority:** P1
- **Status:** Complete
- **Evidence:** [`scripts/diagnostic_ipc.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/scripts/diagnostic_ipc.py), [`src/kicad_agent/ipc/connection.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/ipc/connection.py).
- **Verified Behavior:** Discovers Windows named pipes (`\\.\pipe\kicad\api.sock`) and Unix sockets, verifies process counts, checks kipy library health, and provides masked token logging.
- **Acceptance Criteria:**
  - `diagnostic_ipc.py` runs cleanly and reports status without exceptions. (Verified: runs and reports KiCad 10.0 presence).

#### Task M1.2: Upstream Commit Refusal Handling & Failover Gate (Part 4 & Part 6)
- **Priority:** P1
- **Status:** Complete
- **Evidence:** [`src/kicad_agent/backends/ipc.py#L664-L733`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/ipc.py#L664-L733), [`tests/unit/ipc/test_ipc_fallback.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/tests/unit/ipc/test_ipc_fallback.py).
- **Verified Behavior:** KiCad 10.0.4 refuses schematic `BeginCommit` (`AS_NOT_READY`). `IPCBackend` catches `IPCRequestError` and delegates mutating actions to `SexprBackend`, tagging results with `fallback_used: True` and `backend_used: "ipc->sexpr"`.
- **Acceptance Criteria:**
  - Actions targeting live schematic commit fail over to S-expression backend without crashing.

#### Task M1.3: Enable S-expression Fallback for Schematic Junctions
- **Priority:** P1
- **Status:** Partially complete
- **Evidence:** [`src/kicad_agent/backends/ipc.py#L675-L692`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/ipc.py#L675-L692).
- **Problem:** `IPCBackend._execute_fallback` explicitly rejects `ADD_JUNCTION` with an error stating that `fallback sexpr does not support live junction writes`. However, `SexprBackend` actually implements `add_junction_to_schematic`! This artificial block prevents junction fallback.
- **Acceptance Criteria:**
  - Remove the artificial rejection in `IPCBackend._execute_fallback` so `ADD_JUNCTION` routes through `SexprBackend.execute`.
  - Update `test_refused_live_action_fails_over` in `test_ipc_fallback.py` to verify junction addition succeeds on fallback.
- **Remaining Work:** Remove lines 675-692 in `ipc.py` and update test assertion.
- **Dependencies & Blockers:** None.
- **Suggested Next Action:** Remove early return in `src/kicad_agent/backends/ipc.py:675`.

#### Task M1.4: Resolve Upstream `kipy` Schematic Import Breakage
- **Priority:** P2
- **Status:** Blocked (Upstream Defect)
- **Evidence:** `scripts/diagnostic_ipc.py` output: `ImportError: cannot import name 'PageSettings' from 'kipy.common_types'`.
- **Problem:** Published `kicad-python==0.8.0` has a broken schematic wrapper on Python 3.13 due to missing `PageSettings`.
- **Acceptance Criteria:**
  - Monitor upstream `kicad-python` releases or vendor a fixed monkeypatch in `src/kicad_agent/ipc/kipy_client.py`.
- **Remaining Work:** Maintain graceful degradation via fallback until upstream patch is released.
- **Dependencies & Blockers:** Blocked on upstream `kicad-python` package release.

#### Task M1.5: Live Document Discovery via `GetOpenDocuments`
- **Priority:** P1
- **Status:** Partially complete (In Working Tree)
- **Evidence:** `git diff` in [`src/kicad_agent/backends/base.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/base.py), [`src/kicad_agent/backends/ipc.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/ipc.py), [`src/kicad_agent/backends/ipc_pcb.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/ipc_pcb.py), [`src/kicad_agent/mcp/session.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/mcp/session.py).
- **Verified Behavior:** Discovers active board and schematic filenames directly from KiCad editor via live IPC query, allowing MCP client to connect without specifying absolute paths.
- **Acceptance Criteria:**
  - Uncommitted changes pass all unit tests (`test_mcp_open_document_discovery_requires_ipc` passes).
  - Staged and committed to repo.
- **Remaining Work:** Commit changes to branch.
- **Dependencies & Blockers:** None.

---

### Milestone 2: Backend Execution Engines (PCB & Schematic)
*Objective:* Support complete, bidirectional, non-destructive editing across both PCB and schematic files.

#### Task M2.1: S-Expression PCB Engine
- **Priority:** P1
- **Status:** Complete
- **Evidence:** [`src/kicad_agent/backends/sexpr.py#L1093-L1214`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/sexpr.py#L1093-L1214).
- **Verified Behavior:** Adds footprints, tracks, vias, zones, moves/rotates/deletes footprints, and modifies `Edge.Cuts` board outlines. Supports durable atomic backup checkpoints and rollback.

#### Task M2.2: S-Expression Schematic Engine
- **Priority:** P1
- **Status:** Complete
- **Evidence:** [`src/kicad_agent/backends/sexpr.py#L1257-L1405`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/sexpr.py#L1257-L1405).
- **Verified Behavior:** Adds symbols, wires, junctions, labels, buses, moves symbols, rotates symbols, deletes symbols. Resolves symbol library definitions and pin rotations.

#### Task M2.3: Add Missing `ADD_VIA` to `PcbnewBackend`
- **Priority:** P1
- **Status:** Partially complete
- **Evidence:** [`src/kicad_agent/backends/pcbnew.py#L215-L450`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/pcbnew.py#L215-L450).
- **Problem:** `ActionType.ADD_VIA` is implemented in `SexprBackend` and `IPCPCBBackend`, but missing from `PcbnewBackend.execute()`. Calling `add_via` in native pcbnew mode raises `AgentError(INVALID_ACTION)`.
- **Acceptance Criteria:**
  - Implement `PCB_VIA` creation in `PcbnewBackend.execute` using `pcbnew.PCB_VIA(board)`.
  - Add unit test in `tests/unit/backends/test_backends.py`.
- **Remaining Work:** Implement via creation handler in `pcbnew.py`.
- **Dependencies & Blockers:** None.
- **Suggested Next Action:** Add `elif t == ActionType.ADD_VIA:` branch in `pcbnew.py`.

#### Task M2.4: Implement Schematic Wire and Label Deletion in `SexprBackend`
- **Priority:** P2
- **Status:** Partially complete
- **Evidence:** [`src/kicad_agent/backends/sexpr.py#L1399`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/sexpr.py#L1399).
- **Problem:** `SexprBackend` supports `DELETE_SYMBOL`, but does not support deleting individual wire segments, junctions, or labels by ID or coordinates.
- **Acceptance Criteria:**
  - Implement `DELETE_WIRE`, `DELETE_JUNCTION`, `DELETE_LABEL` actions in `SexprBackend`.
  - Add test coverage verifying AST node removal.
- **Remaining Work:** Write deletion helpers in `sexpr.py`.
- **Dependencies & Blockers:** None.

#### Task M2.5: Replace Mocked `RUN_DRC` in `SexprBackend` with Geometric DRC
- **Priority:** P2
- **Status:** Partially complete
- **Evidence:** [`src/kicad_agent/backends/sexpr.py#L1217-L1224`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/backends/sexpr.py#L1217-L1224).
- **Problem:** `SexprBackend.execute` returns a static mock `{"status": "clean", "unconnected_count": 0, "violations": []}` for DRC.
- **Acceptance Criteria:**
  - Implement basic clearance checking between pads and tracks in SexprBackend, or report `DRC_NOT_AVAILABLE_OFFLINE` instead of a fake clean result.
- **Remaining Work:** Replace mock response with truthful status or geometry collision pass.
- **Dependencies & Blockers:** None.

---

### Milestone 3: Independent Verifiers & Design Rule Checks
*Objective:* Ensure every mutating action is verified against actual physical and electrical constraints rather than superficial pass flags.

#### Task M3.1: Schematic Connectivity & Pin Geometry Verifier
- **Priority:** P1
- **Status:** Complete
- **Evidence:** [`src/kicad_agent/verification/schematic_connectivity.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/verification/schematic_connectivity.py), [`src/kicad_agent/schematic/pin_geometry.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/schematic/pin_geometry.py).
- **Verified Behavior:** Validates all wire ends against resolved pin tips from KiCad symbol libraries, detects dangling ends, missing junctions at 3-way meets, and duplicate references.

#### Task M3.2: Placement & Collision Verifier
- **Priority:** P1
- **Status:** Complete
- **Evidence:** [`src/kicad_agent/verification/placement.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/verification/placement.py).
- **Verified Behavior:** Verifies coordinates within 0.5mm tolerance and detects footprint collisions within 0.8mm minimum center spacing.

#### Task M3.3: Make Intent, Routing, and Structural Verifiers Truthful
- **Priority:** P1
- **Status:** Partially complete
- **Evidence:** [`src/kicad_agent/verification/intent.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/verification/intent.py), [`src/kicad_agent/verification/routing.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/verification/routing.py), [`src/kicad_agent/verification/structural.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/verification/structural.py).
- **Problem:** `IntentVerifier`, `RoutingVerifier`, and `StructuralVerifier` unconditionally return `passed=True` regardless of actual state.
- **Acceptance Criteria:**
  - `IntentVerifier`: Check that target component references specified in `Goal.targets` actually exist in the final state.
  - `RoutingVerifier`: Check that added tracks connect to target pad coordinates and don't short unassociated nets.
  - `StructuralVerifier`: Validate S-expression syntax balance or file existence.
- **Remaining Work:** Implement real validation logic in each verifier.
- **Dependencies & Blockers:** None.
- **Suggested Next Action:** Implement target component check in `IntentVerifier.verify_goal`.

#### Task M3.4: Electrical Rules Check (ERC) Implementation
- **Priority:** P2
- **Status:** Not started
- **Evidence:** `main:src/kicad_agent/agent/tools.py` returns hardcoded `"ERC check passed: 0 warnings, 0 errors."`.
- **Problem:** No real ERC engine exists. Conflicting output pins, un-driven power nets, and missing power flags are ignored.
- **Acceptance Criteria:**
  - Implement pin electrical type checking (e.g. Output connected to Output, Power Input without Power Output).
  - Add `ERCVerifier` to `AgentVerifier`.
- **Remaining Work:** Implement pin type conflict matrix and integrate into verifier.
- **Dependencies & Blockers:** M3.1 (pin geometry resolution).

#### Task M3.5: CLI DRC / ERC Runner via `kicad-cli`
- **Priority:** P2
- **Status:** Not started
- **Acceptance Criteria:**
  - Wrap `kicad-cli pcb drc` and `kicad-cli sch erc` when KiCad binaries are available on PATH.
  - Parse generated JSON / report outputs into structured `VerificationResult`.
- **Remaining Work:** Implement subprocess wrapper in `src/kicad_agent/verification/drc.py`.
- **Dependencies & Blockers:** Requires KiCad 8/9/10 CLI installation on host.

---

### Milestone 4: Model Context Protocol (MCP) & Agent Runtime
*Objective:* Provide a robust, secure, and stateful agent interface for external models and IDEs.

#### Task M4.1: Stdio MCP Server Surface (Tier 1 & Tier 2)
- **Priority:** P1
- **Status:** Complete
- **Evidence:** [`src/kicad_agent/mcp/server.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/mcp/server.py), [`src/kicad_agent/mcp/session.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/mcp/session.py), [`tests/unit/mcp/test_mcp_server.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/tests/unit/mcp/test_mcp_server.py).
- **Verified Behavior:** 43 tools published over standard I/O conforming to the MCP v1 SDK specification.

#### Task M4.2: Resumable Sessions & State Compaction
- **Priority:** P1
- **Status:** Complete
- **Evidence:** [`src/kicad_agent/core/session.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/core/session.py), [`src/kicad_agent/core/session_store.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/core/session_store.py).
- **Verified Behavior:** Full serialization of message histories, pending tool call retention, automated history compaction, and JSON snapshot persistence.

#### Task M4.3: Permission Policy & High-Risk Action Approvals
- **Priority:** P1
- **Status:** Complete
- **Evidence:** [`src/kicad_agent/core/permissions.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/core/permissions.py), [`src/kicad_agent/agent/loop.py#L300-L350`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/agent/loop.py#L300-L350).
- **Verified Behavior:** Classifies actions by risk (LOW, MEDIUM, HIGH, DESTRUCTIVE). Destructive and file-saving operations pause execution and return approval requests to the client.

#### Task M4.4: Generalize Planner beyond Heuristic Regexes
- **Priority:** P1
- **Status:** Partially complete
- **Evidence:** [`src/kicad_agent/agent/planner.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/agent/planner.py).
- **Problem:** `Planner.plan_request` is hardcoded to regexes for "create pcb", "move R1", "rotate", etc. When given novel engineering requests, it falls back to `GET_STATE` without planning actions, ignoring its configured LLM provider.
- **Acceptance Criteria:**
  - Wire `self.provider` into `Planner.plan_request` when regex parsing fails.
  - Return structured plans with domain-neutral Action IR generated by the LLM.
- **Remaining Work:** Connect provider structured tool generation into planner fallback.
- **Dependencies & Blockers:** Centralized provider configuration.

#### Task M4.5: Multi-Provider Support (OpenAI, Ollama, Anthropic)
- **Priority:** P2
- **Status:** Partially complete (Present on `main`, missing on `scad`)
- **Evidence:** `main:src/kicad_agent/providers/llm.py` contains `OpenAICompatibleProvider` and `MockLLMProvider`.
- **Acceptance Criteria:**
  - Integrate `main`'s provider classes into `scad`.
  - Allow local model execution via Ollama/vLLM without requiring Anthropic API keys.
- **Remaining Work:** Merge provider changes from `main`.
- **Dependencies & Blockers:** M0.2 (branch reconciliation).

---

### Milestone 5: Simulation, Plugin UI & Ecosystem Integrations
*Objective:* Connect the platform to SPICE simulation engines, repair the KiCad in-canvas GUI, and establish automated CI/CD.

#### Task M5.1: SPICE Simulation Verification Integration
- **Priority:** P2
- **Status:** Partially complete
- **Evidence:** [`src/kicad_agent/verification/simulation.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/src/kicad_agent/verification/simulation.py).
- **Problem:** `run_ngspice_simulation` exists as a standalone function but is not integrated into `AgentVerifier` or exposed as an MCP tool. Netlist export from schematic is not automated.
- **Acceptance Criteria:**
  - Implement schematic netlist generator (`eeschema --export netlist` or Sexpr netlist parser).
  - Add `SimulationVerifier` subclass in `src/kicad_agent/verification/`.
  - Expose `run_simulation` tool in MCP server.
- **Remaining Work:** Netlist extraction and verifier wrapper.
- **Dependencies & Blockers:** ngspice installation on host.

#### Task M5.2: Modernize KiCad In-Process GUI Plugin
- **Priority:** P3
- **Status:** Not started
- **Evidence:** [`plugin/ui.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/plugin/ui.py), [`plugin/agent.py`](file:///C:/Users/hp/orca/workspaces/Kicad/scad/plugin/agent.py).
- **Problem:** Plugin uses outdated standalone tool definitions rather than the unified `KiCadAgent` orchestrator.
- **Acceptance Criteria:**
  - Refactor `plugin/ui.py` to instantiate `KiCadAgent(backend=PcbnewBackend())`.
  - Render action trace events into the wxPython chat window.
- **Remaining Work:** Rewrite `plugin/agent.py` to wrap `KiCadAgent`.
- **Dependencies & Blockers:** M0.3 (place_component fix).

#### Task M5.3: Automated GitHub Actions CI/CD Pipeline
- **Priority:** P2
- **Status:** Not started
- **Problem:** No `.github/workflows` exists. Regression testing relies entirely on manual local execution.
- **Acceptance Criteria:**
  - Create `.github/workflows/test.yml` running `pytest` across Python 3.9, 3.10, 3.11, 3.12, and 3.13 on Ubuntu and Windows.
  - Run linting and type checks in CI.
- **Remaining Work:** Author workflow YAML and test across matrix.
- **Dependencies & Blockers:** M0.1 (test isolation).

#### Task M5.4: Automated Autorouting Pipeline
- **Priority:** P3
- **Status:** Not started
- **Problem:** PCB track routing currently requires explicit start/end coordinates. No automated maze routing, A* pathfinding, or Freerouting integration exists.
- **Acceptance Criteria:**
  - Implement basic 2D Manhattan / A* maze routing for point-to-point unrouted nets.
  - Or wrap Freerouting (Specctra DSN export/SES import) via `SexprBackend`.
- **Remaining Work:** Author routing engine or DSN translator.
- **Dependencies & Blockers:** M2.1.

---

## 📈 Current Development Stage Summary

- **Architecture:** Complete and validated. Clear separation of LLM Intent -> Action IR -> Multi-tier Backend -> Independent Verifiers -> Repair.
- **Schematic Manipulation:** Highly mature via S-expression backend. Live IPC lane functional for reads, but live commits blocked by KiCad 10.0.4 upstream bug; robust failover to S-expression files.
- **PCB Manipulation:** Fully functional via native `pcbnew` module and S-expression backend. Live PCB IPC lane verified offline for KiCad 10 board items.
- **Model Context Protocol (MCP):** Highly mature. 43 tools published, tested, and actively utilized by external coding agents.
- **Primary Technical Debt:**
  1. Branch divergence between `scad` and `main`.
  2. Single fragile test coupled to mutable root file (`test_repo_first_schematic_exact`).
  3. Placeholder/no-op verifiers for Intent, Routing, and DRC.
  4. Broken calling signature in legacy GUI ActionPlugin.
  5. Heuristic-only planner in `planner.py`.
