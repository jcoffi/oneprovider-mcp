"""Account tools (read-only)."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..safety import RiskTier
from .types import AddToolFn, AppContext


def register(server: MCPServer, ctx: AppContext, add: AddToolFn) -> dict[str, str]:
    registered: dict[str, str] = {}

    async def oneprovider_get_account() -> dict[str, Any]:
        """Retrieve your OneProvider account information (email, name,
        company, address, language). Read-only."""
        data = await ctx.client.get("/account")
        return {"ok": True, "operation": "oneprovider_get_account", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_get_account",
        "Get your OneProvider account information (contact details, country, language).",
        oneprovider_get_account,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_account"] = RiskTier.READ_ONLY.value

    return registered
