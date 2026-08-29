"""Unit tests for IPC message handling and protobuf serialization."""

from kicad_agent.ipc.connection import default_socket_path, generate_client_name
from kicad_agent.ipc.exceptions import IPCRequestError
from kicad_agent.ipc.messages import (
    ApiStatusCode,
    DocumentType,
    get_base_type_protos,
    get_editor_command_protos,
    get_envelope_protos,
    get_schematic_type_protos,
)


def test_socket_discovery():
    sock = default_socket_path()
    assert "api.sock" in sock
    name = generate_client_name("test")
    assert name.startswith("test-")


def test_protobuf_envelope_roundtrip():
    ApiRequest, ApiResponse = get_envelope_protos()
    (SchematicSymbolInstance,) = get_schematic_type_protos()

    sym = SchematicSymbolInstance()
    sym.id.value = "test-uuid"
    sym.position.x_nm = 100_000_000
    sym.position.y_nm = 200_000_000
    sym.definition.id.library_nickname = "Device"
    sym.definition.id.entry_name = "R"

    req = ApiRequest()
    req.header.client_name = "pytest-runner"
    req.message.Pack(sym)

    payload = req.SerializeToString()
    assert len(payload) > 0

    req_unpacked = ApiRequest()
    req_unpacked.ParseFromString(payload)
    assert req_unpacked.header.client_name == "pytest-runner"


def test_ipc_exceptions():
    err = IPCRequestError(status_code=ApiStatusCode.AS_BAD_REQUEST, error_message="Invalid item")
    assert err.status_code == ApiStatusCode.AS_BAD_REQUEST
    assert "Invalid item" in str(err)
