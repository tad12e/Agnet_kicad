"""Junction management for KiCad schematic — FUTURE STUB.

Will implement:
    sch.junctions.add(position=(x, y))

Using KiCad IPC: CreateItems with Junction protobuf message.

C++ path:
    JunctionManager.add() → CreateItems(Junction) → IPC →
    API_HANDLER_SCH → CreateItemForType(SCH_JUNCTION_T) →
    SCH_JUNCTION → SCH_COMMIT → SCH_SCREEN
"""
