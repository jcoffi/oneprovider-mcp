"""Billing tools: invoices and orders (orders listing here; purchase lives
in catalog.py).

Verified endpoints:
- GET  /invoices, /invoices/{invoice_id}
- POST /invoices/{invoice_id}/pay   (financial)
- GET  /store/orders, /store/orders/{order_id}
"""

from __future__ import annotations

from typing import Any

from ..client import validate_id
from ..safety import RiskTier
from .types import AddToolFn, AppContext, MCPServer

_INVOICE_STATUS = ("Paid", "Unpaid", "Cancelled")
_ORDER_STATUS = ("Paid", "Unpaid", "Cancelled", "Refunded")


def register(server: MCPServer, ctx: AppContext, add: AddToolFn) -> dict[str, str]:
    registered: dict[str, str] = {}

    # ======================= read-only =======================

    async def oneprovider_list_invoices(
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        server_id: str | None = None,
    ) -> dict[str, Any]:
        """List invoices with optional filters. Read-only.

        Args:
            page: 1-based page. limit: 1..100.
            status: Optional ``Paid``, ``Unpaid`` or ``Cancelled``.
            server_id: Optional filter by server ID.
        """
        if status not in (None,) + _INVOICE_STATUS:
            raise ValueError(f"status must be one of {_INVOICE_STATUS}")
        if server_id:
            validate_id(server_id, name="server_id")
        data = await ctx.client.get_paginated(
            "/invoices",
            entries_key="invoices",
            page=page,
            limit=limit,
            params={"status": status, "server_id": server_id},
        )
        return {"ok": True, "operation": "oneprovider_list_invoices", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_invoices",
        "List your invoices with optional status/server filters.",
        oneprovider_list_invoices,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_invoices"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_invoice(invoice_id: str) -> dict[str, Any]:
        """Get one invoice's content. Read-only.

        Args:
            invoice_id: The invoice ID.
        """
        validate_id(invoice_id, name="invoice_id")
        data = await ctx.client.get(f"/invoices/{invoice_id}")
        return {"ok": True, "operation": "oneprovider_get_invoice", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_get_invoice",
        "Get the detailed content of one invoice.",
        oneprovider_get_invoice,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_invoice"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_orders(
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        from_api_only: bool = True,
    ) -> dict[str, Any]:
        """List your store orders. Read-only.

        Args:
            page: 1-based page. limit: 1..100.
            status: Optional ``Paid``, ``Unpaid``, ``Cancelled`` or ``Refunded``.
            from_api_only: Only orders created via the API (default true).
        """
        if status not in (None,) + _ORDER_STATUS:
            raise ValueError(f"status must be one of {_ORDER_STATUS}")
        data = await ctx.client.get_paginated(
            "/store/orders",
            entries_key="orders",
            page=page,
            limit=limit,
            params={"status": status, "from_api_only": int(from_api_only)},
        )
        return {"ok": True, "operation": "oneprovider_list_orders", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_orders",
        "List your store orders with optional status filter.",
        oneprovider_list_orders,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_orders"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_order(order_id: str) -> dict[str, Any]:
        """Get one order's details. Read-only.

        Args:
            order_id: The order ID.
        """
        validate_id(order_id, name="order_id")
        data = await ctx.client.get(f"/store/orders/{order_id}")
        return {"ok": True, "operation": "oneprovider_get_order", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_get_order",
        "Get the details of one order.",
        oneprovider_get_order,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_order"] = RiskTier.READ_ONLY.value

    # ======================= financial =======================

    async def oneprovider_pay_invoice(
        invoice_id: str, amount: float, confirmation_token: str
    ) -> dict[str, Any]:
        """Pay an invoice using account funds. FINANCIALLY CONSEQUENTIAL:
        moves real money/credit. Requires the destructive tier and a
        confirmation token.

        Args:
            invoice_id: The invoice ID.
            amount: Amount of account funds to apply.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(invoice_id, name="invoice_id")
        if amount <= 0:
            raise ValueError("amount must be positive")
        ctx.confirmations.consume(
            "oneprovider_pay_invoice",
            {"invoice_id": invoice_id, "amount": amount},
            confirmation_token,
        )
        data = await ctx.client.post(f"/invoices/{invoice_id}/pay", data={"amount": amount})
        return {
            "ok": True,
            "operation": "oneprovider_pay_invoice",
            "data": data,
            "warning": "Payment applied from account funds.",
        }

    if add(
        server,
        ctx,
        "oneprovider_pay_invoice",
        "FINANCIAL: pay an invoice from account funds.",
        oneprovider_pay_invoice,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_pay_invoice"] = RiskTier.DESTRUCTIVE.value

    return registered
