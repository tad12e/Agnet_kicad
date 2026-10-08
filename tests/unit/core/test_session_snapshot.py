import json

import pytest

from kicad_agent.core.session_snapshot import (
    SessionSnapshot,
    SessionSnapshotStore,
    SnapshotError,
)


def test_snapshot_round_trip_and_checksum(tmp_path):
    path = tmp_path / "session.json"
    original = SessionSnapshot(
        session_id="session-1",
        status="waiting_approval",
        mode="build",
        backend="sexpr",
        schematic="design.kicad_sch",
        pending_approvals={"request-1": {"request_id": "request-1"}},
    )
    SessionSnapshotStore.save(str(path), original)
    restored = SessionSnapshotStore.load(str(path))
    assert restored.to_dict() == original.to_dict()


def test_snapshot_rejects_tampering_and_unknown_version(tmp_path):
    path = tmp_path / "session.json"
    snapshot = SessionSnapshot(
        session_id="session-1", status="running", mode="build", backend="sexpr"
    )
    SessionSnapshotStore.save(str(path), snapshot)
    data = json.loads(path.read_text())
    data["status"] = "completed"
    path.write_text(json.dumps(data))
    with pytest.raises(SnapshotError) as exc:
        SessionSnapshotStore.load(str(path))
    assert exc.value.code == "SNAPSHOT_CORRUPT"

    data = snapshot.to_dict()
    data["version"] = 999
    path.write_text(json.dumps(data))
    with pytest.raises(SnapshotError) as exc:
        SessionSnapshotStore.load(str(path))
    assert exc.value.code == "UNSUPPORTED_SNAPSHOT_VERSION"
