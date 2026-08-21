"""KiCad IPC Exception Types.

Domain-specific exceptions for the IPC transport layer.
These replace generic Python exceptions with meaningful error types
that callers can catch and handle appropriately.
"""


class IPCError(Exception):
    """Base exception for all KiCad IPC errors."""
    pass


class IPCConnectionError(IPCError):
    """Failed to connect to KiCad's IPC server.

    Common causes:
    - KiCad is not running
    - The API server is not enabled (Preferences → Plugins → Enable API)
    - Wrong socket path
    """
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
