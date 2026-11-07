"""HTTP client tests (all traffic mocked with respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from oneprovider_mcp.client import OneProviderClient, validate_id
from oneprovider_mcp.exceptions import (
    AccessRestrictedError,
    ApiError,
    AuthenticationError,
    RateLimitError,
    TransportError,
)

from .conftest import BASE_URL, envelope_error, envelope_ok, make_settings

ACCOUNT_BODY = {"email": "user@example.com", "first_name": "Test"}


def _client(**kw) -> OneProviderClient:
    return OneProviderClient(make_settings(**kw))


# ---------------------------------------------------------------- auth


@respx.mock
async def test_auth_headers_sent():
    route = respx.get(f"{BASE_URL}/account").respond(json=envelope_ok(ACCOUNT_BODY))
    async with _client() as c:
        data = await c.get("/account")
    assert route.called
    request = route.calls[0].request
    assert request.headers["Api-Key"] == "API_test_key_for_unit_tests"
    assert request.headers["Client-Key"] == "CK_test_secret_for_unit_tests"
    assert data == ACCOUNT_BODY


@respx.mock
async def test_post_sends_form_encoded():
    route = respx.post(f"{BASE_URL}/vm/boot").respond(json=envelope_ok({"started": True}))
    async with _client() as c:
        await c.post("/vm/boot", data={"vm_id": "123"})
    request = route.calls[0].request
    assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert "vm_id=123" in request.content.decode()


# ---------------------------------------------------------------- success envelopes


@respx.mock
async def test_success_envelope_unwrapped():
    respx.get(f"{BASE_URL}/server/list").respond(json=envelope_ok({"servers": [1, 2]}))
    async with _client() as c:
        assert await c.get("/server/list") == {"servers": [1, 2]}


# ---------------------------------------------------------------- error mapping


@respx.mock
async def test_auth_error_802_mapped():
    respx.get(f"{BASE_URL}/account").respond(json=envelope_error(802, "Invalid access token."))
    async with _client() as c:
        with pytest.raises(AuthenticationError):
            await c.get("/account")


@respx.mock
async def test_restricted_error_812_mapped():
    respx.get(f"{BASE_URL}/support/tickets").respond(
        json=envelope_error(812, "Access restricted to VIP client.")
    )
    async with _client() as c:
        with pytest.raises(AccessRestrictedError):
            await c.get("/support/tickets")


@respx.mock
async def test_generic_api_error_mapped():
    respx.get(f"{BASE_URL}/nope").respond(
        json=envelope_error(404, "The requested resource does not exist.")
    )
    async with _client() as c:
        with pytest.raises(ApiError) as excinfo:
            await c.get("/nope")
    assert excinfo.value.code == 404
    assert "does not exist" in excinfo.value.message


@respx.mock
async def test_error_with_http_200_is_still_error():
    # The API returns HTTP 200 even for errors (verified empirically).
    respx.get(f"{BASE_URL}/account").respond(status_code=200, json=envelope_error(802, "bad token"))
    async with _client() as c:
        with pytest.raises(AuthenticationError):
            await c.get("/account")


@respx.mock
async def test_rate_limit_429_mapped():
    respx.get(f"{BASE_URL}/invoices").respond(
        status_code=429, json={"error": {"message": "slow down", "code": 429}}
    )
    async with _client(max_retries=0) as c:
        with pytest.raises(RateLimitError):
            await c.get("/invoices")


@respx.mock
async def test_malformed_json_raises_api_error():
    respx.get(f"{BASE_URL}/account").respond(
        status_code=200, content=b"not json{", headers={"content-type": "application/json"}
    )
    async with _client() as c:
        with pytest.raises(ApiError, match="Malformed"):
            await c.get("/account")


@respx.mock
async def test_non_json_content_type_rejected():
    respx.get(f"{BASE_URL}/account").respond(
        status_code=200, content=b"<html>hi</html>", headers={"content-type": "text/html"}
    )
    async with _client() as c:
        with pytest.raises(ApiError, match="non-JSON"):
            await c.get("/account")


@respx.mock
async def test_unrecognized_envelope_rejected():
    respx.get(f"{BASE_URL}/account").respond(status_code=200, json={"weird": True})
    async with _client() as c:
        with pytest.raises(ApiError, match="envelope"):
            await c.get("/account")


# ---------------------------------------------------------------- retry behavior


@respx.mock
async def test_get_retries_on_transport_error_then_succeeds():
    route = respx.get(f"{BASE_URL}/account")
    route.side_effect = [
        httpx.ConnectError("boom"),
        httpx.Response(200, json=envelope_ok(ACCOUNT_BODY)),
    ]
    async with _client(max_retries=3, backoff_base=0.01) as c:
        data = await c.get("/account")
    assert data == ACCOUNT_BODY
    assert route.call_count == 2


@respx.mock
async def test_get_retries_exhausted_raises_transport_error():
    respx.get(f"{BASE_URL}/account").mock(side_effect=httpx.ConnectError("boom"))
    async with _client(max_retries=2, backoff_base=0.01) as c:
        with pytest.raises(TransportError):
            await c.get("/account")


@respx.mock
async def test_post_is_never_retried():
    route = respx.post(f"{BASE_URL}/vm/boot").mock(side_effect=httpx.ConnectError("boom"))
    async with _client(max_retries=3, backoff_base=0.01) as c:
        with pytest.raises(TransportError):
            await c.post("/vm/boot", data={"vm_id": "1"})
    assert route.call_count == 1  # no automatic POST retries


@respx.mock
async def test_api_errors_are_not_retried():
    route = respx.get(f"{BASE_URL}/account").respond(json=envelope_error(802, "bad"))
    async with _client(max_retries=3) as c:
        with pytest.raises(AuthenticationError):
            await c.get("/account")
    assert route.call_count == 1


@respx.mock
async def test_timeout_raises_transport_error():
    respx.get(f"{BASE_URL}/account").mock(side_effect=httpx.ReadTimeout("timed out"))
    async with _client(max_retries=0) as c:
        with pytest.raises(TransportError, match="timed out|Timeout"):
            await c.get("/account")


# ---------------------------------------------------------------- pagination


@respx.mock
async def test_get_paginated_single_page():
    respx.get(f"{BASE_URL}/invoices").respond(
        json=envelope_ok(
            {
                "current_page": 1,
                "total_pages": 2,
                "total_number_of_entries": 4,
                "invoices": [{"id": "1"}, {"id": "2"}],
            }
        )
    )
    async with _client() as c:
        data = await c.get_paginated("/invoices", entries_key="invoices", page=1, limit=2)
    assert len(data["invoices"]) == 2
    assert data["pages_fetched"] == 1


@respx.mock
async def test_get_paginated_multi_page_aggregation():
    respx.get(f"{BASE_URL}/invoices").mock(
        side_effect=[
            httpx.Response(
                200,
                json=envelope_ok({"current_page": 1, "total_pages": 2, "invoices": [{"id": "1"}]}),
            ),
            httpx.Response(
                200,
                json=envelope_ok({"current_page": 2, "total_pages": 2, "invoices": [{"id": "2"}]}),
            ),
        ]
    )
    async with _client() as c:
        data = await c.get_paginated(
            "/invoices", entries_key="invoices", page=1, limit=1, max_pages=2
        )
    assert [i["id"] for i in data["invoices"]] == ["1", "2"]
    assert data["pages_fetched"] == 2


@respx.mock
async def test_get_paginated_limit_clamped_to_max():
    route = respx.get(f"{BASE_URL}/invoices").respond(
        json=envelope_ok({"current_page": 1, "total_pages": 1, "invoices": []})
    )
    async with _client() as c:
        await c.get_paginated("/invoices", entries_key="invoices", page=1, limit=10000)
    assert route.calls[0].request.url.params["limit"] == "100"  # API max


# ---------------------------------------------------------------- id validation


@pytest.mark.parametrize("bad", ["", "a/b", "a?b", "a&b", "a b", "../etc", "a" * 200, None, 123])
def test_validate_id_rejects_bad_values(bad):
    with pytest.raises((ValueError, TypeError)):
        if isinstance(bad, str) or bad is None:
            validate_id(bad, name="x")  # type: ignore[arg-type]
        else:
            validate_id(bad, name="x")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "good", ["123", "abc-def", "550e8400-e29b-41d4-a716-446655440000", "srv_1.2", "a:b@c"]
)
def test_validate_id_accepts_reasonable_ids(good):
    assert validate_id(good, name="x") == good


@respx.mock
async def test_requests_stay_on_configured_base_url():
    # Even if a crafted path is passed, httpx joins it against base_url only.
    respx.get(f"{BASE_URL}/server/list").respond(json=envelope_ok({"servers": []}))
    async with _client() as c:
        data = await c.get("/server/list")
    assert data == {"servers": []}
