"""Tool registration modules, grouped by API namespace.

Each module exposes ``register(server, ctx, add_tool) -> dict[str, str]``
returning a mapping of tool name -> tier, for the server's self-description.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..server import AppContext

from mcp.server.mcpserver import MCPServer

from . import account, billing, catalog, servers, support, tags, vms


def register_all(server: MCPServer, ctx: AppContext) -> dict[str, str]:
    from ..server import add_tool  # local import avoids circularity

    registered: dict[str, str] = {}
    for module in (account, servers, vms, catalog, billing, support, tags):
        registered.update(module.register(server, ctx, add_tool))
    return registered
