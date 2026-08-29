"""Test Runner for KiCad AI Agent Test Suite."""

import os
import sys
import time
import traceback

# Ensure workspace paths are on sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = os.path.join(_ROOT, "src")
_SITE_PACKAGES = os.path.join(_ROOT, ".site-packages")
_PROTO = os.path.join(_ROOT, "proto")

for path in [_SITE_PACKAGES, _SRC, _PROTO, _ROOT]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

# Inject mock pcbnew for offline testing
from tests import mock_pcbnew
sys.modules["pcbnew"] = mock_pcbnew


def run_all_tests():
    print("=" * 70)
    print("RUNNING KICAD AI AGENT TEST SUITE")
    print("=" * 70)

    test_modules = [
        ("tests.unit.core.test_actions", [
            "test_action_creation_and_dict",
            "test_agent_error_structure",
            "test_plan_and_dependencies",
            "test_transaction_lifecycle",
        ]),
        ("tests.unit.pcb.test_geometry", [
            "test_mm_nm_conversions",
            "test_pair_conversions",
            "test_point_and_bounding_box",
        ]),
        ("tests.unit.pcb.test_pcb", [
            "test_board_initialization",
            "test_pcb_operations_with_sexpr",
        ]),
        ("tests.unit.schematic.test_models", [
            "test_component_model",
            "test_wire_model",
            "test_junction_model",
            "test_label_model",
        ]),
        ("tests.unit.schematic.test_symbols", [
            "test_symbol_resolver_builtins",
            "test_symbol_resolver_search",
            "test_symbol_parser_string",
        ]),
        ("tests.unit.ipc.test_ipc_messages", [
            "test_socket_discovery",
            "test_protobuf_envelope_roundtrip",
            "test_ipc_exceptions",
        ]),
        ("tests.unit.backends.test_backends", [
            "test_pcbnew_backend_offline",
            "test_sexpr_backend_offline",
        ]),
        ("tests.unit.verification.test_verifiers", [
            "test_placement_verifier",
            "test_placement_collision_detection",
            "test_drc_verifier",
            "test_connectivity_verifier",
            "test_geometry_verifier",
        ]),
        ("tests.unit.agent.test_agent", [
            "test_planner_request_generation",
            "test_planner_multi_component_creation",
            "test_error_analyzer",
            "test_repair_engine",
            "test_action_validator_preconditions",
            "test_tool_registry",
            "test_agent_orchestrator_run",
        ]),
        ("tests.integration.test_agent_integration", [
            "test_agent_integration_with_sexpr",
        ]),
        ("tests.integration.test_pcb_integration", [
            "test_pcb_board_end_to_end",
            "test_pcb_natural_language_pipeline",
        ]),
        ("tests.integration.test_schematic_integration", [
            "test_schematic_end_to_end",
        ]),
    ]

    import tempfile
    passed = 0
    failed = 0
    t0 = time.time()

    sample_pcb_path = os.path.join(_ROOT, "tests", "fixtures", "pcb", "simple_board.kicad_pcb")
    sample_sch_path = os.path.join(_ROOT, "tests", "fixtures", "schematic", "simple_schematic.kicad_sch")

    for mod_name, test_funcs in test_modules:
        print(f"\n[SUITE] {mod_name}")
        try:
            mod = __import__(mod_name, fromlist=test_funcs)
        except Exception as e:
            print(f"  [FAIL] Could not import {mod_name}: {e}")
            traceback.print_exc()
            failed += len(test_funcs)
            continue

        for func_name in test_funcs:
            mock_pcbnew.ResetBoard()
            func = getattr(mod, func_name, None)
            if not func:
                print(f"  [FAIL] Function {func_name} not found in {mod_name}")
                failed += 1
                continue

            try:
                import inspect
                sig = inspect.signature(func)
                kwargs = {}
                tmp_dir = None
                if "tmp_path" in sig.parameters:
                    tmp_dir = tempfile.TemporaryDirectory()
                    kwargs["tmp_path"] = tmp_dir.name
                if "sample_pcb_file" in sig.parameters:
                    kwargs["sample_pcb_file"] = sample_pcb_path
                if "sample_sch_file" in sig.parameters:
                    kwargs["sample_sch_file"] = sample_sch_path

                func(**kwargs)
                print(f"  [PASS] {func_name}")
                passed += 1

                if tmp_dir:
                    try:
                        tmp_dir.cleanup()
                    except Exception:
                        pass
            except Exception as e:
                print(f"  [FAIL] {func_name}: {e}")
                traceback.print_exc()
                failed += 1

    duration = time.time() - t0
    print("\n" + "=" * 70)
    print(f"TEST RUN SUMMARY: {passed} PASSED, {failed} FAILED in {duration:.3f}s")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
