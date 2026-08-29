"""KiCad IPC Client.

Low-level IPC transport layer for communicating with KiCad's API server
over NNG (Nanomsg Next Gen) sockets using Protocol Buffers.
"""

from __future__ import annotations

import os
import time
from typing import Optional, Type, TypeVar

try:
    import pynng
except ImportError:
    pynng = None  # type: ignore[assignment]

try:
    from google.protobuf.message import Message
except ImportError:
    Message = object  # type: ignore[misc,assignment]

from .connection import default_socket_path, generate_client_name
from .exceptions import (
    IPCConnectionError,
    IPCTimeoutError,
    IPCRequestError,
    IPCUnpackError,
)
from .messages import ApiStatusCode, get_envelope_protos

R = TypeVar("R", bound=Message)


class KiCadIPCClient:
    """Low-level IPC client for KiCad's API server.

    Wraps the NNG Req0 socket and protobuf envelope serialization.
    """

    def __init__(
        self,
        socket_path: Optional[str] = None,
        client_name: Optional[str] = None,
        kicad_token: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ):
        self.socket_path = socket_path or default_socket_path()
        self.client_name = client_name or generate_client_name()
        self.kicad_token = kicad_token or os.environ.get("KICAD_API_TOKEN", "")
        if timeout_ms is not None:
            self.timeout_ms = timeout_ms
        else:
            env_timeout = os.environ.get("KICAD_API_TIMEOUT_MS")
            self.timeout_ms = int(env_timeout) if env_timeout else 30000
        self._conn: Optional[pynng.Req0] = None  # type: ignore[name-defined]
        self._connected = False
        self.max_not_ready_retries = 5
        self.not_ready_backoff_base_ms = 1000  # 1s, 2s, 4s, 8s, 16s

    def set_timeout(self, timeout_ms: int) -> None:
        """Update the socket send/receive timeout in milliseconds."""
        self.timeout_ms = timeout_ms
        if self._connected and self._conn:
            self._conn.send_timeout = timeout_ms
            self._conn.recv_timeout = timeout_ms

    def connect(self) -> None:
        """Establish the NNG Req0 socket connection to KiCad."""
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
                f"Make sure KiCad is running with the API server enabled. Error: {e}"
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
        """Serialize a protobuf command, send to KiCad, and return typed response."""
        if not self._connected:
            self.connect()

        ApiRequest, ApiResponse = get_envelope_protos()

        envelope = ApiRequest()
        envelope.header.kicad_token = self.kicad_token
        envelope.header.client_name = self.client_name
        envelope.message.Pack(command)

        payload = envelope.SerializeToString()

        for attempt in range(self.max_not_ready_retries + 1):
            # Send
            try:
                self._conn.send(payload)
            except pynng.exceptions.Timeout as e:
                raise IPCTimeoutError(
                    f"Timed out sending request to KiCad after {self.timeout_ms}ms: {e}"
                ) from e
            except Exception as e:
                self._connected = False
                raise IPCConnectionError(f"Failed to send request to KiCad: {e}") from e

            # Receive
            try:
                reply_bytes = self._conn.recv()
            except pynng.exceptions.Timeout as e:
                raise IPCTimeoutError(
                    f"Timed out waiting for KiCad response after {self.timeout_ms}ms: {e}."
                ) from e
            except Exception as e:
                self._connected = False
                raise IPCConnectionError(
                    f"Failed to receive response from KiCad: {e}"
                ) from e

            reply = ApiResponse()
            reply.ParseFromString(reply_bytes)

            # Check status — retry on AS_NOT_READY (transient state)
            if reply.status.status == ApiStatusCode.AS_NOT_READY:
                if attempt < self.max_not_ready_retries:
                    sleep_s = (self.not_ready_backoff_base_ms / 1000.0) * (2 ** attempt)
                    time.sleep(sleep_s)
                    continue
                else:
                    raise IPCRequestError(
                        status_code=reply.status.status,
                        error_message=(
                            f"KiCad is not ready to reply (attempted {self.max_not_ready_retries + 1} times)."
                        ),
                    )

            # Check status — handle AS_TOKEN_MISMATCH
            if reply.status.status == ApiStatusCode.AS_TOKEN_MISMATCH:
                self.kicad_token = reply.header.kicad_token if reply.header.kicad_token else ""
                envelope.header.kicad_token = self.kicad_token
                payload = envelope.SerializeToString()
                if attempt < self.max_not_ready_retries:
                    continue
                else:
                    raise IPCRequestError(
                        status_code=reply.status.status,
                        error_message=reply.status.error_message,
                    )

            if reply.status.status != ApiStatusCode.AS_OK:
                raise IPCRequestError(
                    status_code=reply.status.status,
                    error_message=reply.status.error_message,
                )

            if reply.header.kicad_token:
                self.kicad_token = reply.header.kicad_token

            response = response_type()
            if not reply.message.Unpack(response):
                raise IPCUnpackError(
                    f"Failed to unpack response of type {response_type.__name__} from KiCad reply."
                )

            return response
