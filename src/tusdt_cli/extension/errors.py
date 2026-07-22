"""Error types for the extension bridge."""


class BridgeError(Exception):
    """Raised when the extension bridge is unreachable, unauthorized, or
    the extension rejects a request."""

    pass
