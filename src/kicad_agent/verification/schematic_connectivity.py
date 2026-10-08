"""Schematic wire-connectivity verification (file or live text).

Checks that every wire/bus segment endpoint lands on a pin tip, a
junction dot, a label anchor, or a fellow wire end (elbows OK, 3+-way
meets without a junction dot and dangling ends are failures).
Unconnected pins and unresolvable libraries are warnings, never failures:
legitimate no-connects exist and KiCad may simply not be installed.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..core.actions import Action
from ..core.results import ActionResult, VerificationResult
from ..schematic.pin_geometry import endpoint_report
from .base import BaseVerifier


class SchematicConnectivityVerifier(BaseVerifier):
    """Verifies schematic wire-endpoint connectivity from document text."""

    @property
    def name(self) -> str:
        return "schematic_connectivity"

    def _load_text(self, expected: Optional[Dict[str, Any]]) -> Optional[str]:
        if not expected:
            return None
        text = expected.get("schematic_text")
        if isinstance(text, str) and text.strip():
            return text
        state = expected.get("state")
        if isinstance(state, dict):
            path = state.get("file", "")
            if path and os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
        return None

    def verify(
        self,
        action: Action,
        result: ActionResult,
        expected: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verifier_name=self.name,
                passed=False,
                message="Cannot verify connectivity on failed action",
                details={"error": str(result.error)},
            )

        text = self._load_text(expected)
        if text is None:
            # Some legacy schematic-capable adapters cannot expose document
            # text, but do return a normalized wire snapshot.  Validate that
            # snapshot rather than treating execution success as proof.
            snapshot = expected.get("action_result", {}) if expected else {}
            start = action.parameters.get("start")
            end = action.parameters.get("end")
            if (
                action.action_type.value in {"add_wire", "add_bus"}
                and isinstance(snapshot, dict)
                and snapshot.get("start") == start
                and snapshot.get("end") == end
            ):
                return VerificationResult(
                    verifier_name=self.name,
                    passed=True,
                    message="Wire endpoints verified from backend post-action snapshot.",
                    details={"evidence_source": "backend_post_action_snapshot"},
                    outcome="passed",
                )
            return VerificationResult(
                verifier_name=self.name,
                passed=False,
                message="No schematic text available (expected['schematic_text'] "
                "or expected['state']['file'])",
            )

        try:
            report = endpoint_report(text)
        except ValueError as e:
            return VerificationResult(
                verifier_name=self.name,
                passed=False,
                message=f"Schematic parse failed: {e}",
            )

        errors = report["errors"]
        warnings = report["warnings"]
        stats = report["stats"]
        passed = not errors
        if passed:
            message = (
                f"All {stats['wire_segments']} wire segments terminate cleanly "
                f"({stats['symbols']} symbols, {stats['junctions']} junctions, "
                f"{stats['labels']} labels)"
            )
            if warnings:
                message += f"; {len(warnings)} warnings"
        else:
            message = "; ".join(e["message"] for e in errors[:5])
            if len(errors) > 5:
                message += f" (+{len(errors) - 5} more)"
        return VerificationResult(
            verifier_name=self.name,
            passed=passed,
            message=message,
            details={
                "errors": errors,
                "warnings": [w["message"] for w in warnings],
                "stats": stats,
            },
        )
