"""KiCad IPC Client.

Low-level transport client that communicates with KiCad's KICAD_API_SERVER
over Nanomsg Next Gen (NNG) sockets using Protocol Buffer envelopes.

Architecture context (C++ side):
    KiCad's api_server.cpp creates an NNG Rep0 socket (KINNG_REQUEST_SERVER).
    Our client creates an NNG Req0 socket and dials the same address.
    Each request is a serialized `ApiRequest` protobuf (from envelope.proto),
    and each response is a serialized `ApiResponse` protobuf.

    The ApiRequest wraps any command (e.g., CreateItems, GetOpenDocuments)
    inside a google.protobuf.Any field.

C++ concepts for the learner:
    In KiCad's api_server.cpp, the handler signature is:
        API_RESULT KICAD_API_SERVER::handleApiRequestString(const std::string& aRequestString)
    - API_RESULT is a typedef for std::optional<ApiResponse>
    - const std::string& means "a reference to a string that won't be modified"
    - The server deserializes the bytes into ApiRequest, routes to the
      appropriate handler, and returns ApiResponse.
"""

from __future__ import annotations

import os
from typing import Optional, Type, TypeVar

try:
    import pynng
except ImportError:
    pynng = None  # type: ignore[assignment]

try:
    from google.protobuf.message import Message
    from google.protobuf.any_pb2 import Any
except ImportError:
    Message = object  # type: ignore[misc,assignment]
    Any = None  # type: ignore[assignment]

from .connection import default_socket_path, generate_client_name
from .exceptions import (
    IPCConnectionError,
    IPCTimeoutError,
    IPCRequestError,
    IPCUnpackError,
)
from .messages import ApiStatusCode

R = TypeVar("R", bound=Message)


class KiCadIPCClient:
    """Low-level IPC client for KiCad's API server.

    Wraps the NNG Req0 socket and protobuf envelope serialization.

    Usage:
        client = KiCadIPCClient()
        client.connect()
        response = client.send(some_protobuf_command, ExpectedResponseType)
        client.close()
    """

    def __init__(
        self,
        socket_path: Optional[str] = None,
        client_name: Optional[str] = None,
        kicad_token: Optional[str] = None,
        timeout_ms: int = 5000,
    ):
        self.socket_path = socket_path or default_socket_path()
        self.client_name = client_name or generate_client_name()
        self.kicad_token = kicad_token or os.environ.get("KICAD_API_TOKEN", "")
        self.timeout_ms = timeout_ms
        self._conn: Optional[pynng.Req0] = None  # type: ignore[name-defined]
        self._connected = False

    def connect(self) -> None:
        """Establish the NNG Req0 socket connection to KiCad.

        C++ context:
            On the KiCad side, KICAD_API_SERVER::Start() (api_server.cpp)
            creates an nng_listener on the same socket path. Our Req0 socket
            dials that address. The NNG protocol handles the handshake.
        """
        if pynng is None:
            raise IPCConnectionError(
                "pynng package is required for KiCad IPC communication. "
                "Install with: pip install pynng"
            )

        if self._connected and self._conn:
            self._conn.close()

        try:
            self._conn = pynng.Req0(
                dial=self.socket_path,
                block_on_dial=True,
                send_timeout=self.timeout_ms,
                recv_timeout=self.timeout_ms,
            )
            self._connected = True
        except Exception as e:
            self._connected = False
            raise IPCConnectionError(
                f"Failed to connect to KiCad IPC server at {self.socket_path}. "
                f"Make sure KiCad is running with the API server enabled "
                f"(Preferences → Plugins). Error: {e}"
            ) from e

    def close(self) -> None:
        """Close the socket connection."""
        if self._connected and self._conn:
            self._conn.close()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def send(self, command: Message, response_type: Type[R]) -> R:
        """Serialize a protobuf command, send to KiCad, return typed response.

        This method:
        1. Wraps `command` in an ApiRequest envelope (with header fields)
        2. Serializes to bytes and sends over the NNG socket
        3. Receives the ApiResponse bytes
        4. Checks the status code
        5. Unpacks the inner message into `response_type`

        C++ context:
            The ApiRequest.message field is a google.protobuf.Any, which
            stores the type URL and serialized bytes of the inner command.
            KiCad's handleApiRequestString() does:
                ApiRequest request;
                request.ParseFromString(aRequestString);
            Then checks request.message().type_url() to route to the
            correct handler (e.g., handleCreateItems for CreateItems).

        Args:
            command: Any protobuf command message (e.g., CreateItems).
            response_type: The expected response protobuf class.

        Returns:
            Deserialized response of type R.

        Raises:
            IPCConnectionError: If not connected or send/recv fails.
            IPCRequestError: If KiCad returns a non-OK status.
            IPCUnpackError: If the response can't be unpacked.
        """
        if not self._connected:
            self.connect()

        # Import envelope protos
        from .messages import get_envelope_protos
        ApiRequest, ApiResponse = get_envelope_protos()

        # Build the envelope
        envelope = ApiRequest()
        envelope.header.kicad_token = self.kicad_token
        envelope.header.client_name = self.client_name
        envelope.message.Pack(command)

        payload = envelope.SerializeToString()

        # Send
        try:
            self._conn.send(payload)
        except pynng.exceptions.Timeout as e:
            raise IPCTimeoutError(f"Timed out sending request to KiCad: {e}") from e
        except Exception as e:
            self._connected = False
            raise IPCConnectionError(f"Failed to send request to KiCad: {e}") from e

        # Receive
        try:
            reply_bytes = self._conn.recv()
        except pynng.exceptions.Timeout as e:
            raise IPCTimeoutError(
                f"Timed out waiting for KiCad response: {e}"
            ) from e
        except Exception as e:
            self._connected = False
            raise IPCConnectionError(
                f"Failed to receive response from KiCad: {e}"
            ) from e

        # Parse envelope
        reply = ApiResponse()
        reply.ParseFromString(reply_bytes)

        # Check status
        if reply.status.status != ApiStatusCode.AS_OK:
            raise IPCRequestError(
                status_code=reply.status.status,
                error_message=reply.status.error_message,
            )

        # Capture token if this is first exchange
        if not self.kicad_token and reply.header.kicad_token:
            self.kicad_token = reply.header.kicad_token

        # Unpack inner message
        response = response_type()
        if not reply.message.Unpack(response):
            raise IPCUnpackError(
                f"Failed to unpack response of type {response_type.__name__} "
                f"from KiCad reply."
            )

        return response
