"""High-level task layer for KiCad agent workflows."""

from .task import Task, TaskType
from .validator import TaskValidator

__all__ = ["Task", "TaskType", "TaskValidator"]
