"""Asynchronous OneProvider API client.

Verified facts about the API (empirical, 2026-11-07):
- Base URL: ``https://api.oneprovider.com``
- Auth via two headers: ``Api-Key`` and ``Client-Key`` (+ ``X-Pretty-JSON: 1``).
- Success envelope: HTTP 200 ``{"result": "success", "response": <data>}``.
- Failure envelope: ``{"error": {"message": str, "code": int}}`` -- frequently
  with HTTP status 200, so the *body* is authoritative, not the status code.
- Documented error codes observed: 404 (unknown resource), 802 (invalid
  access token), 812 (access restricted to VIP clients).
- POST bodies are form-encoded (``application/x-www-form-urlencoded``).

Retry policy: only idempotent GET requests are automatically retried, and only
for transport-level failures or 5xx responses, with bounded exponential
backoff + jitter. POST requests are never automatically retried.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any

import httpx

from .config import Settings
from .exceptions import (
    AccessRestrictedError,
    ApiError,
    AuthenticationError,
    RateLimitError,
    TransportError,
)

logger = logging.getLogger("oneprovider_mcp.client")

USER_AGENT = "oneprovider-mcp/1.0 (MCP; +https://oneprovider.com)"

# IDs appear in URL path segments. Allow a conservative charset; reject
# anything that could change the request target (/, ?, &, whitespace, ..).
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:@+-]{1,128}$")

# API error codes with known semantics (verified empirically or documented).
_CODE_AUTH = {802}
_CODE_RESTRICTED = {812}


def validate_id(value: str, *, name: str = "id") -> str:
    """Validate a user-supplied identifier used inside a URL path segment."""
    if not isinstance(value, str) or not SAFE_ID_RE.match(value):
        raise ValueError(f"Invalid {name}: must match ^[A-Za-z0-9_.:@+-]{{1,128}}$ (got {value!r})")
    return value


class OneProviderClient:
    """Centralized async client with connection pooling and safe retries."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
                **settings.auth_headers,
            },
            timeout=httpx.Timeout(
                settings.timeout_seconds,
                connect=min(10.0, settings.timeout_seconds),
            ),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30.0,
            ),
            follow_redirects=False,
        )

    # -- lifecycle ---------------------------------------------------------

    async def __aenter__(self) -> OneProviderClient:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- low-level request machinery ----------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Perform an API call and return the unwrapped ``response`` payload.

        Raises ApiError subclasses for API-level errors and TransportError for
        network-level failures after exhausting retries (GET only).
        """
        if method not in {"GET", "POST"}:
            raise ValueError(f"Unsupported HTTP method: {method}")

        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        clean_data = {k: v for k, v in (data or {}).items() if v is not None}

        max_attempts = 1
        if method == "GET":
            max_attempts += self._settings.max_retries

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=clean_params or None,
                    data=clean_data or None,
                )
                return self._parse_response(response, method=method, path=path)
            except httpx.TimeoutException:
                last_error = TransportError(
                    f"Request timed out after {self._settings.timeout_seconds}s",
                    kind="timeout",
                )
            except httpx.TransportError as exc:
                last_error = TransportError(
                    f"Transport failure: {type(exc).__name__}", kind="transport"
                )
            except httpx.HTTPStatusError as exc:
                # _parse_response raises this only for 5xx
                last_error = TransportError(
                    f"Server error HTTP {exc.response.status_code}", kind="server"
                )
            except ApiError:
                # API-level errors are deterministic; do not retry.
                raise

            if attempt < max_attempts:
                delay = self._settings.backoff_base * (2 ** (attempt - 1))
                delay += random.uniform(0, delay / 2)  # jitter
                logger.warning(
                    "Transient failure (attempt %d/%d) on %s %s; retrying in %.2fs",
                    attempt,
                    max_attempts,
                    method,
                    path,
                    delay,
                )
                await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    def _parse_response(self, response: httpx.Response, *, method: str, path: str) -> Any:
        if response.status_code == 429:
            raise RateLimitError(
                "Rate limited by OneProvider API; slow down and retry later.",
                code=429,
                http_status=429,
            )
        if response.status_code >= 500:
            # Surface as retryable transport-class error for GETs.
            raise httpx.HTTPStatusError(
                f"Server error {response.status_code}",
                request=response.request,
                response=response,
            )

        content_type = response.headers.get("content-type", "")
        if "json" not in content_type and response.content[:1] not in (b"{", b"["):
            raise ApiError(
                f"Unexpected non-JSON response (content-type={content_type!r})",
                code=None,
                http_status=response.status_code,
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise ApiError(
                "Malformed JSON in API response",
                code=None,
                http_status=response.status_code,
            ) from exc

        if not isinstance(body, dict):
            raise ApiError(
                "Unexpected API payload shape (not a JSON object)",
                code=None,
                http_status=response.status_code,
            )

        error = body.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = str(error.get("message", "unknown error"))
            if code in _CODE_AUTH:
                raise AuthenticationError(message, code=code, http_status=response.status_code)
            if code in _CODE_RESTRICTED:
                raise AccessRestrictedError(message, code=code, http_status=response.status_code)
            raise ApiError(
                message,
                code=code if isinstance(code, int) else None,
                http_status=response.status_code,
            )

        if body.get("result") == "success":
            return body.get("response")

        raise ApiError(
            "Unrecognized API response envelope",
            code=None,
            http_status=response.status_code,
        )

    # -- typed public methods ------------------------------------------------

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, *, data: dict[str, Any] | None = None) -> Any:
        return await self.request("POST", path, data=data)

    async def get_paginated(
        self,
        path: str,
        *,
        entries_key: str,
        page: int = 1,
        limit: int = 20,
        params: dict[str, Any] | None = None,
        max_pages: int = 1,
    ) -> dict[str, Any]:
        """Fetch paginated list endpoints.

        Returns the API's page metadata plus the requested page's entries.
        When ``max_pages > 1``, aggregates up to ``max_pages`` pages (bounded
        to keep responses small) and reports ``pages_fetched``.
        """
        page = max(1, int(page))
        limit = min(max(1, int(limit)), self._settings.max_page_size)
        max_pages = max(1, min(int(max_pages), 10))

        merged: list[Any] = []
        meta: dict[str, Any] = {}
        pages_fetched = 0
        total_pages = 1
        current = page
        while pages_fetched < max_pages and current <= max(total_pages, 1):
            data = await self.get(path, params={**(params or {}), "page": current, "limit": limit})
            if not isinstance(data, dict):
                # Some list endpoints may return bare lists; normalize.
                return {
                    "page": page,
                    "limit": limit,
                    entries_key: data,
                    "pages_fetched": 1,
                }
            meta = data
            merged.extend(data.get(entries_key, []) or [])
            pages_fetched += 1
            total_pages = int(data.get("total_pages", 1) or 1)
            current += 1

        result = {k: v for k, v in meta.items() if k != entries_key}
        result[entries_key] = merged
        result["pages_fetched"] = pages_fetched
        return result
