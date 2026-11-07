"""Operation risk tiers and single-use confirmation tokens.

Risk model
----------
- ``READ_ONLY``: no side effects on OneProvider infrastructure. Always enabled.
- ``STATE_CHANGING``: alters service state (power actions, hostname, tags...).
  Requires ``ONEPROVIDER_ENABLE_WRITES=true`` *and* a single-use confirmation
  token issued by ``oneprovider_request_confirmation``.
- ``DESTRUCTIVE``: destroys data, incurs cost or is financially consequential
  (destroy VM, reinstall, resize, cancel service, create order, pay invoice).
  Requires ``ONEPROVIDER_ENABLE_WRITES=true`` *and*
  ``ONEPROVIDER_ENABLE_DESTRUCTIVE=true`` *and* a confirmation token.

Confirmation tokens are:
- bound to (operation_name, canonical parameters digest),
- single-use,
- short-lived (default 300 s).

Reading the tool's own output is *not* treated as human authorization on its
own: the write/destructive environment switches are what the human controls
when configuring the server. High-risk tiers are hard-disabled by default.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .exceptions import InvalidConfirmationError


class RiskTier(StrEnum):
    READ_ONLY = "read_only"
    STATE_CHANGING = "state_changing"
    DESTRUCTIVE = "destructive"


DEFAULT_TOKEN_TTL_SECONDS = 300


def normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop ``None``-valued keys so omitted optional arguments and explicit
    nulls digest identically on both the issue and consume sides."""
    return {k: v for k, v in (params or {}).items() if v is not None}


def canonical_digest(params: dict[str, Any]) -> str:
    """Stable SHA-256 digest of tool parameters (order-insensitive)."""
    payload = json.dumps(
        normalize_params(params), sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class _PendingConfirmation:
    operation: str
    digest: str
    expires_at: float


@dataclass
class ConfirmationManager:
    """Issues and consumes short-lived, single-use confirmation tokens."""

    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS
    _pending: dict[str, _PendingConfirmation] = field(default_factory=dict)

    def issue(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        token = secrets.token_hex(16)
        self._pending[token] = _PendingConfirmation(
            operation=operation,
            digest=canonical_digest(params),
            expires_at=time.time() + self.ttl_seconds,
        )
        self._sweep()
        return {
            "confirmation_token": token,
            "operation": operation,
            "expires_in_seconds": self.ttl_seconds,
            "note": (
                "Single-use token bound to these exact parameters. Re-issue a new "
                "token if any parameter changes. Pass it as confirmation_token."
            ),
        }

    def consume(self, operation: str, params: dict[str, Any], token: str) -> None:
        pending = self._pending.get(token)
        if pending is None:
            raise InvalidConfirmationError(
                "Unknown or already-used confirmation token. Call "
                "oneprovider_request_confirmation first."
            )
        del self._pending[token]
        if time.time() > pending.expires_at:
            raise InvalidConfirmationError(
                "Confirmation token expired. Request a new one and retry promptly."
            )
        if pending.operation != operation:
            raise InvalidConfirmationError(
                f"Confirmation token was issued for {pending.operation!r}, not {operation!r}."
            )
        if pending.digest != canonical_digest(params):
            raise InvalidConfirmationError(
                "Confirmation token does not match the provided parameters. "
                "Re-request confirmation with the exact final parameters."
            )

    def _sweep(self) -> None:
        now = time.time()
        for tok in [t for t, p in self._pending.items() if now > p.expires_at]:
            del self._pending[tok]
