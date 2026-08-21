"""Net/connectivity inspection for KiCad schematic — FUTURE STUB.

Will implement:
    nets = sch.nets.list()
    net_info = sch.nets.get("GND")
    connections = sch.nets.get_connections(component_ref="R1")

Using KiCad IPC: GetSchematicNetlist command.

C++ path:
    NetManager.list() → GetSchematicNetlist → IPC →
    API_HANDLER_SCH::handleGetSchematicNetlist() →
    CONNECTION_GRAPH → SchematicNetlistResponse
"""
