"""Dedicated-server tools.

Verified endpoints:
- GET  /server/list                     -> list all servers and VMs
- GET  /server/info/{server_id}         -> server details
- GET  /server/manage/{server_id}       -> management methods available
- POST /server/action                   -> execute a management method
- POST /server/hostname                 -> change hostname
- POST /server/cancel                   -> request service cancellation (DESTRUCTIVE)
- POST /server/remove/cancellation      -> remove cancellation request
"""

from __future__ import annotations

from typing import Any

from ..client import validate_id
from ..safety import RiskTier
from .types import AddToolFn, AppContext, MCPServer


def register(server: MCPServer, ctx: AppContext, add: AddToolFn) -> dict[str, str]:
    registered: dict[str, str] = {}

    async def oneprovider_list_servers(page: int = 1, limit: int = 50) -> dict[str, Any]:
        """List all servers and VMs associated with the account. Read-only.

        Args:
            page: 1-based result page (default 1).
            limit: Results per page, capped at 100.
        """
        data = await ctx.client.get_paginated(
            "/server/list", entries_key="servers", page=page, limit=limit
        )
        return {"ok": True, "operation": "oneprovider_list_servers", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_servers",
        "List all dedicated servers and VMs on the account with IDs, names and statuses.",
        oneprovider_list_servers,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_servers"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_server(server_id: str) -> dict[str, Any]:
        """Retrieve full details of one server (hardware, OS, location,
        expiry). Read-only.

        Args:
            server_id: The server ID (from oneprovider_list_servers).
        """
        validate_id(server_id, name="server_id")
        data = await ctx.client.get(f"/server/info/{server_id}")
        return {"ok": True, "operation": "oneprovider_get_server", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_get_server",
        "Get detailed information about one server: hardware, OS, IP, location, expiry.",
        oneprovider_get_server,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_server"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_server_manage_methods(server_id: str) -> dict[str, Any]:
        """List the management methods available for a server (the allowed
        ``action`` values for oneprovider_server_power_action). Read-only.

        Args:
            server_id: The server ID.
        """
        validate_id(server_id, name="server_id")
        data = await ctx.client.get(f"/server/manage/{server_id}")
        return {
            "ok": True,
            "operation": "oneprovider_get_server_manage_methods",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_get_server_manage_methods",
        "List management methods (power actions etc.) available for a server.",
        oneprovider_get_server_manage_methods,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_server_manage_methods"] = RiskTier.READ_ONLY.value

    # ---------------- state-changing (tier 2) ----------------

    async def oneprovider_server_power_action(
        server_id: str, action: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Execute a management action on a dedicated server (e.g. reboot,
        power on/off) using a method name from
        oneprovider_get_server_manage_methods. STATE-CHANGING: may restart or
        interrupt the server. Requires a confirmation token.

        Args:
            server_id: The server ID.
            action: Method name exactly as returned by
                oneprovider_get_server_manage_methods.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(server_id, name="server_id")
        if not action or any(c in action for c in "/?& \t\n"):
            raise ValueError("action must be a bare method name")
        ctx.confirmations.consume(
            "oneprovider_server_power_action",
            {"server_id": server_id, "action": action},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/server/action", data={"server_id": server_id, "action": action}
        )
        return {
            "ok": True,
            "operation": "oneprovider_server_power_action",
            "requested_action": action,
            "server_id": server_id,
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_server_power_action",
        "Execute a server management action (reboot/poweron/poweroff/...) from the "
        "methods listed by oneprovider_get_server_manage_methods. Interrupts service.",
        oneprovider_server_power_action,
        RiskTier.STATE_CHANGING,
        title="Server power action",
    ):
        registered["oneprovider_server_power_action"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_set_server_hostname(
        server_id: str, hostname: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Change a server's hostname. STATE-CHANGING. Requires a
        confirmation token.

        Args:
            server_id: The server ID.
            hostname: New hostname (letters, digits, dots, hyphens).
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(server_id, name="server_id")
        import re as _re

        if not _re.match(r"^[A-Za-z0-9]([A-Za-z0-9-.]{0,251}[A-Za-z0-9])?$", hostname):
            raise ValueError("hostname contains invalid characters")
        ctx.confirmations.consume(
            "oneprovider_set_server_hostname",
            {"server_id": server_id, "hostname": hostname},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/server/hostname", data={"server_id": server_id, "hostname": hostname}
        )
        return {
            "ok": True,
            "operation": "oneprovider_set_server_hostname",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_set_server_hostname",
        "Change a dedicated server's hostname.",
        oneprovider_set_server_hostname,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_set_server_hostname"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_remove_server_cancellation(
        server_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Remove an existing cancellation request on a server or VM.
        STATE-CHANGING. Requires a confirmation token.

        Args:
            server_id: The server ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(server_id, name="server_id")
        ctx.confirmations.consume(
            "oneprovider_remove_server_cancellation",
            {"server_id": server_id},
            confirmation_token,
        )
        data = await ctx.client.post("/server/remove/cancellation", data={"server_id": server_id})
        return {
            "ok": True,
            "operation": "oneprovider_remove_server_cancellation",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_remove_server_cancellation",
        "Remove a pending cancellation request on a server or VM.",
        oneprovider_remove_server_cancellation,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_remove_server_cancellation"] = RiskTier.STATE_CHANGING.value

    # ---------------- destructive (tier 3) ----------------

    async def oneprovider_request_server_cancellation(
        server_id: str, reason: str, cancellation_type: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Request cancellation of a server or VM. DESTRUCTIVE / financially
        consequential: the service will stop being billed/served per the
        chosen cancellation type. Requires confirmation token.

        Args:
            server_id: The server ID.
            reason: Reason for the cancellation.
            cancellation_type: One of ``Immediate`` or
                ``End of Billing Period``.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(server_id, name="server_id")
        if cancellation_type not in ("Immediate", "End of Billing Period"):
            raise ValueError("cancellation_type must be 'Immediate' or 'End of Billing Period'")
        ctx.confirmations.consume(
            "oneprovider_request_server_cancellation",
            {
                "server_id": server_id,
                "reason": reason,
                "cancellation_type": cancellation_type,
            },
            confirmation_token,
        )
        data = await ctx.client.post(
            "/server/cancel",
            data={"server_id": server_id, "reason": reason, "type": cancellation_type},
        )
        return {
            "ok": True,
            "operation": "oneprovider_request_server_cancellation",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_request_server_cancellation",
        "DESTRUCTIVE: request cancellation of a server/VM (Immediate or End of Billing Period).",
        oneprovider_request_server_cancellation,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_request_server_cancellation"] = RiskTier.DESTRUCTIVE.value

    return registered
