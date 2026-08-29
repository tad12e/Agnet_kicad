"""IPC Protocol Serialization and Packaging Utilities."""

from __future__ import annotations

from typing import Any, Tuple, Type, TypeVar
from google.protobuf.message import Message

from .exceptions import IPCUnpackError
from .messages import get_envelope_protos

R = TypeVar("R", bound=Message)


class ProtocolHelper:
    """Helper for packing commands into ApiRequest and unpacking ApiResponse."""

    @staticmethod
    def pack_request(command: Message, client_name: str, token: str = "") -> bytes:
        """Wrap a command message into an ApiRequest envelope and serialize to bytes."""
        ApiRequest, _ = get_envelope_protos()
        envelope = ApiRequest()
        envelope.header.client_name = client_name
        envelope.header.kicad_token = token
        envelope.message.Pack(command)
        return envelope.SerializeToString()

    @staticmethod
    def unpack_response(reply_bytes: bytes, response_type: Type[R]) -> Tuple[R, str, int, str]:
        """Parse ApiResponse envelope, extract token, status code, error message, and inner message.
        
        Returns:
            Tuple of (unpacked_response, new_token, status_code, error_message)
        """
        _, ApiResponse = get_envelope_protos()
        reply = ApiResponse()
        reply.ParseFromString(reply_bytes)
        
        status_code = reply.status.status
        error_message = reply.status.error_message
        token = reply.header.kicad_token if reply.header.kicad_token else ""
        
        response = response_type()
        if reply.message.ByteSize() > 0:
            if not reply.message.Unpack(response):
                raise IPCUnpackError(
                    f"Failed to unpack response of type {response_type.__name__} from KiCad reply."
                )
        
        return response, token, status_code, error_message
