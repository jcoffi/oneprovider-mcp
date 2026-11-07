"""Exception hierarchy for the OneProvider MCP server.

All exceptions carry safe, redact-able messages. Credential values must never
be embedded in exception messages or logs.
"""

from __future__ import annotations


class OneProviderMCPError(Exception):
    """Base class for all errors raised by the OneProvider MCP server."""


class ConfigurationError(OneProviderMCPError):
    """Raised when configuration is missing or invalid (e.g. no credentials)."""


class ValidationError(OneProviderMCPError):
    """Raised when a tool argument fails local validation before any request."""


class WritesDisabledError(OneProviderMCPError):
    """Raised when a state-changing tool is invoked while writes are disabled.

    This is enforced in code (tool availability *and* runtime guard), not only
    through tool descriptions.
    """


class DestructiveDisabledError(OneProviderMCPError):
    """Raised when a destructive/financial tool is invoked while destructive
    operations are disabled."""


class ConfirmationError(OneProviderMCPError):
    """Base class for confirmation token problems."""


class ConfirmationRequiredError(ConfirmationError):
    """Raised when a state-changing call is made without a confirmation token.

    The message explains how to obtain one via the
    ``oneprovider_request_confirmation`` tool.
    """


class InvalidConfirmationError(ConfirmationError):
    """Raised when a confirmation token is unknown, expired, already used, or
    bound to a different operation/parameters."""


class ApiError(OneProviderMCPError):
    """An error returned by the OneProvider API.

    The API answers with HTTP 200 even for failures; the authoritative signal
    is the JSON envelope ``{"error": {"message": ..., "code": ...}}``.
    """

    def __init__(self, message: str, code: int | None = None, http_status: int | None = None):
        self.message = message
        self.code = code
        self.http_status = http_status
        super().__init__(f"OneProvider API error {code if code is not None else '?'}: {message}")

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "error": {
                "type": "api_error",
                "code": self.code,
                "http_status": self.http_status,
                "message": self.message,
            },
        }


class AuthenticationError(ApiError):
    """Invalid access token (documented API code 802, verified empirically)."""


class AccessRestrictedError(ApiError):
    """Endpoint exists but the account tier cannot access it (e.g. code 812
    'Access restricted to VIP client' observed for GET /support/tickets)."""


class RateLimitError(ApiError):
    """Rate limited by the API (HTTP 429 or rate-limit error payload)."""


class TransportError(OneProviderMCPError):
    """Network-level failure: DNS, connection refused, timeout, TLS."""

    def __init__(self, message: str, kind: str = "transport"):
        self.kind = kind
        super().__init__(message)
