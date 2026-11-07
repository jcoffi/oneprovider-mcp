"""Security tests: secret redaction, write gating, confirmation binding,
prevention of arbitrary API requests and accidental destructive operations."""

from __future__ import annotations

import json

import pytest
import respx

from oneprovider_mcp.client import OneProviderClient, validate_id
from oneprovider_mcp.config import load_settings
from oneprovider_mcp.exceptions import ConfigurationError
from oneprovider_mcp.server import build_server
from oneprovider_mcp.tools.vms import _valid_ip

from .conftest import BASE_URL, FAKE_API_KEY, FAKE_SECRET, envelope_ok, make_settings

# ---------------------------------------------------------------- secret hygiene


def test_client_never_exposes_secrets_in_repr(settings):
    c = OneProviderClient(settings)
    assert "API_test_key_for_unit_tests" not in repr(settings.safe_summary())
    # Only the outbound transport headers carry the raw key (never tool output):
    assert c._client.headers["Api-Key"] == FAKE_API_KEY


def test_safe_summary_never_contains_raw_secrets():
    s = make_settings()
    blob = json.dumps(s.safe_summary())
    assert FAKE_API_KEY not in blob
    assert FAKE_SECRET not in blob


def test_error_payloads_from_tools_contain_no_secrets(ro_server):
    import asyncio

    async def run():
        result = await ro_server.call_tool("oneprovider_get_server", {"server_id": "bad!"})
        return result.content[0].text

    text = asyncio.run(run())
    assert FAKE_API_KEY not in text
    assert FAKE_SECRET not in text


@respx.mock
async def test_api_key_sent_only_in_headers_not_url():
    route = respx.get(f"{BASE_URL}/account").respond(json=envelope_ok({}))
    c = OneProviderClient(make_settings())
    await c.get("/account")
    url = str(route.calls[0].request.url)
    assert FAKE_API_KEY not in url
    assert FAKE_SECRET not in url
    assert route.calls[0].request.headers["Api-Key"] == FAKE_API_KEY


# ---------------------------------------------------------------- write gating


async def test_writes_disabled_by_default_ro_server(ro_server):
    names = {t.name for t in await ro_server.list_tools()}
    write_like = [
        n
        for n in names
        if any(
            v in n
            for v in (
                "boot_vm",
                "shutdown_vm",
                "reboot_vm",
                "poweroff",
                "destroy",
                "reinstall",
                "resize",
                "pay_invoice",
                "create_order",
                "cancel",
            )
        )
    ]
    assert write_like == [], f"state-changing tools registered in read-only mode: {write_like}"


@respx.mock
async def test_write_tools_absent_so_state_changes_impossible(ro_server):
    """In read-only mode, invoking a state-changing tool must fail: it is not
    registered at all (enforced in code, not by description only)."""
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="Unknown tool"):
        await ro_server.call_tool(
            "oneprovider_reboot_vm", {"vm_id": "1", "confirmation_token": "x"}
        )


@respx.mock
async def test_destructive_needs_both_flags(ro_server):
    names = {t.name for t in await ro_server.list_tools()}
    assert "oneprovider_destroy_vm" not in names

    from oneprovider_mcp.safety import ConfirmationManager

    write_only = build_server(
        make_settings(enable_writes=True),
        OneProviderClient(make_settings(enable_writes=True)),
        ConfirmationManager(),
    )
    names = {t.name for t in await write_only.list_tools()}
    assert "oneprovider_reboot_vm" in names
    assert "oneprovider_destroy_vm" not in names


# ---------------------------------------------------------------- confirmation binding


@respx.mock
async def test_confirmation_bound_to_exact_parameters(write_server):
    respx.post(f"{BASE_URL}/vm/boot").respond(json=envelope_ok({}))
    issued = json.loads(
        (
            await write_server.call_tool(
                "oneprovider_request_confirmation",
                {"operation": "oneprovider_boot_vm", "params": {"vm_id": "42"}},
            )
        )
        .content[0]
        .text
    )
    token = issued["confirmation_token"]

    # Same operation but DIFFERENT target must be rejected:
    out = json.loads(
        (
            await write_server.call_tool(
                "oneprovider_boot_vm",
                {"vm_id": "43", "confirmation_token": token},
            )
        )
        .content[0]
        .text
    )
    assert out["ok"] is False
    assert out["error"]["type"] == "confirmation_error"


@respx.mock
async def test_destructive_tool_requires_confirmation_even_when_enabled(destructive_server):
    respx.post(f"{BASE_URL}/vm/destroy").respond(json=envelope_ok({}))
    out = json.loads(
        (
            await destructive_server.call_tool(
                "oneprovider_destroy_vm",
                {"vm_id": "1", "confirm_close": True, "confirmation_token": ""},
            )
        )
        .content[0]
        .text
    )
    assert out["ok"] is False
    assert out["error"]["type"] == "confirmation_error"


# ---------------------------------------------------------------- arbitrary request prevention


def test_base_url_must_be_https(tmp_path, monkeypatch):
    monkeypatch.delenv("ONEPROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("ONEPROVIDER_API_SECRET", raising=False)
    monkeypatch.setenv("ONEPROVIDER_API_KEY", FAKE_API_KEY)
    monkeypatch.setenv("ONEPROVIDER_API_SECRET", FAKE_SECRET)
    monkeypatch.setenv("ONEPROVIDER_BASE_URL", "http://internal-metadata.amazonaws.com")
    with pytest.raises(ConfigurationError):
        load_settings(env_file=tmp_path / "missing.env")


@pytest.mark.parametrize("bad", ["../../admin", "x/y", "x y", "", "a?b"])
def test_validate_id_blocks_path_manipulation(bad):
    with pytest.raises(ValueError):
        validate_id(bad, name="x")


@pytest.mark.parametrize("bad", ["not-an-ip", "999.1.1.1", "example.com", ""])
def test_ip_validation_blocks_non_ips(bad):
    with pytest.raises(ValueError):
        _valid_ip(bad)


@respx.mock
async def test_tool_cannot_request_foreign_host(ro_server):
    """Tools construct paths only; even a hostile path stays on base_url."""
    respx.get(f"{BASE_URL}/server/info/ok1").respond(json=envelope_ok({"id": "ok1"}))
    out = json.loads(
        (await ro_server.call_tool("oneprovider_get_server", {"server_id": "ok1"})).content[0].text
    )
    assert out["ok"] is True
    assert str(respx.mock.calls[-1].request.url).startswith(BASE_URL)


# ---------------------------------------------------------------- destructive guards


async def test_destroy_requires_confirm_close_true(destructive_server):
    from oneprovider_mcp.safety import ConfirmationManager

    tok = ConfirmationManager().issue(
        "oneprovider_destroy_vm",
        {"vm_id": "1", "confirm_close": True, "confirmation_token": ""},
    )["confirmation_token"]
    respx.post(f"{BASE_URL}/vm/destroy").respond(json=envelope_ok({}))
    out = json.loads(
        (
            await destructive_server.call_tool(
                "oneprovider_destroy_vm",
                {"vm_id": "1", "confirm_close": False, "confirmation_token": tok},
            )
        )
        .content[0]
        .text
    )
    assert out["ok"] is False
    assert "confirm_close" in out["error"]["message"]


async def test_malformed_payloads_fail_closed_before_request(ro_server):
    """Validation happens before any network call."""
    out = json.loads(
        (await ro_server.call_tool("oneprovider_search_vm_by_ip", {"ip": "definitely.not.an.ip"}))
        .content[0]
        .text
    )
    assert out["ok"] is False
    assert out["error"]["type"] == "validation_error"
