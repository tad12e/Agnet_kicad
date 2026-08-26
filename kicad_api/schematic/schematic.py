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

import os
from typing import Optional

from ..ipc.client import KiCadIPCClient
from ..ipc.messages import get_editor_command_protos, get_base_type_protos, DocumentType
from .components import ComponentManager
from .wires import WireManager


class SchematicAPI:
    """High-level Schematic API interface.

    Provides sub-managers for different schematic operations:
    - components: Add, get, list symbol instances
    - wires: Connect pins with wires
    - junctions: Place junction dots
    - power: Place power symbols
    - nets: Inspect connectivity
    """

    def __init__(
        self,
        client: Optional[KiCadIPCClient] = None,
        document_proto: Optional[object] = None,
        timeout_ms: Optional[int] = None,
        filepath: Optional[str] = None,
    ):
        if client is not None:
            self.client = client
            if timeout_ms is not None:
                self.client.set_timeout(timeout_ms)
        else:
            self.client = KiCadIPCClient(timeout_ms=timeout_ms)
        self.filepath = filepath
        self._document_proto = document_proto
        self.components = ComponentManager(self)
        self.wires = WireManager(self)

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
        try:
            cmd = GetOpenDocuments()
            cmd.type = DocumentType.DOCTYPE_SCHEMATIC
            resp = self.client.send(cmd, GetOpenDocumentsResponse)
            if resp.documents:
                doc = resp.documents[0]
                if not doc.project.name and doc.board_filename:
                    base_name = os.path.splitext(os.path.basename(doc.board_filename))[0]
                    doc.project.name = base_name
                self._document_proto = doc
                return self._document_proto
        except Exception:
            pass

        # Fallback placeholder if querying headless/unnamed or if schematic window is opening
        doc = DocumentSpecifier()
        doc.type = DocumentType.DOCTYPE_SCHEMATIC
        if self.filepath:
            doc.board_filename = os.path.basename(self.filepath)
            base_name = os.path.splitext(doc.board_filename)[0]
            doc.project.name = base_name
        self._document_proto = doc
        return self._document_proto

    @property
    def sheet_path(self):
        """Return the SheetPath for the active root sheet in this schematic."""
        if hasattr(self, "_sheet_path") and self._sheet_path is not None:
            return self._sheet_path

        doc = self.document_proto
        if doc.HasField("sheet_path") and doc.sheet_path.path:
            self._sheet_path = doc.sheet_path
            return self._sheet_path

        # Try extracting root sheet UUID from local .kicad_sch file
        try:
            import re
            candidate_dirs = [
                r"C:\Users\hp\ECE\test\Agent",
                os.getcwd(),
            ]
            for cdir in candidate_dirs:
                sch_file = os.path.join(cdir, doc.board_filename or "Agent.kicad_sch")
                if os.path.exists(sch_file):
                    with open(sch_file, "r", encoding="utf-8", errors="ignore") as f:
                        m = re.search(r'\(uuid\s+"?([0-9a-fA-F\-]{36})"?\)', f.read(4096))
                        if m:
                            _, _, _, SheetPath = get_base_type_protos()
                            sp = SheetPath()
                            sp.path.add().value = m.group(1)
                            self._sheet_path = sp
                            return self._sheet_path
        except Exception:
            pass

        return None

