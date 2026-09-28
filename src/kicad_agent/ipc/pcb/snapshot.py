"""Live PCB snapshot reading via KiCad IPC (10.0.x only).

Provides read-only inspection of the open PCB board:
- GetOpenDocuments (PCB) -> board filename, project info
- GetItems (PCB_ITEM_TYPES) -> footprints, tracks, vias, zones, pads, etc.
- GetNets -> net names
- GetItemsByNet -> items filtered by one or more nets (Group A)
- GetConnectedItems -> items copper-connected to given item IDs (Group A)
- GetBoardStackup -> layer stackup info
- GetBoardEnabledLayers -> enabled layer list
- GetGraphicsDefaults -> line/text thickness per layer class
- GetVisibleLayers -> editor-visible layer list (Group A)
- GetActiveLayer -> editor active layer (Group A)
- SaveDocumentToString -> full board as S-expression text
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .messages_pcb import (
    get_base_type,
    get_board_command,
    get_board_command_protos,
    get_editor_command,
    get_editor_command_protos,
    get_base_type_protos,
    PCB_ITEM_TYPES,
    PCB_COPPER_ITEM_TYPES,
)
from ..client import KiCadIPCClient
from ..messages import DocumentType, ItemRequestStatus, ApiStatusCode


# =============================================================================
# PCB Snapshot Reader
# =============================================================================

class PCBSnapshotReader:
    """Read-only live PCB inspector via IPC.

    Usage:
        client = KiCadIPCClient()
        client.connect()
        reader = PCBSnapshotReader(client)
        snapshot = reader.get_full_snapshot()
    """

    def __init__(self, client: KiCadIPCClient):
        self.client = client
        self._doc = None

    def _get_document(self, doc_type: int = DocumentType.DOCTYPE_PCB):
        """Resolve the live open PCB document (cached)."""
        if self._doc is not None and getattr(self._doc, "type", None) == doc_type:
            return self._doc

        procs = get_editor_command_protos()
        GetOpenDocuments = procs[2]
        GetOpenDocumentsResponse = procs[3]
        cmd = GetOpenDocuments()
        cmd.type = doc_type
        try:
            resp = self.client.send(cmd, GetOpenDocumentsResponse)
        except Exception as e:
            raise RuntimeError(f"GetOpenDocuments failed: {e}") from e

        for doc in resp.documents:
            if getattr(doc, "type", None) == doc_type:
                self._doc = doc
                return doc

        if resp.documents:
            self._doc = resp.documents[0]
            return self._doc

        raise RuntimeError(
            f"No open document of type {doc_type} in KiCad. "
            "Open a project with the PCB editor and retry."
        )

    # -------------------------------------------------------------------------
    # Public read methods
    # -------------------------------------------------------------------------

    def get_board_info(self) -> Dict[str, Any]:
        """Return basic board metadata from GetOpenDocuments."""
        doc = self._get_document()
        proj = getattr(doc, "project", None)
        return {
            "board_filename": getattr(doc, "board_filename", ""),
            "project_name": getattr(proj, "name", "") if proj else "",
            "project_path": getattr(proj, "path", "") if proj else "",
        }

    def get_items(self, item_types: Optional[List[int]] = None) -> List[Any]:
        """GetItems for the given PCB item types (default: all PCB_ITEM_TYPES).

        Returns raw protobuf items (unpacked via GetItemsResponse.items).
        Caller must unpack each Any to the expected type.
        """
        if item_types is None:
            item_types = list(PCB_ITEM_TYPES)

        procs = get_editor_command_protos()
        GetItems = procs[4]
        GetItemsResponse = procs[5]
        doc = self._get_document()

        cmd = GetItems()
        cmd.header.document.CopyFrom(doc)
        cmd.types.extend(item_types)

        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except Exception as e:
            raise RuntimeError(f"GetItems failed: {e}") from e

        if resp.status != ItemRequestStatus.IRS_OK:
            raise RuntimeError(f"GetItems rejected (request status {resp.status})")

        return list(resp.items)

    def get_items_by_id(self, ids: List[str]) -> List[Any]:
        """GetItemsById for specific KIID strings."""
        procs = get_editor_command_protos()
        GetItemsById = procs[10]
        GetItemsResponse = procs[5]
        doc = self._get_document()

        cmd = GetItemsById()
        cmd.header.document.CopyFrom(doc)
        for value in ids:
            kiid = cmd.items.add()
            kiid.value = value

        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except Exception as e:
            raise RuntimeError(f"GetItemsById failed: {e}") from e

        if resp.status != ItemRequestStatus.IRS_OK:
            raise RuntimeError(f"GetItemsById rejected (request status {resp.status})")

        return list(resp.items)

    def get_copper_items(self) -> List[Any]:
        """GetItems for copper types only: trace, arc, via, zone, pad."""
        return self.get_items(list(PCB_COPPER_ITEM_TYPES))

    def get_footprints(self) -> List[Any]:
        """GetItems for footprints only."""
        procs = get_editor_command_protos()
        GetItems = procs[4]
        GetItemsResponse = procs[5]
        from .messages_pcb import KiCadObjectTypePCB
        doc = self._get_document()
        cmd = GetItems()
        cmd.header.document.CopyFrom(doc)
        cmd.types.append(KiCadObjectTypePCB.KOT_PCB_FOOTPRINT)
        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except Exception as e:
            raise RuntimeError(f"GetItems(footprints) failed: {e}") from e
        if resp.status != ItemRequestStatus.IRS_OK:
            raise RuntimeError(f"GetItems rejected: {resp.status}")
        return list(resp.items)

    def get_tracks(self) -> List[Any]:
        """GetItems for tracks + arcs."""
        procs = get_editor_command_protos()
        GetItems = procs[4]
        GetItemsResponse = procs[5]
        from .messages_pcb import KiCadObjectTypePCB
        doc = self._get_document()
        cmd = GetItems()
        cmd.header.document.CopyFrom(doc)
        cmd.types.extend([KiCadObjectTypePCB.KOT_PCB_TRACE, KiCadObjectTypePCB.KOT_PCB_ARC])
        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except Exception as e:
            raise RuntimeError(f"GetItems(tracks) failed: {e}") from e
        if resp.status != ItemRequestStatus.IRS_OK:
            raise RuntimeError(f"GetItems rejected: {resp.status}")
        return list(resp.items)

    def get_vias(self) -> List[Any]:
        """GetItems for vias."""
        procs = get_editor_command_protos()
        GetItems = procs[4]
        GetItemsResponse = procs[5]
        from .messages_pcb import KiCadObjectTypePCB
        doc = self._get_document()
        cmd = GetItems()
        cmd.header.document.CopyFrom(doc)
        cmd.types.append(KiCadObjectTypePCB.KOT_PCB_VIA)
        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except Exception as e:
            raise RuntimeError(f"GetItems(vias) failed: {e}") from e
        if resp.status != ItemRequestStatus.IRS_OK:
            raise RuntimeError(f"GetItems rejected: {resp.status}")
        return list(resp.items)

    def get_zones(self) -> List[Any]:
        """GetItems for zones."""
        procs = get_editor_command_protos()
        GetItems = procs[4]
        GetItemsResponse = procs[5]
        from .messages_pcb import KiCadObjectTypePCB
        doc = self._get_document()
        cmd = GetItems()
        cmd.header.document.CopyFrom(doc)
        cmd.types.append(KiCadObjectTypePCB.KOT_PCB_ZONE)
        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except Exception as e:
            raise RuntimeError(f"GetItems(zones) failed: {e}") from e
        if resp.status != ItemRequestStatus.IRS_OK:
            raise RuntimeError(f"GetItems rejected: {resp.status}")
        return list(resp.items)

    def get_pads(self) -> List[Any]:
        """GetItems for pads."""
        procs = get_editor_command_protos()
        GetItems = procs[4]
        GetItemsResponse = procs[5]
        from .messages_pcb import KiCadObjectTypePCB
        doc = self._get_document()
        cmd = GetItems()
        cmd.header.document.CopyFrom(doc)
        cmd.types.append(KiCadObjectTypePCB.KOT_PCB_PAD)
        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except Exception as e:
            raise RuntimeError(f"GetItems(pads) failed: {e}") from e
        if resp.status != ItemRequestStatus.IRS_OK:
            raise RuntimeError(f"GetItems rejected: {resp.status}")
        return list(resp.items)

    def get_nets(self) -> List[Dict[str, Any]]:
        """GetNets -> list of {name, code} dicts."""
        GetNets, NetsResponse = get_board_command_protos()[:2]
        doc = self._get_document()

        cmd = GetNets()
        cmd.board.CopyFrom(doc)

        try:
            resp = self.client.send(cmd, NetsResponse)
        except Exception as e:
            raise RuntimeError(f"GetNets failed: {e}") from e

        nets = []
        for net in resp.nets:
            code = net.code.value if net.code else 0
            nets.append({"name": net.name, "code": code})
        return nets

    def get_board_stackup(self) -> Dict[str, Any]:
        """GetBoardStackup -> simplified layer stackup info."""
        procs = get_board_command_protos()
        GetBoardStackup = procs[7]
        BoardStackupResponse = procs[8]
        doc = self._get_document()

        cmd = GetBoardStackup()
        cmd.board.CopyFrom(doc)

        try:
            resp = self.client.send(cmd, BoardStackupResponse)
        except Exception as e:
            raise RuntimeError(f"GetBoardStackup failed: {e}") from e

        stackup = resp.stackup
        layers = []
        for layer in stackup.layers:
            layers.append({
                "layer": layer.layer,
                "type": layer.type,
                "enabled": layer.enabled,
                "thickness_mm": layer.thickness.value_nm / 1_000_000.0 if layer.thickness else 0,
                "user_name": layer.user_name,
            })
        return {
            "finish": stackup.finish.type_name if stackup.finish else "",
            "copper_layer_count": len([l for l in layers if l["type"] == 1]),  # BSLT_COPPER
            "layers": layers,
        }

    def get_board_enabled_layers(self) -> Dict[str, Any]:
        """GetBoardEnabledLayers -> enabled layer list."""
        procs = get_board_command_protos()
        GetBoardEnabledLayers = procs[9]
        BoardEnabledLayersResponse = procs[10]
        doc = self._get_document()

        cmd = GetBoardEnabledLayers()
        cmd.board.CopyFrom(doc)

        try:
            resp = self.client.send(cmd, BoardEnabledLayersResponse)
        except Exception as e:
            raise RuntimeError(f"GetBoardEnabledLayers failed: {e}") from e

        return {
            "copper_layer_count": resp.copper_layer_count,
            "layers": list(resp.layers),
        }

    def get_graphics_defaults(self) -> Dict[str, Any]:
        """GetGraphicsDefaults -> line/text thickness per layer class."""
        procs = get_board_command_protos()
        GetGraphicsDefaults = procs[12]
        GraphicsDefaultsResponse = procs[13]
        doc = self._get_document()

        cmd = GetGraphicsDefaults()
        cmd.board.CopyFrom(doc)

        try:
            resp = self.client.send(cmd, GraphicsDefaultsResponse)
        except Exception as e:
            raise RuntimeError(f"GetGraphicsDefaults failed: {e}") from e

        defaults = []
        for layer_default in resp.defaults.layers:
            defaults.append({
                "layer_class": layer_default.layer,
                "line_thickness_mm": layer_default.line_thickness.value_nm / 1_000_000.0,
                "text_size_mm": (
                    layer_default.text.size.x_nm / 1_000_000.0,
                    layer_default.text.size.y_nm / 1_000_000.0,
                ),
                "text_thickness_mm": layer_default.text.stroke_width.value_nm / 1_000_000.0,
                "italic": layer_default.text.italic,
                "keep_upright": layer_default.text.keep_upright,
            })
        return {"layers": defaults}

    def get_board_origin(self, origin_type: int = 1) -> Dict[str, float]:
        """GetBoardOrigin -> {x_mm, y_mm} for grid (1) or drill (2) origin."""
        procs = get_board_command_protos()
        GetBoardOrigin = procs[14]
        doc = self._get_document()

        cmd = GetBoardOrigin()
        cmd.board.CopyFrom(doc)
        cmd.type = origin_type

        try:
            resp = self.client.send(cmd, get_base_type_protos()[1])  # Vector2
        except Exception as e:
            raise RuntimeError(f"GetBoardOrigin failed: {e}") from e

        return {"x_mm": resp.x_nm / 1_000_000.0, "y_mm": resp.y_nm / 1_000_000.0}

    def get_board_layer_name(self, layer: int) -> str:
        """GetBoardLayerName -> user-visible layer name."""
        procs = get_board_command_protos()
        GetBoardLayerName = procs[16]
        BoardLayerNameResponse = procs[17]
        doc = self._get_document()

        cmd = GetBoardLayerName()
        cmd.board.CopyFrom(doc)
        cmd.layer = layer

        try:
            resp = self.client.send(cmd, BoardLayerNameResponse)
        except Exception as e:
            raise RuntimeError(f"GetBoardLayerName failed: {e}") from e

        return resp.name

    def get_items_by_net(
        self,
        net_names: List[str],
        item_types: Optional[List[int]] = None,
    ) -> List[Any]:
        """GetItemsByNet -> items on the given nets (Group A, needs 10.0.1+).

        Accepts net *names* and resolves them through get_nets first, because
        running boards may not know their numeric codes ahead of time.  Pass
        item_types (KiCadObjectType ids) to narrow the read, e.g. only traces.
        Returns raw unpacked protobuf items (unpacked via GetItemsResponse.items).
        """
        GetItemsByNet = get_board_command("GetItemsByNet")
        nets = {n["name"]: n["code"] for n in self.get_nets()}
        doc = self._get_document()

        cmd = GetItemsByNet()
        cmd.header.document.CopyFrom(doc)
        if item_types is not None:
            cmd.types.extend(item_types)
        for name in net_names:
            if name not in nets:
                raise RuntimeError(
                    f"Net '{name}' not found on board "
                    f"(known: {sorted(nets)[:10]}{'...' if len(nets) > 10 else ''})."
                )
            net = cmd.nets.add()
            net.name = name
            net.code.value = nets[name]

        try:
            GetItemsResponse = get_editor_command("GetItemsResponse")
            resp = self.client.send(cmd, GetItemsResponse)
        except Exception as e:
            raise RuntimeError(f"GetItemsByNet failed: {e}") from e

        if resp.status != ItemRequestStatus.IRS_OK:
            raise RuntimeError(f"GetItemsByNet rejected: {resp.status}")
        return list(resp.items)

    def get_connected_items(
        self,
        ids: List[str],
        item_types: Optional[List[int]] = None,
    ) -> List[Any]:
        """GetConnectedItems -> items copper-connected to the given KIIDs (Group A).

        Returns raw unpacked protobuf items (unpacked via GetItemsResponse.items).
        """
        GetConnectedItems = get_board_command("GetConnectedItems")
        GetItemsResponse = get_editor_command("GetItemsResponse")
        doc = self._get_document()

        cmd = GetConnectedItems()
        cmd.header.document.CopyFrom(doc)
        for value in ids:
            kiid = cmd.items.add()
            kiid.value = value
        if item_types is not None:
            cmd.types.extend(item_types)

        try:
            resp = self.client.send(cmd, GetItemsResponse)
        except Exception as e:
            raise RuntimeError(f"GetConnectedItems failed: {e}") from e

        if resp.status != ItemRequestStatus.IRS_OK:
            raise RuntimeError(f"GetConnectedItems rejected: {resp.status}")
        return list(resp.items)

    def get_visible_layers(self) -> List[int]:
        """GetVisibleLayers -> editor-visible BoardLayer ids (Group A)."""
        GetVisibleLayers = get_board_command("GetVisibleLayers")
        BoardLayers = get_board_command("BoardLayers")
        doc = self._get_document()

        cmd = GetVisibleLayers()
        cmd.board.CopyFrom(doc)

        try:
            resp = self.client.send(cmd, BoardLayers)
        except Exception as e:
            raise RuntimeError(f"GetVisibleLayers failed: {e}") from e

        return list(resp.layers)

    def get_active_layer(self) -> int:
        """GetActiveLayer -> the layer the editor is currently drawing on (Group A)."""
        GetActiveLayer = get_board_command("GetActiveLayer")
        BoardLayerResponse = get_board_command("BoardLayerResponse")
        doc = self._get_document()

        cmd = GetActiveLayer()
        cmd.board.CopyFrom(doc)

        try:
            resp = self.client.send(cmd, BoardLayerResponse)
        except Exception as e:
            raise RuntimeError(f"GetActiveLayer failed: {e}") from e

        return resp.layer

    def save_document_to_string(self) -> str:
        """SaveDocumentToString -> full board as S-expression text (read-only)."""
        procs = get_editor_command_protos()
        SaveDocumentToString = procs[20]
        SavedDocumentResponse = procs[21]
        doc = self._get_document()

        cmd = SaveDocumentToString()
        cmd.document.CopyFrom(doc)

        try:
            resp = self.client.send(cmd, SavedDocumentResponse)
        except Exception as e:
            raise RuntimeError(f"SaveDocumentToString failed: {e}") from e

        contents = getattr(resp, "contents", "") or ""
        if not contents.strip():
            raise RuntimeError("Live board text came back empty.")
        return contents

    # -------------------------------------------------------------------------
    # Convenience: full snapshot
    # -------------------------------------------------------------------------

    def get_full_snapshot(self) -> Dict[str, Any]:
        """Return a combined snapshot dict (reads all above)."""
        snapshot = {
            "board_info": self.get_board_info(),
            "nets": self.get_nets(),
            "stackup": self.get_board_stackup(),
            "enabled_layers": self.get_board_enabled_layers(),
            "graphics_defaults": self.get_graphics_defaults(),
            "origin_grid": self.get_board_origin(1),
            "origin_drill": self.get_board_origin(2),
        }

        # Items - unpack from Any to expected types
        from .types_pcb import (
            track_to_dict, arc_to_dict, via_to_dict,
            zone_to_dict, footprint_instance_to_dict, pad_to_dict,
        )
        from .messages_pcb import get_board_type

        Track = get_board_type("Track")
        Arc = get_board_type("Arc")
        Via = get_board_type("Via")
        Pad = get_board_type("Pad")
        Zone = get_board_type("Zone")
        FootprintInstance = get_board_type("FootprintInstance")

        footprints = []
        tracks = []
        arcs = []
        vias = []
        zones = []
        pads = []

        for any_msg in self.get_items():
            type_url = any_msg.TypeName() if hasattr(any_msg, "TypeName") else ""
            short = type_url.rsplit(".", 1)[-1].rsplit("/", 1)[-1]

            if short == "FootprintInstance":
                fp = FootprintInstance()
                if any_msg.Unpack(fp):
                    footprints.append(footprint_instance_to_dict(fp))
            elif short == "Track":
                tr = Track()
                if any_msg.Unpack(tr):
                    tracks.append(track_to_dict(tr))
            elif short == "Arc":
                ar = Arc()
                if any_msg.Unpack(ar):
                    arcs.append(arc_to_dict(ar))
            elif short == "Via":
                vi = Via()
                if any_msg.Unpack(vi):
                    vias.append(via_to_dict(vi))
            elif short == "Zone":
                zn = Zone()
                if any_msg.Unpack(zn):
                    zones.append(zone_to_dict(zn))
            elif short == "Pad":
                pd = Pad()
                if any_msg.Unpack(pd):
                    pads.append(pad_to_dict(pd))

        snapshot["footprints"] = footprints
        snapshot["tracks"] = tracks
        snapshot["arcs"] = arcs
        snapshot["vias"] = vias
        snapshot["zones"] = zones
        snapshot["pads"] = pads
        snapshot["counts"] = {
            "footprints": len(footprints),
            "tracks": len(tracks),
            "arcs": len(arcs),
            "vias": len(vias),
            "zones": len(zones),
            "pads": len(pads),
            "nets": len(snapshot["nets"]),
        }

        return snapshot


def get_pcb_snapshot(client: KiCadIPCClient) -> Dict[str, Any]:
    """Convenience function: connect, read full snapshot, disconnect."""
    reader = PCBSnapshotReader(client)
    return reader.get_full_snapshot()