"""Wire management for KiCad schematic — FUTURE STUB.

Will implement:
    sch.wires.add(start=(x1, y1), end=(x2, y2))
    sch.wires.connect(pin1, pin2)

Using KiCad IPC: CreateItems with SchematicLine (SLT_WIRE type).

C++ path:
    WireManager.add() → CreateItems(SchematicLine) → IPC →
    API_HANDLER_SCH → CreateItemForType(SCH_LINE_T) →
    SCH_LINE(SLT_WIRE) → SCH_COMMIT → SCH_SCREEN
"""
