"""KiCad IPC Exception Types.

Domain-specific exceptions for the IPC transport layer.
"""

from __future__ import annotations


class IPCError(Exception):
    """Base exception for all KiCad IPC transport errors."""
    pass


class IPCConnectionError(IPCError):
    """Failed to connect to KiCad's IPC server."""
    pass


class IPCTimeoutError(IPCError):
    """Request to KiCad timed out waiting for a response."""
    pass


class IPCRequestError(IPCError):
    """KiCad returned an error status for the API request.

    Attributes:
        status_code: The ApiStatusCode returned by KiCad.
        error_message: The error message from KiCad.
    """

    def __init__(self, status_code: int, error_message: str):
        self.status_code = status_code
        self.error_message = error_message
        super().__init__(
            f"KiCad API error [status={status_code}]: {error_message}"
        )


class IPCUnpackError(IPCError):
    """Failed to unpack a protobuf response message from KiCad."""
    pass
