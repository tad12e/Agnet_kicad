"""Component Management for KiCad Schematic.

Handles adding, retrieving, and manipulating symbols/components
in an Eeschema schematic via the official KiCad IPC API.

The complete execution path for adding a component:

    Python: ComponentManager.add(lib_id="Device:R", ...)
        ↓
    Build SchematicSymbolInstance protobuf message
        ↓
    Pack into CreateItems command
        ↓
    KiCadIPCClient.send() → NNG socket → KiCad
        ↓
    C++ API_HANDLER_EDITOR::handleCreateItems()
        ↓
    C++ handleCreateUpdateItemsInternal()
        ↓
    C++ CreateItemForType(SCH_SYMBOL_T, targetScreen)
        → std::make_unique<SCH_SYMBOL>()
        ↓
    C++ UnpackSymbol() — deserializes protobuf into SCH_SYMBOL fields
        ↓
    C++ commit->Add(createdItem, targetScreen)
        ↓
    C++ pushCurrentCommit("Created items via API")
        → SCH_COMMIT::Push()
        → SCH_SCREEN::Items().push_back()
        → undo/redo stack updated
        → connectivity notified
        ↓
    Response sent back with created item data
        ↓
    Python: Unpack response → Component model
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, Optional, Tuple

from google.protobuf.any_pb2 import Any

from ..models.component import Component
from ..geometry.point import mm_to_nm, nm_to_mm
from ..ipc.messages import (
    get_schematic_type_protos,
    get_editor_command_protos,
    get_base_type_protos,
    ItemStatusCode,
)

if TYPE_CHECKING:
    from .schematic import SchematicAPI


class ComponentManager:
    """Manager for schematic components/symbols.

    Acts as the high-level adapter between user/AI commands and
    KiCad's IPC protocol for symbol placement.
    """

    def __init__(self, schematic: SchematicAPI):
        self.schematic = schematic
        self.client = schematic.client

    def add(
        self,
        lib_id: str,
        reference: str,
        value: str,
        position: Tuple[float, float],
        unit: int = 1,
        rotation: float = 0,
        item_id: Optional[str] = None,
    ) -> Component:
        """Add a component/symbol to the schematic.

        Args:
            lib_id: Symbol library identifier, e.g., "Device:R" or "Timer:NE555".
            reference: Reference designator, e.g., "R1", "C1", "U1".
            value: Component value string, e.g., "10k", "100nF", "NE555".
            position: (X, Y) coordinates in millimeters.
            unit: Symbol unit number (default 1). Multi-unit symbols like
                  op-amps use units 1, 2, 3, etc.
            item_id: Optional specific UUID. If omitted, one is generated.

        Returns:
            Created Component object with KiCad-assigned data.

        Raises:
            RuntimeError: If KiCad rejects the creation request.
            ImportError: If kipy protobuf package is not installed.
        """
        # Parse lib_id into library nickname and entry name
        if ":" in lib_id:
            lib_nickname, entry_name = lib_id.split(":", 1)
        else:
            lib_nickname = ""
            entry_name = lib_id

        # Convert position from mm to nm (KiCad internal units)
        pos_x_nm = mm_to_nm(position[0])
        pos_y_nm = mm_to_nm(position[1])
        generated_uuid = item_id or str(uuid.uuid4())

        doc_proto = self.schematic.document_proto

        # Resolve local schematic file path on disk
        sch_filepath = None
        candidate_paths = [
            getattr(self.schematic, "filepath", None),
            doc_proto.board_filename,
            os.path.join(r"C:\Users\hp\ECE\test\Agent", doc_proto.board_filename or "Agent.kicad_sch"),
            os.path.join(os.getcwd(), doc_proto.board_filename or "Agent.kicad_sch"),
        ]
        for p in candidate_paths:
            if p and os.path.exists(p):
                sch_filepath = os.path.abspath(p)
                break

        # In KiCad 10.x, live IPC CreateItems for symbols has an unhandled C++ nullptr bug.
        # Use Microsoft SchGen S-expression engine when on disk for KiCad 10.
        # KiCad 11+ uses live IPC CreateItems directly.
        use_sexpr = sch_filepath is not None

        if use_sexpr:
            from .sexpr import add_symbol_to_schematic
            sym_uuid = add_symbol_to_schematic(
                sch_path=sch_filepath,
                lib_name=lib_nickname,
                symbol_name=entry_name,
                reference=reference,
                value=value,
                pos_x_mm=position[0],
                pos_y_mm=position[1],
                rotation=rotation,
            )
            return Component(
                id=sym_uuid,
                lib_id=lib_id,
                reference=reference,
                value=value,
                position_mm=position,
                unit=unit,
            )

        # Import protobuf classes for live IPC (KiCad 11+)
        (SchematicSymbolInstance,) = get_schematic_type_protos()
        CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()

        # 1. Build the SchematicSymbolInstance protobuf message
        sym_proto = SchematicSymbolInstance()
        sym_proto.id.value = generated_uuid
        sym_proto.position.x_nm = pos_x_nm
        sym_proto.position.y_nm = pos_y_nm

        # Copy hierarchical sheet path to symbol instance (without mutating document_proto)
        sheet_path = self.schematic.sheet_path
        if sheet_path is not None:
            sym_proto.path.CopyFrom(sheet_path)
        elif doc_proto.HasField("sheet_path") and doc_proto.sheet_path.path:
            sym_proto.path.CopyFrom(doc_proto.sheet_path)

        # Definition reference (library ID) and unit count
        sym_proto.definition.id.library_nickname = lib_nickname
        sym_proto.definition.id.entry_name = entry_name
        sym_proto.definition.unit_count = 1
        sym_proto.definition.body_style_count = 1

        # Default orientation (SSO_0 = 1)
        sym_proto.transform.orientation = 1
        sym_proto.unit.unit = unit

        # Definition Mandatory Fields
        sym_proto.definition.reference_field.name = "Reference"
        sym_proto.definition.reference_field.text.text = reference
        sym_proto.definition.reference_field.text.position.x_nm = 0
        sym_proto.definition.reference_field.text.position.y_nm = -2_540_000
        sym_proto.definition.reference_field.visible = True

        sym_proto.definition.value_field.name = "Value"
        sym_proto.definition.value_field.text.text = value
        sym_proto.definition.value_field.text.position.x_nm = 0
        sym_proto.definition.value_field.text.position.y_nm = 2_540_000
        sym_proto.definition.value_field.visible = True

        sym_proto.definition.footprint_field.name = "Footprint"
        sym_proto.definition.footprint_field.text.text = ""
        sym_proto.definition.footprint_field.visible = False

        sym_proto.definition.datasheet_field.name = "Datasheet"
        sym_proto.definition.datasheet_field.text.text = "~"
        sym_proto.definition.datasheet_field.visible = False

        sym_proto.definition.description_field.name = "Description"
        sym_proto.definition.description_field.text.text = ""
        sym_proto.definition.description_field.visible = False

        # Instance Mandatory Fields
        sym_proto.reference_field.name = "Reference"
        sym_proto.reference_field.text.text = reference
        sym_proto.reference_field.text.position.x_nm = pos_x_nm
        sym_proto.reference_field.text.position.y_nm = pos_y_nm - 2_540_000
        sym_proto.reference_field.visible = True

        sym_proto.value_field.name = "Value"
        sym_proto.value_field.text.text = value
        sym_proto.value_field.text.position.x_nm = pos_x_nm
        sym_proto.value_field.text.position.y_nm = pos_y_nm + 2_540_000
        sym_proto.value_field.visible = True

        sym_proto.footprint_field.name = "Footprint"
        sym_proto.footprint_field.text.text = ""
        sym_proto.footprint_field.visible = False

        sym_proto.datasheet_field.name = "Datasheet"
        sym_proto.datasheet_field.text.text = "~"
        sym_proto.datasheet_field.visible = False

        sym_proto.description_field.name = "Description"
        sym_proto.description_field.text.text = ""
        sym_proto.description_field.visible = False

        # Add pins to definition.items so KiCad C++ LIB_SYMBOL has pin objects
        try:
            from proto.schematic.schematic_types_pb2 import (
                SchematicPin,
                SchematicPinOrientation,
                SchematicPinShape,
            )
            from proto.common.types.base_types_pb2 import ElectricalPinType

            # Pin 1
            pin1 = SchematicPin()
            pin1.id.value = str(uuid.uuid4())
            pin1.name = "~"
            pin1.number = "1"
            pin1.position.x_nm = 0
            pin1.position.y_nm = -2_540_000
            pin1.length.value_nm = 2_540_000
            pin1.orientation = SchematicPinOrientation.SPO_DOWN
            pin1.electrical_type = ElectricalPinType.EPT_PASSIVE
            pin1.shape = SchematicPinShape.SPS_LINE
            pin1.visible = True

            any_p1 = Any()
            any_p1.Pack(pin1)
            c1 = sym_proto.definition.items.add()
            c1.item.CopyFrom(any_p1)
            c1.unit.unit = unit
            c1.body_style.style = 1

            # Pin 2
            pin2 = SchematicPin()
            pin2.id.value = str(uuid.uuid4())
            pin2.name = "~"
            pin2.number = "2"
            pin2.position.x_nm = 0
            pin2.position.y_nm = 2_540_000
            pin2.length.value_nm = 2_540_000
            pin2.orientation = SchematicPinOrientation.SPO_UP
            pin2.electrical_type = ElectricalPinType.EPT_PASSIVE
            pin2.shape = SchematicPinShape.SPS_LINE
            pin2.visible = True

            any_p2 = Any()
            any_p2.Pack(pin2)
            c2 = sym_proto.definition.items.add()
            c2.item.CopyFrom(any_p2)
            c2.unit.unit = unit
            c2.body_style.style = 1
        except Exception:
            pass

        # 2. Pack into google.protobuf.Any
        any_item = Any()
        any_item.Pack(sym_proto)

        # 3. Build CreateItems command with intact document header
        cmd = CreateItems()
        cmd.header.document.CopyFrom(doc_proto)
        cmd.items.append(any_item)

        # 4. Send over IPC
        response: CreateItemsResponse = self.client.send(cmd, CreateItemsResponse)

        # 5. Verify response
        if not response.created_items:
            raise RuntimeError("KiCad did not return any created items.")

        first_result = response.created_items[0]
        status_code = first_result.status.code

        if status_code not in (ItemStatusCode.ISC_OK, ItemStatusCode.ISC_UNKNOWN):
            raise RuntimeError(
                f"KiCad failed to create {reference}: "
                f"{first_result.status.error_message}"
            )

        # 6. Unpack returned symbol
        created_proto = SchematicSymbolInstance()
        if first_result.item.Unpack(created_proto):
            return Component(
                id=created_proto.id.value,
                lib_id=lib_id,
                reference=created_proto.reference_field.text.text or reference,
                value=created_proto.value_field.text.text or value,
                position_mm=(
                    nm_to_mm(created_proto.position.x_nm),
                    nm_to_mm(created_proto.position.y_nm),
                ),
                unit=created_proto.unit.unit if created_proto.HasField("unit") else unit,
                raw_proto=created_proto,
            )

        # Fallback if unpack fails — return what we sent
        return Component(
            id=generated_uuid,
            lib_id=lib_id,
            reference=reference,
            value=value,
            position_mm=position,
            unit=unit,
            raw_proto=sym_proto,
        )
