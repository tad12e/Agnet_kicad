"""KiCad Schematic API Adapter.

Provides high-level programmatic access to the Eeschema schematic canvas
through KiCad's IPC API.

This is the main entry point for schematic operations:
    sch = SchematicAPI(client=client)
    sch.components.add(...)
    sch.wires.add(...)       # FUTURE
    sch.junctions.add(...)   # FUTURE
"""

from __future__ import annotations

from typing import Optional

from ..ipc.client import KiCadIPCClient
from ..ipc.messages import get_editor_command_protos, get_base_type_protos, DocumentType
from .components import ComponentManager


class SchematicAPI:
    """High-level Schematic API interface.

    Provides sub-managers for different schematic operations:
    - components: Add, get, list symbol instances
    - wires: Connect pins with wires (FUTURE)
    - junctions: Place junction dots (FUTURE)
    - power: Place power symbols (FUTURE)
    - nets: Inspect connectivity (FUTURE)
    """

    def __init__(
        self,
        client: Optional[KiCadIPCClient] = None,
        document_proto: Optional[object] = None,
    ):
        self.client = client or KiCadIPCClient()
        self._document_proto = document_proto
        self.components = ComponentManager(self)

    @property
    def document_proto(self):
        """Return the DocumentSpecifier protobuf for this schematic.

        Queries KiCad for open schematic documents on first access.

        C++ context:
            KiCad's API_HANDLER_EDITOR::handleGetOpenDocuments() iterates
            through open documents and returns DocumentSpecifier messages.
            Each DocumentSpecifier has:
            - DocumentType type  (DOCTYPE_SCHEMATIC, DOCTYPE_PCB, etc.)
            - KIID board_id      (unique identifier for the document)

            The CreateItems command requires a DocumentSpecifier in its
            header to know which document to modify.
        """
        if self._document_proto is not None:
            return self._document_proto

        # Import protos
        _, _, GetOpenDocuments, GetOpenDocumentsResponse = get_editor_command_protos()
        _, _, _, DocumentSpecifier = get_base_type_protos()

        # Query open schematic documents from KiCad
        cmd = GetOpenDocuments()
        cmd.type = DocumentType.DOCTYPE_SCHEMATIC
        resp = self.client.send(cmd, GetOpenDocumentsResponse)

        if not resp.documents:
            # Fallback placeholder if querying headless/unnamed
            doc = DocumentSpecifier()
            doc.type = DocumentType.DOCTYPE_SCHEMATIC
            self._document_proto = doc
            return self._document_proto

        self._document_proto = resp.documents[0]
        return self._document_proto
