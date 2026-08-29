"""Observability and execution trace logging for the KiCad AI Agent."""

from __future__ import annotations

import datetime
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceEvent:
    """A timestamped event in the agent execution lifecycle."""
    event_type: str  # PLAN_CREATED, ACTION_START, ACTION_RESULT, VERIFY_RESULT, ERROR, REPAIR_ATTEMPT, etc.
    timestamp: float = field(default_factory=time.time)
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def formatted_time(self) -> str:
        dt = datetime.datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%H:%M:%S")

    def to_log_string(self) -> str:
        return f"[{self.formatted_time}] {self.event_type:<18} {self.message}"


class AgentTrace:
    """Stores full observability trace of an agent session."""

    def __init__(self, user_request: str = ""):
        self.user_request = user_request
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.events: List[TraceEvent] = []
        self.metrics: Dict[str, Any] = {
            "total_actions": 0,
            "actions_passed": 0,
            "actions_failed": 0,
            "repairs_attempted": 0,
            "repairs_succeeded": 0,
            "retries": 0,
        }

    def record(self, event_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> TraceEvent:
        event = TraceEvent(
            event_type=event_type,
            timestamp=time.time(),
            message=message,
            details=details or {},
        )
        self.events.append(event)
        return event

    def finish(self, success: bool, final_state: Optional[Dict[str, Any]] = None):
        self.end_time = time.time()
        status = "COMPLETED_SUCCESS" if success else "FAILED"
        self.record("SESSION_END", f"Session finished with status: {status}")
        self.metrics["duration_seconds"] = round(self.end_time - self.start_time, 3)
        self.metrics["success"] = success
        if final_state:
            self.metrics["final_component_count"] = final_state.get("component_count", 0)

    def print_trace(self):
        """Print clean human-readable log stream."""
        for ev in self.events:
            print(ev.to_log_string())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_request": self.user_request,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metrics": self.metrics,
            "events": [
                {
                    "time": ev.formatted_time,
                    "event_type": ev.event_type,
                    "message": ev.message,
                    "details": ev.details,
                }
                for ev in self.events
            ],
        }
