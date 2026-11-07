"""MCP server assembly: tools, resources, prompts, transports.

Design notes
------------
- Tools are registered by risk tier. Read-only tools are always registered;
  state-changing tools only when ``ONEPROVIDER_ENABLE_WRITES`` is truthy;
  destructive/financial tools additionally require
  ``ONEPROVIDER_ENABLE_DESTRUCTIVE``. Enforcement is in code, not prose.
- All tool functions are wrapped so that expected errors become structured
  ``{"ok": false, "error": {...}}`` payloads instead of crashing the MCP
  session; unexpected exceptions are logged (stderr) and returned generically.
- STDOUT is reserved for the MCP protocol; all logging goes to STDERR.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .client import OneProviderClient
from .config import Settings
from .exceptions import (
    AccessRestrictedError,
    ApiError,
    AuthenticationError,
    ConfigurationError,
    ConfirmationError,
    DestructiveDisabledError,
    OneProviderMCPError,
    RateLimitError,
    TransportError,
    ValidationError,
    WritesDisabledError,
)
from .safety import ConfirmationManager, RiskTier
from .tools.types import AppContext

logger = logging.getLogger("oneprovider_mcp.server")

ToolFn = Callable[..., Awaitable[dict[str, Any]]]


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, AuthenticationError):
        return {
            "ok": False,
            "error": {
                "type": "authentication_error",
                "code": exc.code,
                "message": exc.message,
                "hint": "Check ONEPROVIDER_API_KEY / ONEPROVIDER_API_SECRET.",
            },
        }
    if isinstance(exc, AccessRestrictedError):
        return {
            "ok": False,
            "error": {
                "type": "access_restricted",
                "code": exc.code,
                "message": exc.message,
                "hint": "This endpoint may require a higher account tier (e.g. VIP).",
            },
        }
    if isinstance(exc, RateLimitError):
        return {"ok": False, "error": {"type": "rate_limited", "message": str(exc)}}
    if isinstance(exc, ApiError):
        return exc.to_dict()
    if isinstance(exc, TransportError):
        return {"ok": False, "error": {"type": exc.kind, "message": str(exc)}}
    if isinstance(exc, WritesDisabledError):
        return {
            "ok": False,
            "error": {
                "type": "writes_disabled",
                "message": str(exc),
                "hint": "Set ONEPROVIDER_ENABLE_WRITES=true in the MCP server environment.",
            },
        }
    if isinstance(exc, DestructiveDisabledError):
        return {
            "ok": False,
            "error": {
                "type": "destructive_disabled",
                "message": str(exc),
                "hint": "Set ONEPROVIDER_ENABLE_DESTRUCTIVE=true to allow this tier.",
            },
        }
    if isinstance(exc, ConfirmationError):
        return {
            "ok": False,
            "error": {"type": "confirmation_error", "message": str(exc)},
        }
    if isinstance(exc, ConfigurationError):
        return {
            "ok": False,
            "error": {"type": "configuration_error", "message": str(exc)},
        }
    if isinstance(exc, (ValidationError, ValueError)):
        return {"ok": False, "error": {"type": "validation_error", "message": str(exc)}}
    if isinstance(exc, OneProviderMCPError):
        return {
            "ok": False,
            "error": {"type": "oneprovider_error", "message": str(exc)},
        }
    # Unexpected: log details to stderr, return sanitized payload.
    logger.exception("Unhandled tool error")
    return {
        "ok": False,
        "error": {
            "type": "internal_error",
            "message": f"{type(exc).__name__} (details logged server-side)",
        },
    }


def wrap_tool(fn: ToolFn) -> ToolFn:
    """Wrap a tool coroutine so expected errors become structured payloads.

    ``functools.wraps`` sets ``__wrapped__`` so ``inspect.signature`` (used by
    the SDK to build the tool's argument schema) still resolves to the
    original function's signature.
    """

    @functools.wraps(fn)
    async def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return await fn(*args, **kwargs)
        except (OneProviderMCPError, ValueError) as exc:
            return _error_payload(exc)
        except Exception as exc:  # noqa: BLE001 -- tool boundary
            return _error_payload(exc)

    return wrapped


def add_tool(
    server: MCPServer,
    ctx: AppContext,
    name: str,
    description: str,
    fn: ToolFn,
    tier: RiskTier,
    *,
    destructive: bool = False,
    idempotent: bool = False,
    title: str | None = None,
) -> bool:
    """Register a tool if its risk tier is enabled by configuration.

    Returns True when the tool was registered.
    """
    if tier is RiskTier.STATE_CHANGING and not ctx.settings.enable_writes:
        return False
    if tier is RiskTier.DESTRUCTIVE and not (
        ctx.settings.enable_writes and ctx.settings.enable_destructive
    ):
        return False

    annotations = ToolAnnotations(
        title=title or name,
        read_only_hint=(tier is RiskTier.READ_ONLY),
        destructive_hint=(destructive or tier is RiskTier.DESTRUCTIVE),
        idempotent_hint=idempotent,
        open_world_hint=True,
    )
    server.tool(name=name, description=description, annotations=annotations)(wrap_tool(fn))
    return True


def build_server(
    settings: Settings,
    client: OneProviderClient,
    confirmations: ConfirmationManager,
) -> MCPServer:
    """Create the MCPServer instance with all eligible tools registered."""
    server: MCPServer = MCPServer(
        name="oneprovider",
        title="OneProvider Infrastructure",
        description=(
            "Read and manage OneProvider dedicated servers, OneCloud VMs, catalog, "
            "billing, support tickets and tags. Read-only by default; write and "
            "destructive tiers require explicit environment opt-in plus single-use "
            "confirmation tokens."
        ),
        instructions=(
            "Authentication uses ONEPROVIDER_API_KEY and ONEPROVIDER_API_SECRET loaded "
            "from ~/Projects/.env. Most listing tools support page/limit pagination "
            "(max limit 100). State-changing tools are only available when writes are "
            "enabled and require a single-use confirmation token from "
            "oneprovider_request_confirmation. Never chain destructive operations "
            "without explicit human approval."
        ),
    )

    ctx = AppContext(settings=settings, client=client, confirmations=confirmations)

    from .tools import register_all

    registered = register_all(server, ctx)
    _register_meta_tools(server, ctx, registered)
    _register_resources(server, ctx)
    _register_prompts(server)

    logger.info(
        "oneprovider MCP server built: %d tools registered (writes=%s, destructive=%s)",
        len(registered),
        settings.enable_writes,
        settings.enable_destructive,
    )
    return server


def _register_meta_tools(server: MCPServer, ctx: AppContext, registered: dict[str, str]) -> None:
    """The confirmation issuer and a server self-description tool."""

    async def oneprovider_request_confirmation(
        operation: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Request a single-use confirmation token for a state-changing or
        destructive operation.

        Args:
            operation: Exact name of the target tool (e.g.
                ``oneprovider_reboot_vm``).
            params: The *exact* parameters that will be passed to the target
                tool, including confirmation_token absent. The token is bound
                to these values; any difference invalidates it.
        """
        if operation not in registered:
            return {
                "ok": False,
                "error": {
                    "type": "validation_error",
                    "message": f"Unknown operation {operation!r}. Available: {sorted(registered)}",
                },
            }
        return {**ctx.confirmations.issue(operation, params), "ok": True}

    async def oneprovider_server_info() -> dict[str, Any]:
        """Describe this MCP server: enabled tiers, registered tools, and the
        configuration summary (credentials redacted)."""
        return {
            "ok": True,
            "server": "oneprovider",
            "configuration": ctx.settings.safe_summary(),
            "tools": registered,
        }

    server.tool(
        name="oneprovider_request_confirmation",
        description=(
            "Issue a short-lived single-use confirmation token bound to an "
            "operation and its exact parameters. Required by all write and "
            "destructive tools via their confirmation_token argument."
        ),
        annotations=ToolAnnotations(title="Request operation confirmation", read_only_hint=True),
    )(oneprovider_request_confirmation)

    server.tool(
        name="oneprovider_server_info",
        description="Report this MCP server's configuration and available tools.",
        annotations=ToolAnnotations(title="Server info", read_only_hint=True),
    )(oneprovider_server_info)

    registered["oneprovider_request_confirmation"] = "meta"
    registered["oneprovider_server_info"] = "meta"


def _register_resources(server: MCPServer, ctx: AppContext) -> None:
    @server.resource(
        "oneprovider://account",
        name="Account summary",
        description="OneProvider account information.",
        mime_type="application/json",
    )
    async def account_resource() -> str:
        import json

        data = await ctx.client.get("/account")
        return json.dumps({"ok": True, "data": data}, default=str)

    @server.resource(
        "oneprovider://servers",
        name="Server inventory",
        description="All dedicated servers and VMs on the account.",
        mime_type="application/json",
    )
    async def servers_resource() -> str:
        import json

        data = await ctx.client.get("/server/list")
        return json.dumps({"ok": True, "data": data}, default=str)

    @server.resource(
        "oneprovider://vm/catalog",
        name="OneCloud catalog",
        description="OneCloud templates, locations and sizes.",
        mime_type="application/json",
    )
    async def vm_catalog_resource() -> str:
        import json

        templates = await ctx.client.get("/vm/templates")
        locations = await ctx.client.get("/vm/locations")
        sizes = await ctx.client.get("/vm/sizes")
        return json.dumps(
            {
                "ok": True,
                "templates": templates,
                "locations": locations,
                "sizes": sizes,
            },
            default=str,
        )

    @server.resource(
        "oneprovider://catalog/locations",
        name="Catalog locations",
        description="Datacenter locations available for dedicated configurations.",
        mime_type="application/json",
    )
    async def catalog_locations_resource() -> str:
        import json

        data = await ctx.client.get("/store/configs/locations", params={"page": 1, "limit": 100})
        return json.dumps({"ok": True, "data": data}, default=str)


def _register_prompts(server: MCPServer) -> None:
    @server.prompt(
        name="infrastructure_review",
        description="Review the full OneProvider infrastructure inventory.",
    )
    def infrastructure_review() -> str:
        return (
            "Using the oneprovider MCP tools (read-only), list all servers and VMs "
            "with oneprovider_list_servers, then summarize: total count, dedicated "
            "vs OneCloud split, hostnames, IPs, locations and renewal dates. Flag "
            "anything expired or nearing expiry. Do not modify anything."
        )

    @server.prompt(
        name="server_status_check",
        description="Inspect the status of a specific server.",
    )
    def server_status_check(server_id: str) -> str:
        return (
            f"Using the oneprovider MCP tools (read-only), retrieve details and "
            f"status for server '{server_id}' with oneprovider_get_server, list its "
            f"available management methods with "
            f"oneprovider_get_server_manage_methods, and report OS/hardware/summary. "
            f"Do not execute any management action."
        )

    @server.prompt(
        name="billing_overview",
        description="Review recent invoices and account standing.",
    )
    def billing_overview() -> str:
        return (
            "Using the oneprovider MCP tools (read-only), fetch account info with "
            "oneprovider_get_account and the latest invoices with "
            "oneprovider_list_invoices (page 1, limit 10). Summarize unpaid vs paid "
            "totals and upcoming renewals. Do not pay anything."
        )
