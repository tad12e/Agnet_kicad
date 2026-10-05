"""Validation for high-level KiCad tasks."""

from __future__ import annotations

from typing import List

from ..core.errors import AgentError, ErrorCategory, ErrorSeverity
from .task import Task, TaskType


class TaskValidator:
    """Validate structured high-level tasks before planning/execution."""

    def validate(self, task: Task) -> List[AgentError]:
        errors: List[AgentError] = []

        if not task.task_type:
            errors.append(AgentError(
                category=ErrorCategory.INVALID_PARAMETER,
                message="Task type is required.",
                operation="task_validation",
                severity=ErrorSeverity.ERROR,
            ))

        if not task.description or not task.description.strip():
            errors.append(AgentError(
                category=ErrorCategory.INVALID_PARAMETER,
                message="Task description cannot be empty.",
                operation="task_validation",
                severity=ErrorSeverity.ERROR,
            ))

        if task.domain not in {"pcb", "schematic", "system"}:
            errors.append(AgentError(
                category=ErrorCategory.INVALID_PARAMETER,
                message=f"Unsupported task domain: {task.domain}",
                operation="task_validation",
                severity=ErrorSeverity.ERROR,
            ))

        if task.task_type == TaskType.BUILD_CIRCUIT:
            circuit_type = task.requirements.get("circuit_type")
            if not circuit_type:
                errors.append(AgentError(
                    category=ErrorCategory.INVALID_PARAMETER,
                    message="BUILD_CIRCUIT tasks require a 'circuit_type' requirement.",
                    operation="task_validation",
                    severity=ErrorSeverity.ERROR,
                ))

            components = task.requirements.get("components")
            if components is None:
                errors.append(AgentError(
                    category=ErrorCategory.INVALID_PARAMETER,
                    message="BUILD_CIRCUIT tasks require a 'components' list.",
                    operation="task_validation",
                    severity=ErrorSeverity.ERROR,
                ))

        return errors
