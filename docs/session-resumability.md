# Session snapshots and resumability

The MCP session exposes `save_session` and `resume_session`. A snapshot is a
versioned JSON envelope containing the session identity, backend mode, open
documents, status, and pending approval requests.

Snapshots are written by atomic replacement and include a SHA-256 checksum.
Resume validates the kind, version, checksum, status, document paths, and
approval records before changing the live session. Unsupported versions,
tampering, malformed JSON, missing documents, and terminal statuses return
explicit error codes; they are never treated as an empty session.

Only `pending`, `running`, `waiting_approval`, and `waiting_user` sessions are
resumable. `completed`, `failed`, and `cancelled` snapshots remain useful as
audit records but cannot be resumed.
