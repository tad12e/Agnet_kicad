"""Atomic JSON persistence for provider-neutral agent sessions."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Union

from .session import AgentSession


class SessionStoreError(RuntimeError):
    """Raised when an agent session cannot be saved or restored."""


class SessionStore:
    """Persist conversation state without storing provider credentials."""

    SCHEMA_VERSION = 1

    def save(
        self,
        session: AgentSession,
        path: Union[str, os.PathLike[str]],
    ) -> str:
        """Atomically write a versioned session snapshot and return its path."""
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "session": session.to_dict(),
        }
        try:
            fd, temporary = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=str(target.parent),
                text=True,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except (OSError, TypeError, ValueError) as exc:
            try:
                if "temporary" in locals():
                    os.unlink(temporary)
            except OSError:
                pass
            raise SessionStoreError(
                f"Could not save session to '{target}': {exc}"
            ) from exc
        return str(target)

    def load(self, path: Union[str, os.PathLike[str]]) -> AgentSession:
        """Load and validate a persisted agent session."""
        target = Path(path).expanduser()
        try:
            with target.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("schema_version") != self.SCHEMA_VERSION:
                raise SessionStoreError(
                    f"Unsupported session schema version: "
                    f"{payload.get('schema_version')}"
                )
            session_data = payload.get("session")
            if not isinstance(session_data, dict):
                raise SessionStoreError("Session snapshot is missing 'session'.")
            return AgentSession.from_dict(session_data)
        except SessionStoreError:
            raise
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise SessionStoreError(
                f"Could not load session from '{target}': {exc}"
            ) from exc
