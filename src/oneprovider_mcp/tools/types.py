"""Shared types for tool modules (defined here to avoid circular imports)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer

from ..client import OneProviderClient
from ..config import Settings
from ..safety import ConfirmationManager, RiskTier


@dataclass
class AppContext:
    """Shared context captured by every registered tool."""

    settings: Settings
    client: OneProviderClient
    confirmations: ConfirmationManager


# (server, ctx, name, description, fn, tier, *, destructive, idempotent, title) -> bool
AddToolFn = Callable[..., bool]

__all__ = ["MCPServer", "RiskTier", "AddToolFn", "AppContext"]
