"""PCB mutation helpers for KiCad IPC (10.0.x only).

Create / Update / Delete with a commit lifecycle and per-item verification,
mirroring the schematic lane in ``backends/ipc.py``.

Rules kept from the schematic lane:
- Every write runs inside BeginCommit ... EndCommit and the commit is DROPPED
  on any failure, so a rejected edit never lingers in KiCad's undo history.
- A write is only reported successful when KiCad says so: request status
  IRS_OK, result count == sent count, every item status ISC_OK / IDS_OK, and
  the created KIID comes back from the server (never fabricated locally).
- Protos are resolved by name from the local proto/ directory only
  (``messages_pcb``), with no kipy fallback, to avoid protobuf
  descriptor-pool conflicts.
"""

from __future__ import annotations

import time
from typing import Any, Callable, List, Optional, Sequence, Tuple

from google.protobuf.empty_pb2 import Empty

from .messages_pcb import (
    get_base_type,
    get_board_command,
    get_board_type,
    get_commit_protos,
    get_editor_command,
    get_item_mutation,
)
from ..client import KiCadIPCClient
from ..exceptions import IPCRequestError, IPCTimeoutError
from ..messages import (
    ApiStatusCode,
    CommitAction,
    ItemDeletionStatus,
    ItemRequestStatus,
    ItemStatusCode,
)
from .types_pcb import (
    build_arc,
    build_copper_zone,
    build_footprint_instance,
    build_track,
    build_via,
    pack_any,
)


class PCBMutationError(Exception):
    """PCB mutation failed with details."""
    pass


# =============================================================================
# Commit lifecycle (same pattern as the schematic lane)
# =============================================================================

def begin_commit(client: KiCadIPCClient, doc) -> Any:
    """Open a KiCad edit commit; returns the commit id proto.

    ``doc`` is accepted for API symmetry but is never sent: in KiCad 10.0
    ``BeginCommit`` has no fields at all (kipy's ``Board.begin_commit`` sends a
    bare ``BeginCommit()``), so attaching a document header raises
    AttributeError.
    """
    BeginCommit, BeginCommitResponse, _, _ = get_commit_protos()
    cmd = BeginCommit()
    try:
        resp = client.send(cmd, BeginCommitResponse)
    except Exception as e:
        raise PCBMutationError(f"BeginCommit failed: {e}") from e
    return resp.id


def end_commit(client: KiCadIPCClient, commit_id, doc, message: str, drop: bool = False) -> None:
    """Close a commit (CMA_COMMIT) or roll it back (CMA_DROP).

    ``EndCommit`` carries only id/action/message in 10.0 — like BeginCommit it
    has no document header.
    """
    _, _, EndCommit, EndCommitResponse = get_commit_protos()
    cmd = EndCommit()
    cmd.id.CopyFrom(commit_id)
    cmd.action = CommitAction.CMA_DROP if drop else CommitAction.CMA_COMMIT
    cmd.message = message
    try:
        client.send(cmd, EndCommitResponse)
    except Exception as e:
        raise PCBMutationError(f"EndCommit failed: {e}") from e


def run_commit(client: KiCadIPCClient, doc, message: str, fn: Callable[[], Any]) -> Any:
    """Run fn() inside a commit; DROP the commit on any failure."""
    commit_id = begin_commit(client, doc)
    try:
        result = fn()
    except Exception:
        try:
            end_commit(client, commit_id, doc, "drop: " + message, drop=True)
        except Exception:
            pass
        raise
    end_commit(client, commit_id, doc, message)
    return result


# =============================================================================
# Verification helpers
# =============================================================================

def _created_id(resp, message_type) -> str:
    """Unpack the first created item's id; empty string when missing/unpackable."""
    try:
        item = message_type()
        if resp.created_items and resp.created_items[0].item.Unpack(item):
            return getattr(getattr(item, "id", None), "value", "") or ""
    except Exception:
        pass
    return ""


def _verify_create_response(resp, expected_count: int, item_type_name: str = "item") -> None:
    """Verify CreateItems: status OK, count matches, every item status ISC_OK."""
    if resp.status != ItemRequestStatus.IRS_OK:
        raise PCBMutationError(f"CreateItems rejected (request status {resp.status})")
    if len(resp.created_items) != expected_count:
        raise PCBMutationError(
            f"CreateItems count mismatch: sent {expected_count}, "
            f"server returned {len(resp.created_items)}"
        )
    failures = [
        r.status.error_message or f"code {r.status.code}"
        for r in resp.created_items
        if r.status.code != ItemStatusCode.ISC_OK
    ]
    if failures:
        raise PCBMutationError(f"CreateItems {item_type_name} failures: {'; '.join(failures)}")


def _create_one(client: KiCadIPCClient, doc, any_item, message_type, label: str, message: str) -> str:
    """CreateItems for a single item inside a commit; returns the server KIID."""
    CreateItems = get_editor_command("CreateItems")
    CreateItemsResponse = get_editor_command("CreateItemsResponse")

    def _create():
        cmd = CreateItems()
        cmd.header.document.CopyFrom(doc)
        cmd.items.append(any_item)
        resp = client.send(cmd, CreateItemsResponse)
        _verify_create_response(resp, 1, label)
        return _created_id(resp, message_type)

    return run_commit(client, doc, message, _create)


# =============================================================================
# Public mutation functions
# =============================================================================

def add_track(
    client: KiCadIPCClient,
    doc,
    start: Tuple[float, float],
    end: Tuple[float, float],
    width_mm: float = 0.25,
    layer: int = 3,
    net_name: str = "",
    net_code: int = 0,
    locked: bool = False,
) -> str:
    """Create a track segment inside a commit. Returns the created KIID."""
    track = build_track(start, end, width_mm, layer, net_name, net_code, locked)
    message = (
        f"add track {start[0]:.2f},{start[1]:.2f} -> {end[0]:.2f},{end[1]:.2f} "
        f"on layer {layer}"
    )
    return _create_one(client, doc, pack_any(track), get_board_type("Track"), "track", message)


def add_arc(
    client: KiCadIPCClient,
    doc,
    start: Tuple[float, float],
    mid: Tuple[float, float],
    end: Tuple[float, float],
    width_mm: float = 0.25,
    layer: int = 3,
    net_name: str = "",
    net_code: int = 0,
    locked: bool = False,
) -> str:
    """Create an arc track inside a commit. Returns the created KIID."""
    arc = build_arc(start, mid, end, width_mm, layer, net_name, net_code, locked)
    message = (
        f"add arc {start[0]:.2f},{start[1]:.2f} -> {end[0]:.2f},{end[1]:.2f} "
        f"on layer {layer}"
    )
    return _create_one(client, doc, pack_any(arc), get_board_type("Arc"), "arc", message)


def add_via(
    client: KiCadIPCClient,
    doc,
    position: Tuple[float, float],
    size_mm: float = 0.8,
    drill_mm: float = 0.4,
    net_name: str = "",
    net_code: int = 0,
    via_type: int = 1,
    layers: Tuple[int, int] = (3, 34),
    locked: bool = False,
) -> str:
    """Create a via inside a commit. Returns the created KIID."""
    via = build_via(position, size_mm, drill_mm, net_name, net_code, via_type, layers, locked)
    message = f"add via at {position[0]:.2f},{position[1]:.2f}"
    return _create_one(client, doc, pack_any(via), get_board_type("Via"), "via", message)


def add_copper_zone(
    client: KiCadIPCClient,
    doc,
    polygon: List[Tuple[float, float]],
    layer: int = 3,
    net_name: str = "GND",
    net_code: int = 0,
    clearance_mm: float = 0.5,
    min_thickness_mm: float = 0.25,
    fill_mode: int = 1,
    priority: int = 0,
    locked: bool = False,
) -> str:
    """Create a copper zone inside a commit.

    Returns the created KIID.  The zone is empty until ``refill_zones`` runs.
    """
    zone = build_copper_zone(
        polygon, layer, net_name, net_code,
        clearance_mm, min_thickness_mm, fill_mode, priority, locked
    )
    return _create_one(
        client, doc, pack_any(zone), get_board_type("Zone"), "zone",
        f"add copper zone '{net_name}'",
    )


def add_footprint_instance(
    client: KiCadIPCClient,
    doc,
    reference: str,
    value: str,
    position: Tuple[float, float],
    orientation_deg: float = 0.0,
    layer: int = 3,
    locked: bool = False,
    library_id: str = "",
    footprint_name: str = "",
) -> str:
    """Create a minimal footprint instance inside a commit. Returns the KIID.

    The footprint definition should already exist in a loaded KiCad library;
    this builds the instance only.
    """
    fp = build_footprint_instance(
        reference, value, position, orientation_deg,
        layer, locked, library_id, footprint_name
    )
    return _create_one(
        client, doc, pack_any(fp), get_board_type("FootprintInstance"), "footprint",
        f"add footprint {reference}",
    )


def update_item(client: KiCadIPCClient, doc, item) -> Any:
    """Update an existing item (must carry a valid KIID); returns the updated proto."""
    UpdateItems = get_item_mutation("UpdateItems")
    UpdateItemsResponse = get_item_mutation("UpdateItemsResponse")
    cmd = UpdateItems()
    cmd.header.document.CopyFrom(doc)
    cmd.items.append(pack_any(item))
    try:
        resp = client.send(cmd, UpdateItemsResponse)
    except Exception as e:
        raise PCBMutationError(f"UpdateItems failed: {e}") from e

    if resp.status != ItemRequestStatus.IRS_OK:
        raise PCBMutationError(f"UpdateItems rejected (request status {resp.status})")
    if len(resp.updated_items) != 1:
        raise PCBMutationError(
            f"UpdateItems count mismatch: expected 1, got {len(resp.updated_items)}"
        )
    if resp.updated_items[0].status.code != ItemStatusCode.ISC_OK:
        raise PCBMutationError(
            f"UpdateItems failed: {resp.updated_items[0].status.error_message or 'ISC error'}"
        )

    updated = type(item)()
    if not resp.updated_items[0].item.Unpack(updated):
        raise PCBMutationError("UpdateItems response did not unpack to the expected type")
    return updated


def update_item_in_commit(client: KiCadIPCClient, doc, item, message: str) -> Any:
    """Update an item inside a commit; returns the updated proto."""
    return run_commit(client, doc, message, lambda: update_item(client, doc, item))


def delete_items_by_id(client: KiCadIPCClient, doc, ids: Sequence[str]) -> None:
    """Delete items by KIID strings.

    Verifies the request status AND that every requested KIID reports IDS_OK;
    a missing deletion record counts as a failure.
    """
    DeleteItems = get_item_mutation("DeleteItems")
    DeleteItemsResponse = get_item_mutation("DeleteItemsResponse")
    cmd = DeleteItems()
    cmd.header.document.CopyFrom(doc)
    for value in ids:
        kiid = cmd.item_ids.add()
        kiid.value = value
    try:
        resp = client.send(cmd, DeleteItemsResponse)
    except Exception as e:
        raise PCBMutationError(f"DeleteItems failed: {e}") from e

    if resp.status != ItemRequestStatus.IRS_OK:
        raise PCBMutationError(f"DeleteItems rejected (request status {resp.status})")
    by_id = {r.id.value: r for r in resp.deleted_items}
    failures = []
    for value in ids:
        result = by_id.get(value)
        if result is None:
            failures.append(f"{value}: no deletion record")
        elif result.status != ItemDeletionStatus.IDS_OK:
            failures.append(f"{value}: deletion status {result.status}")
    if failures:
        raise PCBMutationError(f"DeleteItems failures: {'; '.join(failures)}")


def delete_items_in_commit(client: KiCadIPCClient, doc, ids: Sequence[str], message: str) -> None:
    """Delete items inside a commit."""
    run_commit(client, doc, message, lambda: delete_items_by_id(client, doc, ids))


# =============================================================================
# Zone refill (blocking board operation)
# =============================================================================

def refill_zones(
    client: KiCadIPCClient,
    doc,
    zone_ids: Optional[Sequence[str]] = None,
    block: bool = True,
    max_poll_seconds: float = 30.0,
    poll_interval_seconds: float = 0.5,
) -> None:
    """Refill some (``zone_ids``) or all copper zones on the board.

    KiCad replies to RefillZones immediately with an empty message and then
    answers AS_BUSY to every request until the fill has finished
    (board_commands.proto).  With ``block=True`` this polls a cheap board read
    until the editor is free again, like kipy's ``Board.refill_zones``;
    with ``block=False`` it returns at once and the caller must expect AS_BUSY
    on the next request.
    """
    RefillZones = get_board_command("RefillZones")
    cmd = RefillZones()
    cmd.board.CopyFrom(doc)
    if zone_ids:
        for zid in zone_ids:
            cmd.zones.add().value = zid

    try:
        client.send(cmd, Empty)  # fire-and-forget: KiCad answers Empty
    except Exception as e:
        raise PCBMutationError(f"RefillZones failed: {e}") from e

    if not block:
        return
    _wait_until_board_is_free(client, doc, max_poll_seconds, poll_interval_seconds)


def _wait_until_board_is_free(
    client: KiCadIPCClient,
    doc,
    max_poll_seconds: float,
    poll_interval_seconds: float,
) -> None:
    """Poll a cheap board read until KiCad stops answering AS_BUSY.

    Uses GetBoardEnabledLayers because the 10.0 protos vendored here have no
    Ping command; any board query reports the same AS_BUSY state.
    """
    GetBoardEnabledLayers = get_board_command("GetBoardEnabledLayers")
    BoardEnabledLayersResponse = get_board_command("BoardEnabledLayersResponse")

    deadline = time.monotonic() + max(0.0, max_poll_seconds)
    last_error: Optional[Exception] = None

    while time.monotonic() < deadline:
        time.sleep(max(0.0, poll_interval_seconds))
        probe = GetBoardEnabledLayers()
        probe.board.CopyFrom(doc)
        try:
            client.send(probe, BoardEnabledLayersResponse)
            return
        except IPCRequestError as e:
            if e.status_code != ApiStatusCode.AS_BUSY:
                raise PCBMutationError(f"Zone refill probe failed: {e}") from e
            last_error = e
        except IPCTimeoutError as e:
            # Transport timeout: the editor is still busy with the fill.
            last_error = e

    raise PCBMutationError(
        f"Board still busy {max_poll_seconds}s after RefillZones ({last_error}); "
        "the zone fill may still be running."
    )


# =============================================================================
# Board origin (Group A)
# =============================================================================

def set_board_origin(
    client: KiCadIPCClient,
    doc,
    origin_mm: Tuple[float, float],
    origin_kind: str = "grid",
) -> None:
    """Move the board origin to ``origin_mm`` (x, y in mm).

    ``origin_kind`` is ``"grid"`` (the placement grid origin, BOT_GRID) or
    ``"drill"`` (the drill/place-file origin, BOT_DRILL).

    This deliberately runs inside a commit: moving the origin shifts every
    coordinate shown in the editor, so a failed call must never leave a
    half-applied origin behind.
    """
    SetBoardOrigin = get_board_command("SetBoardOrigin")
    BoardOriginType = get_board_command("BoardOriginType")
    kinds = {
        "grid": BoardOriginType.BOT_GRID,
        "drill": BoardOriginType.BOT_DRILL,
    }
    if origin_kind not in kinds:
        raise PCBMutationError(
            f"origin_kind must be one of {sorted(kinds)} (got {origin_kind!r})"
        )

    Vector2 = get_base_type("Vector2")

    def _set():
        cmd = SetBoardOrigin()
        cmd.board.CopyFrom(doc)
        cmd.type = kinds[origin_kind]
        origin = Vector2()
        origin.x_nm = int(round(origin_mm[0] * 1_000_000))
        origin.y_nm = int(round(origin_mm[1] * 1_000_000))
        cmd.origin.CopyFrom(origin)
        try:
            client.send(cmd, Empty)
        except Exception as e:
            raise PCBMutationError(f"SetBoardOrigin failed: {e}") from e

    run_commit(client, doc, f"set {origin_kind} origin", _set)


# =============================================================================
# Editor layer controls (Group A)
# =============================================================================

def set_visible_layers(client: KiCadIPCClient, doc, layers: Sequence[int]) -> None:
    """Show exactly ``layers`` (editor-only: does not change the stackup).

    Takes BoardLayer ids (e.g. 3 == BL_F_Cu).  Hiding all copper layers is
    refused locally, because that would leave KiCad showing an empty canvas.
    """
    if not layers:
        raise PCBMutationError("Refusing to hide every layer: pass at least one layer.")
    SetVisibleLayers = get_board_command("SetVisibleLayers")

    cmd = SetVisibleLayers()
    cmd.board.CopyFrom(doc)
    cmd.layers.extend(layers)
    try:
        client.send(cmd, Empty)
    except Exception as e:
        raise PCBMutationError(f"SetVisibleLayers failed: {e}") from e


def set_active_layer(client: KiCadIPCClient, doc, layer: int) -> int:
    """Switch the layer the editor draws on; returns the layer id sent."""
    SetActiveLayer = get_board_command("SetActiveLayer")

    cmd = SetActiveLayer()
    cmd.board.CopyFrom(doc)
    cmd.layer = layer
    try:
        client.send(cmd, Empty)
    except Exception as e:
        raise PCBMutationError(f"SetActiveLayer failed: {e}") from e
    return layer

