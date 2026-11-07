"""Support and abuse-report tools.

Verified endpoints:
- GET  /support/tickets (observed: code 812 'Access restricted to VIP client'
       on a standard account)
- GET  /support/tickets/{ticket_id} (NOTE: marks the ticket as read)
- GET  /support/tickets/departments
- POST /support/tickets, .../{ticket_id}/reopen|close|reply
- GET  /abuses, /abuses/{server_id}
"""

from __future__ import annotations

from typing import Any

from ..client import validate_id
from ..safety import RiskTier
from .types import AddToolFn, AppContext, MCPServer


def register(server: MCPServer, ctx: AppContext, add: AddToolFn) -> dict[str, str]:
    registered: dict[str, str] = {}

    # ======================= read-only =======================

    async def oneprovider_list_support_departments() -> dict[str, Any]:
        """List all support departments and sub-departments. Read-only."""
        data = await ctx.client.get("/support/tickets/departments")
        return {
            "ok": True,
            "operation": "oneprovider_list_support_departments",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_list_support_departments",
        "List support departments and sub-departments (needed to open tickets).",
        oneprovider_list_support_departments,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_support_departments"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_support_tickets() -> dict[str, Any]:
        """List open/unread support tickets. Read-only. NOTE: on standard
        (non-VIP) accounts the API may answer 812 'Access restricted to VIP
        client' for this endpoint."""
        data = await ctx.client.get("/support/tickets")
        return {
            "ok": True,
            "operation": "oneprovider_list_support_tickets",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_list_support_tickets",
        "List open/unread support tickets (may require VIP account tier).",
        oneprovider_list_support_tickets,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_support_tickets"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_support_ticket(ticket_id: str) -> dict[str, Any]:
        """Get one support ticket's content. Read-only except for one
        documented side effect: the API marks the ticket as read.

        Args:
            ticket_id: The ticket ID.
        """
        validate_id(ticket_id, name="ticket_id")
        data = await ctx.client.get(f"/support/tickets/{ticket_id}")
        return {
            "ok": True,
            "operation": "oneprovider_get_support_ticket",
            "data": data,
            "note": "The API marks this ticket as read.",
        }

    if add(
        server,
        ctx,
        "oneprovider_get_support_ticket",
        "Get a support ticket's content (side effect: API marks it as read).",
        oneprovider_get_support_ticket,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_support_ticket"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_abuses(page: int = 1, limit: int = 20) -> dict[str, Any]:
        """List abuse reports on the account. Read-only.

        Args:
            page: 1-based page. limit: 1..100.
        """
        data = await ctx.client.get_paginated(
            "/abuses", entries_key="abuses", page=page, limit=limit
        )
        return {"ok": True, "operation": "oneprovider_list_abuses", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_abuses",
        "List abuse reports filed against your services.",
        oneprovider_list_abuses,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_abuses"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_server_abuses(
        server_id: str, page: int = 1, limit: int = 20
    ) -> dict[str, Any]:
        """List abuse reports for one server. Read-only.

        Args:
            server_id: The server ID.
            page: 1-based page. limit: 1..100.
        """
        validate_id(server_id, name="server_id")
        data = await ctx.client.get_paginated(
            f"/abuses/{server_id}", entries_key="abuses", page=page, limit=limit
        )
        return {"ok": True, "operation": "oneprovider_list_server_abuses", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_server_abuses",
        "List abuse reports for one specific server.",
        oneprovider_list_server_abuses,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_server_abuses"] = RiskTier.READ_ONLY.value

    # ======================= state-changing =======================

    async def oneprovider_create_support_ticket(
        department: str,
        message: str,
        subject: str | None = None,
        server_id: str | None = None,
        sub_department: str | None = None,
        confirmation_token: str = "",
    ) -> dict[str, Any]:
        """Open a new support ticket. STATE-CHANGING (creates a real ticket).

        Args:
            department: Department ID from
                oneprovider_list_support_departments.
            message: Ticket message body.
            subject: Subject (mandatory when the department does not require
                a server).
            server_id: Related server ID (required by server-specific
                departments).
            sub_department: Optional sub-department ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(department, name="department")
        if server_id:
            validate_id(server_id, name="server_id")
        if sub_department:
            validate_id(sub_department, name="sub_department")
        if not message.strip():
            raise ValueError("message must not be empty")
        ctx.confirmations.consume(
            "oneprovider_create_support_ticket",
            {
                "department": department,
                "message": message,
                "subject": subject,
                "server_id": server_id,
                "sub_department": sub_department,
                "confirmation_token": confirmation_token,
            },
            confirmation_token,
        )
        payload: dict[str, Any] = {"department": department, "message": message}
        if subject:
            payload["subject"] = subject
        if server_id:
            payload["server_id"] = server_id
        if sub_department:
            payload["sub_department"] = sub_department
        data = await ctx.client.post("/support/tickets", data=payload)
        return {
            "ok": True,
            "operation": "oneprovider_create_support_ticket",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_create_support_ticket",
        "Open a new support ticket with OneProvider support.",
        oneprovider_create_support_ticket,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_create_support_ticket"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_reply_support_ticket(
        ticket_id: str, message: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Reply to a support ticket. STATE-CHANGING.

        Args:
            ticket_id: The ticket ID.
            message: Reply message.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(ticket_id, name="ticket_id")
        if not message.strip():
            raise ValueError("message must not be empty")
        ctx.confirmations.consume(
            "oneprovider_reply_support_ticket",
            {"ticket_id": ticket_id, "message": message},
            confirmation_token,
        )
        data = await ctx.client.post(
            f"/support/tickets/{ticket_id}/reply", data={"message": message}
        )
        return {
            "ok": True,
            "operation": "oneprovider_reply_support_ticket",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_reply_support_ticket",
        "Reply to an open support ticket.",
        oneprovider_reply_support_ticket,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_reply_support_ticket"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_close_support_ticket(
        ticket_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Close an open support ticket. STATE-CHANGING.

        Args:
            ticket_id: The ticket ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(ticket_id, name="ticket_id")
        ctx.confirmations.consume(
            "oneprovider_close_support_ticket",
            {"ticket_id": ticket_id},
            confirmation_token,
        )
        data = await ctx.client.post(f"/support/tickets/{ticket_id}/close")
        return {
            "ok": True,
            "operation": "oneprovider_close_support_ticket",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_close_support_ticket",
        "Close an open support ticket.",
        oneprovider_close_support_ticket,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_close_support_ticket"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_reopen_support_ticket(
        ticket_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Reopen a closed support ticket. STATE-CHANGING.

        Args:
            ticket_id: The ticket ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(ticket_id, name="ticket_id")
        ctx.confirmations.consume(
            "oneprovider_reopen_support_ticket",
            {"ticket_id": ticket_id},
            confirmation_token,
        )
        data = await ctx.client.post(f"/support/tickets/{ticket_id}/reopen")
        return {
            "ok": True,
            "operation": "oneprovider_reopen_support_ticket",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_reopen_support_ticket",
        "Reopen a closed support ticket.",
        oneprovider_reopen_support_ticket,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_reopen_support_ticket"] = RiskTier.STATE_CHANGING.value

    return registered
