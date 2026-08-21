"""Unit tests for kicad_api.ipc messages and serialization."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kicad_api.ipc.messages import (
    get_envelope_protos,
    get_editor_command_protos,
    get_base_type_protos,
    get_schematic_type_protos,
    ApiStatusCode,
    DocumentType,
    ItemStatusCode,
)
from kicad_api.ipc.connection import default_socket_path, generate_client_name
from kicad_api.ipc.exceptions import IPCConnectionError, IPCRequestError


def test_socket_discovery():
    sock = default_socket_path()
    assert "api.sock" in sock
    name = generate_client_name("test")
    assert name.startswith("test-")


def test_protobuf_envelope_roundtrip():
    ApiRequest, ApiResponse = get_envelope_protos()
    CreateItems, _, _, _ = get_editor_command_protos()
    (SchematicSymbolInstance,) = get_schematic_type_protos()

    sym = SchematicSymbolInstance()
    sym.id.value = "test-uuid"
    sym.position.x_nm = 100_000_000
    sym.position.y_nm = 200_000_000
    sym.definition.id.library_nickname = "Device"
    sym.definition.id.entry_name = "R"
    sym.reference_field.text.text = "R1"
    sym.value_field.text.text = "10k"

    req = ApiRequest()
    req.header.client_name = "pytest-runner"
    req.message.Pack(sym)

    payload = req.SerializeToString()
    assert len(payload) > 0

    req_unpacked = ApiRequest()
    req_unpacked.ParseFromString(payload)
    assert req_unpacked.header.client_name == "pytest-runner"

    sym_unpacked = SchematicSymbolInstance()
    assert req_unpacked.message.Unpack(sym_unpacked)
    assert sym_unpacked.id.value == "test-uuid"
    assert sym_unpacked.position.x_nm == 100_000_000
    assert sym_unpacked.position.y_nm == 200_000_000
    assert sym_unpacked.reference_field.text.text == "R1"
    assert sym_unpacked.value_field.text.text == "10k"


def test_ipc_exceptions():
    err = IPCRequestError(status_code=ApiStatusCode.AS_BAD_REQUEST, error_message="Invalid item")
    assert err.status_code == ApiStatusCode.AS_BAD_REQUEST
    assert "Invalid item" in str(err)
