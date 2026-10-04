"""Live PCB IPC Backend (KiCad 10.0.x only).

PCB lane of the IPC transport, kept in a separate module from the
schematic lane (``backends/ipc.py``) on purpose: neither lane may import
from the other; both share only ``ipc/client.py`` and the KiCadBackend
interface.

Reads go through ``ipc/pcb/snapshot.py`` (PCBSnapshotReader); writes go
through ``ipc/pcb/mutations_pcb.py`` (commit lifecycle + per-item
verification).  Anything the 10.0 board API cannot express raises an
honest ``AgentError(INVALID_ACTION)`` instead of a fabricated success.

Optional ``fallback`` (e.g. a file-targeted SexprBackend) receives any
PCB-domain action the live server cannot serve: connection loss, IPC
refusal, or an unmapped action.  Failover results are marked with
``data["fallback_used"]=True`` and ``backend_used="ipc-pcb-><name>"``.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from ..core.actions import Action, ActionDomain, ActionType
from ..core.errors import AgentError, ErrorCategory
from ..core.results import ActionResult
from ..ipc.client import KiCadIPCClient
from ..ipc.exceptions import IPCRequestError
from ..ipc.messages import ApiStatusCode, DocumentType
from ..ipc.pcb import mutations_pcb
from ..ipc.pcb.messages_pcb import KiCadObjectTypePCB, get_board_type
from ..ipc.pcb.snapshot import PCBSnapshotReader
from .base import KiCadBackend


# =============================================================================
# Layer resolution (BoardLayer enum, 10.0 branch)
# =============================================================================

_NON_COPPER_LAYERS = {
    "F.SilkS": 40,
    "B.SilkS": 39,
    "F.Mask": 42,
    "B.Mask": 41,
    "F.Paste": 38,
    "B.Paste": 37,
    "F.Adhes": 36,
    "B.Adhes": 35,
    "Dwgs.User": 43,
    "Cmts.User": 44,
    "Eco1.User": 45,
    "Eco2.User": 46,
    "Edge.Cuts": 47,
    "Margin": 48,
    "B.CrtYd": 49,
    "F.CrtYd": 50,
    "B.Fab": 51,
    "F.Fab": 52,
}

_COPPER_LAYERS = {"F.Cu": 3, "B.Cu": 34}
for _i in range(1, 31):
    _COPPER_LAYERS[f"In{_i}.Cu"] = 3 + _i

_LAYER_BY_NAME = {**_COPPER_LAYERS, **_NON_COPPER_LAYERS}


def resolve_layer(layer: Any, default: int = 3) -> int:
    """Resolve a layer reference to a BoardLayer id.

    Accepts an int id (passed through), a standard name such as "F.Cu",
    or None (falls back to ``default``).  Raises AgentError(INVALID_PARAMETER)
    for anything else instead of guessing.
    """
    if layer is None:
        return default
    if isinstance(layer, bool):
        raise AgentError(
            category=ErrorCategory.INVALID_PARAMETER,
            message=f"Invalid PCB layer: {layer!r}",
        )
    if isinstance(layer, int):
        return layer
    if isinstance(layer, str):
        name = layer.strip()
        if name in _LAYER_BY_NAME:
            return _LAYER_BY_NAME[name]
        raise AgentError(
            category=ErrorCategory.INVALID_PARAMETER,
            message=f"Unknown PCB layer name: {layer!r}",
        )
    raise AgentError(
        category=ErrorCategory.INVALID_PARAMETER,
        message=f"Invalid PCB layer: {layer!r}",
    )


def _as_point(value: Any, name: str) -> Tuple[float, float]:
    """Coerce [x, y] / (x, y) parameters to a float pair."""
    try:
        x, y = value[0], value[1]
        return float(x), float(y)
    except (TypeError, ValueError, IndexError) as e:
        raise AgentError(
            category=ErrorCategory.INVALID_PARAMETER,
            message=f"Parameter {name!r} must be an [x, y] pair in mm (got {value!r})",
        ) from e


class IPCPCBBackend(KiCadBackend):
    """Live KiCad PCB IPC backend (10.0.x board API)."""

    # Backend-level errors eligible for PCB failover.
    FAILOVER_CATEGORIES = frozenset({
        ErrorCategory.CONNECTION_ERROR,
        ErrorCategory.IPC_ERROR,
        ErrorCategory.INVALID_ACTION,
    })

    def __init__(
        self,
        client: Optional[KiCadIPCClient] = None,
        socket_path: Optional[str] = None,
        fallback: Optional[KiCadBackend] = None,
    ):
        self.client = client or KiCadIPCClient(socket_path=socket_path)
        self.fallback = fallback
        self._doc_proto = None

    @property
    def name(self) -> str:
        return "ipc-pcb"

    def is_available(self) -> bool:
        try:
            return self.client.is_connected
        except Exception:
            return False

    def connect(self) -> None:
        self.client.connect()

    def disconnect(self) -> None:
        self.client.close()

    # ------------------------------------------------------------------
    # Documents: IPC works on the LIVE open board, never on files.
    # ------------------------------------------------------------------

    def load_board(self, filepath: str) -> Dict[str, Any]:
        raise AgentError(
            category=ErrorCategory.INVALID_ACTION,
            message="IPCPCBBackend manages the live open PCB, not files. Use "
            "PcbnewBackend/SexprBackend to load board files.",
        )

    def save_board(self, filepath: Optional[str] = None) -> bool:
        raise AgentError(
            category=ErrorCategory.INVALID_ACTION,
            message="IPCPCBBackend cannot save files. Use PcbnewBackend/SexprBackend.",
        )

    def load_schematic(self, filepath: str) -> Dict[str, Any]:
        raise AgentError(
            category=ErrorCategory.INVALID_ACTION,
            message="IPCPCBBackend is PCB-only. Use IPCBackend/SexprBackend for schematics.",
        )

    def save_schematic(self, filepath: Optional[str] = None) -> bool:
        raise AgentError(
            category=ErrorCategory.INVALID_ACTION,
            message="IPCPCBBackend is PCB-only. Use IPCBackend/SexprBackend for schematics.",
        )

    def _get_document(self, doc_type: int = DocumentType.DOCTYPE_PCB):
        """Resolve the live open PCB document.

        Honest-error contract (same as the schematic lane): NEVER fabricates
        a document. Raises AgentError(CONNECTION_ERROR) when KiCad is
        unreachable, has no PCB open, or rejects the request.
        """
        if self._doc_proto is not None and getattr(self._doc_proto, "type", None) == doc_type:
            return self._doc_proto

        reader = PCBSnapshotReader(self.client)
        try:
            doc = reader._get_document(doc_type)
        except AgentError:
            raise
        except RuntimeError as e:
            raise AgentError(
                category=ErrorCategory.CONNECTION_ERROR,
                message=f"GetOpenDocuments failed: {e}. Is KiCad running with "
                "the API server enabled (Preferences > Plugins) and a PCB open?",
            ) from e
        except Exception as e:
            if (isinstance(e, IPCRequestError)
                    and e.status_code == ApiStatusCode.AS_UNHANDLED):
                hint = ("No handler: open the PCB editor frame in KiCad "
                        "(double-click the .kicad_pcb) and retry.")
            else:
                hint = ("Is KiCad running with the API server enabled "
                        "(Preferences > Plugins)?")
            raise AgentError(
                category=ErrorCategory.CONNECTION_ERROR,
                message=f"GetOpenDocuments failed: {e}. {hint}",
            ) from e

        self._doc_proto = doc
        return doc

    def _reader(self) -> PCBSnapshotReader:
        return PCBSnapshotReader(self.client)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def get_state(self, domain: str = "pcb") -> Dict[str, Any]:
        """Live board state. Raises AgentError when no live PCB exists."""
        if domain != "pcb":
            raise AgentError(
                category=ErrorCategory.INVALID_ACTION,
                message=f"IPCPCBBackend is PCB-only; cannot serve domain {domain!r}.",
            )
        try:
            snapshot = self._reader().get_full_snapshot()
        except AgentError:
            raise
        except RuntimeError as e:
            raise AgentError(
                category=ErrorCategory.CONNECTION_ERROR,
                message=f"PCB snapshot read failed: {e}",
            ) from e
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"PCB snapshot read failed: {e}",
            ) from e

        info = snapshot.get("board_info", {})
        components = []
        for fp in snapshot.get("footprints", []):
            pos = fp.get("position", (0.0, 0.0))
            components.append({
                "ref": fp.get("reference", ""),
                "reference": fp.get("reference", ""),
                "value": fp.get("value", ""),
                "x": pos[0] if len(pos) > 0 else 0.0,
                "y": pos[1] if len(pos) > 1 else 0.0,
                "rotation": fp.get("orientation_deg", 0.0),
                "layer": fp.get("layer", 3),
                "id": fp.get("id", ""),
            })

        nets = snapshot.get("nets", [])
        return {
            "components": components,
            "component_count": len(components),
            "file": info.get("board_filename", ""),
            "board_filename": info.get("board_filename", ""),
            "project_name": info.get("project_name", ""),
            "nets": [n.get("name", "") for n in nets if isinstance(n, dict)],
            "tracks": snapshot.get("tracks", []),
            "tracks_count": snapshot.get("counts", {}).get("tracks", 0),
            "vias": snapshot.get("vias", []),
            "vias_count": snapshot.get("counts", {}).get("vias", 0),
            "zones": snapshot.get("zones", []),
            "zones_count": snapshot.get("counts", {}).get("zones", 0),
            "pads_count": snapshot.get("counts", {}).get("pads", 0),
            # NOTE: no unconnected_pads key on purpose — the 10.0 board API
            # exposes no ratsnest count, and reporting 0 would be fabricated.
        }

    # ------------------------------------------------------------------
    # Footprint lookup (reference -> KIID + proto)
    # ------------------------------------------------------------------

    def _resolve_footprint_id(self, doc, reference: str) -> str:
        """Map a reference designator to a live KIID via footprint scan."""
        want = (reference or "").upper()
        FootprintInstance = get_board_type("FootprintInstance")
        for any_msg in self._reader().get_footprints():
            fp = FootprintInstance()
            try:
                if not any_msg.Unpack(fp):
                    continue
            except Exception:
                continue
            ref_field = getattr(fp, "reference_field", None)
            text = getattr(getattr(ref_field, "text", None), "text", "")
            ref = str(getattr(text, "text", "") or "")
            if ref.upper() == want:
                return getattr(getattr(fp, "id", None), "value", "") or ""
        raise AgentError(
            category=ErrorCategory.MISSING_OBJECT,
            message=f"Footprint '{reference}' not found on the live board.",
            target_object=reference,
        )

    def _fetch_footprint(self, doc, footprint_id: str):
        """Fetch one FootprintInstance proto by KIID."""
        FootprintInstance = get_board_type("FootprintInstance")
        items = self._reader().get_items_by_id([footprint_id])
        if not items:
            raise AgentError(
                category=ErrorCategory.MISSING_OBJECT,
                message=f"Footprint id '{footprint_id}' vanished before update.",
            )
        fp = FootprintInstance()
        try:
            ok = items[0].Unpack(fp)
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=f"Fetched footprint did not unpack: {e}",
            ) from e
        if not ok:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message="Fetched footprint did not unpack.",
            )
        return fp

    # ------------------------------------------------------------------
    # Failover
    # ------------------------------------------------------------------

    def _should_failover(self, action: Action, err: AgentError) -> bool:
        """PCB-only failover gate."""
        return (
            self.fallback is not None
            and action.domain == ActionDomain.PCB
            and err.category in self.FAILOVER_CATEGORIES
        )

    def _execute_fallback(self, action: Action, t0: float, ipc_error: AgentError) -> ActionResult:
        """Delegate to the fallback backend, marking the result honestly."""
        assert self.fallback is not None
        try:
            result = self.fallback.execute(action)
        except Exception as e:
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=AgentError(
                    category=ErrorCategory.IPC_ERROR,
                    message=f"IPC failed ({ipc_error.message}) and fallback "
                    f"{self.fallback.name} raised: {e}",
                ),
                execution_time_ms=(time.time() - t0) * 1000,
                backend_used=f"ipc-pcb->{self.fallback.name}",
            )
        if not isinstance(result.data, dict):
            result.data = {"result": result.data}
        result.data["fallback_used"] = True
        result.data["ipc_error"] = ipc_error.message
        result.backend_used = f"ipc-pcb->{self.fallback.name}"
        return result

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, action: Action) -> ActionResult:
        t0 = time.time()
        try:
            return self._execute_live(action, t0)
        except Exception as e:
            err = e if isinstance(e, AgentError) else AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=str(e),
                operation=action.action_type.value,
            )
            if self._should_failover(action, err):
                return self._execute_fallback(action, t0, err)
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=err,
                execution_time_ms=(time.time() - t0) * 1000,
                backend_used=self.name,
            )

    def _execute_live(self, action: Action, t0: float) -> ActionResult:
        p = action.parameters
        t = action.action_type

        if action.domain != ActionDomain.PCB:
            raise AgentError(
                category=ErrorCategory.INVALID_ACTION,
                message=f"IPCPCBBackend is PCB-only; action domain is "
                f"{action.domain.value}. Schematic actions belong to IPCBackend.",
            )

        def _ok(data: Dict[str, Any]) -> ActionResult:
            return ActionResult(
                action_id=action.action_id,
                success=True,
                data=data,
                execution_time_ms=(time.time() - t0) * 1000,
                backend_used=self.name,
            )

        try:
            if t == ActionType.GET_STATE:
                return _ok(self.get_state("pcb"))

            doc = self._get_document(DocumentType.DOCTYPE_PCB)

            if t == ActionType.ADD_TRACK:
                start = p.get("start", (p.get("x1", 0.0), p.get("y1", 0.0)))
                end = p.get("end", (p.get("x2", 0.0), p.get("y2", 0.0)))
                start = _as_point(start, "start")
                end = _as_point(end, "end")
                width_mm = float(p.get("width_mm", 0.25))
                layer = resolve_layer(p.get("layer", "F.Cu"))
                net_name = str(p.get("net_name", ""))
                net_code = int(p.get("net", 0))
                created_id = mutations_pcb.add_track(
                    self.client, doc, start, end, width_mm, layer,
                    net_name, net_code,
                )
                if not created_id:
                    raise AgentError(
                        category=ErrorCategory.IPC_ERROR,
                        message="Server echoed track without an id (silent reject).",
                    )
                return _ok({"id": created_id, "items_created": 1})

            elif t == ActionType.ADD_VIA:
                at = _as_point(p.get("at", (p.get("x", 0.0), p.get("y", 0.0))), "at")
                size_mm = float(p.get("size_mm", 0.8))
                drill_mm = float(p.get("drill_mm", 0.4))
                raw_layers = p.get("layers", ("F.Cu", "B.Cu"))
                try:
                    layers = tuple(resolve_layer(v) for v in raw_layers)
                except TypeError as e:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message=f"Parameter 'layers' must be a pair of layers (got {raw_layers!r})",
                    ) from e
                if len(layers) != 2:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message=f"Parameter 'layers' must be a pair of layers (got {raw_layers!r})",
                    )
                net_name = str(p.get("net_name", ""))
                net_code = int(p.get("net", 0))
                created_id = mutations_pcb.add_via(
                    self.client, doc, at, size_mm, drill_mm,
                    net_name, net_code, 1, layers,
                )
                if not created_id:
                    raise AgentError(
                        category=ErrorCategory.IPC_ERROR,
                        message="Server echoed via without an id (silent reject).",
                    )
                return _ok({"id": created_id, "items_created": 1})

            elif t in (ActionType.ADD_ZONE, ActionType.CREATE_ZONE):
                polygon = p.get("polygon", [])
                try:
                    points = [_as_point(v, f"polygon[{i}]") for i, v in enumerate(polygon)]
                except TypeError as e:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message=f"Parameter 'polygon' must be a list of [x, y] pairs (got {polygon!r})",
                    ) from e
                if len(points) < 3:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message="A zone polygon needs at least 3 vertices.",
                    )
                layer = resolve_layer(p.get("layer", "F.Cu"))
                net_name = str(p.get("net_name", p.get("net", "GND") or "GND"))
                net_code = int(p.get("net", 0)) if str(p.get("net", "")).isdigit() else 0
                created_id = mutations_pcb.add_copper_zone(
                    self.client, doc, points, layer, net_name, net_code,
                )
                if not created_id:
                    raise AgentError(
                        category=ErrorCategory.IPC_ERROR,
                        message="Server echoed zone without an id (silent reject).",
                    )
                mutations_pcb.refill_zones(self.client, doc, [created_id])
                return _ok({"id": created_id, "items_created": 1, "refilled": True})

            elif t == ActionType.FILL_ZONE:
                ids = p.get("ids", p.get("zone_ids", None))
                if ids is not None and not isinstance(ids, (list, tuple)):
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message=f"Parameter 'ids' must be a list of KIIDs (got {ids!r})",
                    )
                mutations_pcb.refill_zones(
                    self.client, doc, list(ids) if ids else None,
                )
                return _ok({"refilled": True, "zone_ids": list(ids) if ids else "all"})

            elif t == ActionType.ADD_FOOTPRINT:
                ref = str(p.get("reference", p.get("ref", "")) or "")
                if not ref:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message="ADD_FOOTPRINT requires a 'reference'.",
                    )
                try:
                    x = float(p["x"])
                    y = float(p["y"])
                except (KeyError, TypeError, ValueError) as e:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message="ADD_FOOTPRINT requires numeric x/y.",
                    ) from e
                value = str(p.get("value", ""))
                rotation = float(p.get("rotation", 0.0))
                layer = resolve_layer(p.get("layer", "F.Cu"))
                footprint_id = str(p.get("footprint_id", p.get("footprint", "")) or "")
                lib = str(p.get("footprint_lib", p.get("library", "")) or "")
                mod = str(p.get("footprint_name", "") or "")
                if footprint_id and ":" in footprint_id:
                    lib, mod = footprint_id.split(":", 1)
                if not mod:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message="ADD_FOOTPRINT over live IPC needs a footprint "
                        "('footprint_id' like 'Resistor_SMD:R_0402' or "
                        "'footprint_lib' + 'footprint_name'); the server has "
                        "no component-type lookup.",
                    )
                created_id = mutations_pcb.add_footprint_instance(
                    self.client, doc, ref, value, (x, y), rotation,
                    layer, False, lib, mod,
                )
                if not created_id:
                    raise AgentError(
                        category=ErrorCategory.IPC_ERROR,
                        message="Server echoed footprint without an id (silent reject).",
                    )
                return _ok({"id": created_id, "reference": ref})

            elif t == ActionType.MOVE_FOOTPRINT:
                ref = str(p.get("reference", p.get("ref", "")) or "")
                if not ref:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message="MOVE_FOOTPRINT requires a 'reference'.",
                    )
                try:
                    x = float(p["x"])
                    y = float(p["y"])
                except (KeyError, TypeError, ValueError) as e:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message="MOVE_FOOTPRINT requires numeric x/y.",
                    ) from e
                rotation = p.get("rotation", None)
                fp_id = self._resolve_footprint_id(doc, ref)
                fp = self._fetch_footprint(doc, fp_id)
                fp.position.x_nm = int(round(x * 1_000_000))
                fp.position.y_nm = int(round(y * 1_000_000))
                if rotation is not None:
                    fp.orientation.value_degrees = float(rotation)
                updated = mutations_pcb.update_item_in_commit(
                    self.client, doc, fp, f"move footprint {ref}",
                )
                new_id = getattr(getattr(updated, "id", None), "value", "") or fp_id
                return _ok({"id": new_id, "reference": ref, "x": x, "y": y})

            elif t == ActionType.ROTATE_FOOTPRINT:
                ref = str(p.get("reference", p.get("ref", "")) or "")
                if not ref:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message="ROTATE_FOOTPRINT requires a 'reference'.",
                    )
                try:
                    angle = float(p.get("angle", p.get("rotation", 90.0)))
                except (TypeError, ValueError) as e:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message="ROTATE_FOOTPRINT requires a numeric angle.",
                    ) from e
                fp_id = self._resolve_footprint_id(doc, ref)
                fp = self._fetch_footprint(doc, fp_id)
                fp.orientation.value_degrees = angle
                updated = mutations_pcb.update_item_in_commit(
                    self.client, doc, fp, f"rotate footprint {ref}",
                )
                new_id = getattr(getattr(updated, "id", None), "value", "") or fp_id
                return _ok({"id": new_id, "reference": ref, "rotation": angle})

            elif t in (ActionType.REMOVE_FOOTPRINT, ActionType.DELETE_FOOTPRINT):
                ref = str(p.get("reference", p.get("ref", "")) or "")
                fp_id = str(p.get("id", "") or "")
                if not fp_id:
                    if not ref:
                        raise AgentError(
                            category=ErrorCategory.INVALID_PARAMETER,
                            message="REMOVE_FOOTPRINT requires a 'reference' or 'id'.",
                        )
                    fp_id = self._resolve_footprint_id(doc, ref)
                mutations_pcb.delete_items_in_commit(
                    self.client, doc, [fp_id], f"remove footprint {ref or fp_id}",
                )
                return _ok({"id": fp_id, "reference": ref})

            elif t == ActionType.REMOVE_TRACK:
                track_id = str(p.get("id", "") or "")
                if not track_id:
                    raise AgentError(
                        category=ErrorCategory.INVALID_PARAMETER,
                        message="REMOVE_TRACK requires an 'id' (live KIID).",
                    )
                mutations_pcb.delete_items_in_commit(
                    self.client, doc, [track_id], "remove track",
                )
                return _ok({"id": track_id})

            elif t in (ActionType.CREATE_BOARD_OUTLINE, ActionType.MODIFY_BOARD_OUTLINE):
                raise AgentError(
                    category=ErrorCategory.INVALID_ACTION,
                    message="Board outline drawing is not mapped to the 10.0 "
                    "PCB IPC surface (no Edge.Cuts primitive builder).",
                )

            elif t == ActionType.RUN_DRC:
                raise AgentError(
                    category=ErrorCategory.INVALID_ACTION,
                    message="RUN_DRC is not mapped to the 10.0 PCB IPC surface "
                    "(the board API exposes only InjectDrcError markers).",
                )

            elif t in (ActionType.LOAD_BOARD, ActionType.LOAD_DOCUMENT):
                return self.load_board(p.get("filepath", p.get("path", "")))

            elif t in (ActionType.SAVE_BOARD, ActionType.SAVE_DOCUMENT):
                self.save_board(p.get("filepath", p.get("path")))
                return _ok({"saved": True})

            else:
                if t in (ActionType.CREATE_NET, ActionType.ASSIGN_NET,
                         ActionType.ADD_PAD, ActionType.MODIFY_PAD,
                         ActionType.ROUTE_TRACK):
                    reason = (f"{t.value} is not mapped to the 10.0 PCB IPC "
                              "surface (no net/pad authoring handler).")
                elif t in (ActionType.CREATE_BOARD,):
                    reason = ("CREATE_BOARD is not mapped to the 10.0 PCB IPC "
                              "surface (IPC edits the open board, never creates files).")
                else:
                    reason = (f"Live PCB IPC execution for {t.value} is not "
                              "mapped (schematic actions belong to IPCBackend).")
                raise AgentError(
                    category=ErrorCategory.INVALID_ACTION,
                    message=reason,
                )

        except AgentError:
            raise
        except mutations_pcb.PCBMutationError as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=str(e),
                operation=t.value,
            ) from e
        except Exception as e:
            raise AgentError(
                category=ErrorCategory.IPC_ERROR,
                message=str(e),
                operation=t.value,
            ) from e
