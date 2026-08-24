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

        # Ensure symbol definition is cached in the schematic file if available
        if doc_proto.project.path and doc_proto.board_filename:
            sch_file = os.path.join(doc_proto.project.path, doc_proto.board_filename)
            if os.path.exists(sch_file):
                try:
                    from .cache_helper import extract_symbol_definition, inject_lib_symbols_into_schematic
                    sym_lib_path = f"C:\\Program Files\\KiCad\\10.0\\share\\kicad\\symbols\\{lib_nickname}.kicad_sym"
                    if os.path.exists(sym_lib_path):
                        sym_def = extract_symbol_definition(sym_lib_path, entry_name)
                        inject_lib_symbols_into_schematic(sch_file, {lib_id: sym_def})
                except Exception:
                    pass

        # Import protobuf classes
        (SchematicSymbolInstance,) = get_schematic_type_protos()
        CreateItems, CreateItemsResponse, _, _ = get_editor_command_protos()

        # 1. Build the SchematicSymbolInstance protobuf message
        sym_proto = SchematicSymbolInstance()
        sym_proto.id.value = generated_uuid
        sym_proto.position.x_nm = pos_x_nm
        sym_proto.position.y_nm = pos_y_nm

        # Copy hierarchical sheet path from the schematic
        doc_proto = self.schematic.document_proto
        sheet_path = self.schematic.sheet_path
        if sheet_path is not None:
            sym_proto.path.CopyFrom(sheet_path)
            doc_proto.sheet_path.CopyFrom(sheet_path)
        elif hasattr(doc_proto, "sheet_path") and doc_proto.sheet_path.path:
            sym_proto.path.CopyFrom(doc_proto.sheet_path)

        # Definition reference (library ID) and unit count
        sym_proto.definition.id.library_nickname = lib_nickname
        sym_proto.definition.id.entry_name = entry_name
        sym_proto.definition.unit_count = 1

        # Default orientation (SSO_0 = 1)
        sym_proto.transform.orientation = 1

        # Instance fields: Reference and Value
        sym_proto.reference_field.name = "Reference"
        sym_proto.reference_field.text.text = reference
        sym_proto.reference_field.visible = True

        sym_proto.value_field.name = "Value"
        sym_proto.value_field.text.text = value
        sym_proto.value_field.visible = True

        sym_proto.unit.unit = unit

        # Definition fields
        sym_proto.definition.reference_field.name = "Reference"
        sym_proto.definition.reference_field.text.text = reference
        sym_proto.definition.reference_field.visible = True

        sym_proto.definition.value_field.name = "Value"
        sym_proto.definition.value_field.text.text = value
        sym_proto.definition.value_field.visible = True

        # 2. Pack into google.protobuf.Any
        any_item = Any()
        any_item.Pack(sym_proto)

        # 3. Build CreateItems command with document header
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
