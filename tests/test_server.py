"""MCP server behavior tests: tiered registration, tool execution, error
propagation, confirmation flow. All API traffic mocked."""

from __future__ import annotations

import json

import pytest
import respx

from oneprovider_mcp.exceptions import InvalidConfirmationError
from oneprovider_mcp.safety import RiskTier, canonical_digest

from .conftest import BASE_URL, envelope_error, envelope_ok

READ_ONLY_MIN = {
    "oneprovider_get_account",
    "oneprovider_list_servers",
    "oneprovider_get_server",
    "oneprovider_list_vms",
    "oneprovider_list_invoices",
    "oneprovider_list_abuses",
    "oneprovider_request_confirmation",
    "oneprovider_server_info",
}
WRITE_ONLY_TOOLS = {
    "oneprovider_boot_vm",
    "oneprovider_shutdown_vm",
    "oneprovider_reboot_vm",
    "oneprovider_set_server_hostname",
    "oneprovider_create_support_ticket",
    "oneprovider_add_cart_item",
    "oneprovider_create_tag",
}
DESTRUCTIVE_TOOLS = {
    "oneprovider_destroy_vm",
    "oneprovider_reinstall_vm",
    "oneprovider_resize_vm",
    "oneprovider_request_server_cancellation",
    "oneprovider_create_order",
    "oneprovider_pay_invoice",
    "oneprovider_remove_tag",
}


async def _tool_names(server) -> set[str]:
    return {t.name for t in await server.list_tools()}


async def _call(server, name: str, arguments: dict) -> dict:
    result = await server.call_tool(name, arguments)
    assert result.content, f"no content returned for {name}"
    return json.loads(result.content[0].text)


# ---------------------------------------------------------------- registration tiers


async def test_read_only_server_has_no_write_tools(ro_server):
    names = await _tool_names(ro_server)
    assert names >= READ_ONLY_MIN
    assert not (names & WRITE_ONLY_TOOLS), "write tools leaked into read-only mode"
    assert not (names & DESTRUCTIVE_TOOLS), "destructive tools leaked into read-only mode"


async def test_writes_server_exposes_write_tools_but_not_destructive(write_server):
    names = await _tool_names(write_server)
    assert names >= WRITE_ONLY_TOOLS
    assert not (names & DESTRUCTIVE_TOOLS)


async def test_destructive_server_exposes_all_tiers(destructive_server):
    names = await _tool_names(destructive_server)
    assert names >= WRITE_ONLY_TOOLS
    assert names >= DESTRUCTIVE_TOOLS


async def test_ro_annotations(ro_server):
    tools = {t.name: t for t in await ro_server.list_tools()}
    assert tools["oneprovider_get_account"].annotations.read_only_hint is True
    assert tools["oneprovider_server_info"].annotations.read_only_hint is True


# ---------------------------------------------------------------- tool execution


@respx.mock
async def test_get_account_tool(ro_server):
    respx.get(f"{BASE_URL}/account").respond(json=envelope_ok({"email": "a@b.c"}))
    out = await _call(ro_server, "oneprovider_get_account", {})
    assert out["ok"] is True
    assert out["data"]["email"] == "a@b.c"


@respx.mock
async def test_list_servers_tool(ro_server):
    respx.get(f"{BASE_URL}/server/list").respond(
        json=envelope_ok({"servers": [{"id": "1", "status": "online"}]})
    )
    out = await _call(ro_server, "oneprovider_list_servers", {"page": 1, "limit": 10})
    assert out["ok"] is True
    assert out["data"]["servers"][0]["id"] == "1"


@respx.mock
async def test_invalid_argument_returns_structured_error(ro_server):
    out = await _call(ro_server, "oneprovider_get_server", {"server_id": "bad id!"})
    assert out["ok"] is False
    assert out["error"]["type"] == "validation_error"


@respx.mock
async def test_api_error_propagates_structured(ro_server):
    respx.get(f"{BASE_URL}/server/info/999").respond(
        json=envelope_error(404, "The requested resource does not exist.")
    )
    out = await _call(ro_server, "oneprovider_get_server", {"server_id": "999"})
    assert out["ok"] is False
    assert out["error"]["type"] == "api_error"
    assert out["error"]["code"] == 404


@respx.mock
async def test_auth_error_payload_has_hint(ro_server):
    respx.get(f"{BASE_URL}/account").respond(json=envelope_error(802, "Invalid access token."))
    out = await _call(ro_server, "oneprovider_get_account", {})
    assert out["ok"] is False
    assert out["error"]["type"] == "authentication_error"


# ---------------------------------------------------------------- confirmation flow


async def test_confirmation_issue_and_consume(confirmations):
    params = {"vm_id": "42"}
    tok = confirmations.issue("op_x", params)["confirmation_token"]
    confirmations.consume("op_x", params, tok)  # must not raise


async def test_confirmation_single_use(confirmations):
    tok = confirmations.issue("op", {"a": 1})["confirmation_token"]
    confirmations.consume("op", {"a": 1}, tok)
    with pytest.raises(InvalidConfirmationError):
        confirmations.consume("op", {"a": 1}, tok)


async def test_confirmation_params_binding(confirmations):
    tok = confirmations.issue("op", {"a": 1})["confirmation_token"]
    with pytest.raises(InvalidConfirmationError, match="does not match"):
        confirmations.consume("op", {"a": 2}, tok)


async def test_confirmation_operation_binding(confirmations):
    tok = confirmations.issue("op_a", {"a": 1})["confirmation_token"]
    with pytest.raises(InvalidConfirmationError, match="issued for"):
        confirmations.consume("op_b", {"a": 1}, tok)


async def test_confirmation_expiry(confirmations):
    import time

    short = confirmations
    tok = short.issue("op", {"a": 1})["confirmation_token"]
    # Age the token past its TTL, then attempt consumption:
    short._pending[tok].expires_at = time.time() - 1
    with pytest.raises(InvalidConfirmationError, match="expired"):
        short.consume("op", {"a": 1}, tok)


async def test_confirmation_token_digest_is_order_insensitive():
    assert canonical_digest({"a": 1, "b": 2}) == canonical_digest({"b": 2, "a": 1})


@respx.mock
async def test_write_tool_requires_confirmation(write_server):
    respx.post(f"{BASE_URL}/vm/boot").respond(json=envelope_ok({"ok": 1}))
    out = await _call(
        write_server, "oneprovider_boot_vm", {"vm_id": "42", "confirmation_token": ""}
    )
    assert out["ok"] is False
    assert out["error"]["type"] == "confirmation_error"
    assert not any(c.called for c in respx.mock.calls if "vm/boot" in str(c.request.url))


@respx.mock
async def test_write_tool_with_valid_confirmation(write_server):
    route = respx.post(f"{BASE_URL}/vm/boot").respond(json=envelope_ok({"started": True}))
    params = {"vm_id": "42"}
    # Issue via the meta tool (as an agent would):
    issued = await _call(
        write_server,
        "oneprovider_request_confirmation",
        {"operation": "oneprovider_boot_vm", "params": params},
    )
    assert issued["ok"] is True
    token = issued["confirmation_token"]
    out = await _call(
        write_server, "oneprovider_boot_vm", {"vm_id": "42", "confirmation_token": token}
    )
    assert out["ok"] is True
    assert route.call_count == 1
    # Token is single-use:
    again = await _call(
        write_server, "oneprovider_boot_vm", {"vm_id": "42", "confirmation_token": token}
    )
    assert again["ok"] is False


@respx.mock
async def test_confirmation_for_unknown_operation_rejected(ro_server):
    out = await _call(
        ro_server,
        "oneprovider_request_confirmation",
        {"operation": "oneprovider_nonexistent", "params": {}},
    )
    assert out["ok"] is False
    assert out["error"]["type"] == "validation_error"


# ---------------------------------------------------------------- meta & self-description


async def test_server_info_reports_configuration(ro_server):
    out = await _call(ro_server, "oneprovider_server_info", {})
    assert out["ok"] is True
    assert out["configuration"]["enable_writes"] is False
    assert "API_test_key" not in json.dumps(out)


# ---------------------------------------------------------------- resources & prompts


async def test_resources_registered(ro_server):
    resources = await ro_server.list_resources()
    uris = {str(r.uri) for r in resources}
    assert "oneprovider://account" in uris
    assert "oneprovider://servers" in uris


async def test_prompts_registered(ro_server):
    prompts = {p.name for p in await ro_server.list_prompts()}
    assert {"infrastructure_review", "server_status_check", "billing_overview"} <= prompts


async def test_read_only_semantics_enforced_in_code(ro_server):
    """Calling a write tool that is not registered must fail at the protocol
    level (tool simply does not exist)."""
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError):
        await ro_server.call_tool("oneprovider_boot_vm", {"vm_id": "1", "confirmation_token": "x"})


def test_risk_tier_values():
    assert RiskTier.READ_ONLY.value == "read_only"
    assert RiskTier.STATE_CHANGING.value == "state_changing"
    assert RiskTier.DESTRUCTIVE.value == "destructive"
