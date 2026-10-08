"""Deterministic structural validation for execution plans."""

from __future__ import annotations

from typing import Dict, List, Set

from .plans import Plan


class PlanValidator:
    """Validate action IDs, dependencies, and stage membership before execution."""

    def validate(self, plan: Plan) -> List[str]:
        errors: List[str] = []
        action_ids = [action.action_id for action in plan.actions]
        known_ids = set(action_ids)

        if len(action_ids) != len(known_ids):
            errors.append("Plan contains duplicate action IDs.")

        for action_id, prerequisites in plan.dependencies.items():
            if action_id not in known_ids:
                errors.append(f"Dependency target '{action_id}' is not in the plan.")
            for prerequisite in prerequisites:
                if prerequisite not in known_ids:
                    errors.append(
                        f"Dependency '{prerequisite}' for '{action_id}' is not in the plan."
                    )
                if prerequisite == action_id:
                    errors.append(f"Action '{action_id}' cannot depend on itself.")

        if self._has_cycle(plan.dependencies):
            errors.append("Plan dependencies contain a cycle.")

        stage_orders = [stage.order for stage in plan.stages]
        if len(stage_orders) != len(set(stage_orders)):
            errors.append("Plan stages must have unique order values.")

        staged_actions: Set[str] = set()
        for stage in plan.stages:
            for action_id in stage.action_ids:
                if action_id not in known_ids:
                    errors.append(
                        f"Stage '{stage.name}' references unknown action '{action_id}'."
                    )
                if action_id in staged_actions:
                    errors.append(f"Action '{action_id}' appears in multiple stages.")
                staged_actions.add(action_id)

        return errors

    @staticmethod
    def _has_cycle(graph: Dict[str, List[str]]) -> bool:
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dependency in graph.get(node, []):
                if visit(dependency):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)
