"""Tag management tools.

Verified endpoints:
- GET  /tag/listing/{project_uuid}, /tag/{tag_id}
- POST /tag/add, /tag/edit, /tag/assign, /tag/unassign, /tag/remove
"""

from __future__ import annotations

from typing import Any

from ..client import validate_id
from ..safety import RiskTier
from .types import AddToolFn, AppContext, MCPServer


def register(server: MCPServer, ctx: AppContext, add: AddToolFn) -> dict[str, str]:
    registered: dict[str, str] = {}

    # ======================= read-only =======================

    async def oneprovider_list_tags(project_uuid: str | None = None) -> dict[str, Any]:
        """List tags, optionally scoped to a project. Read-only.

        Args:
            project_uuid: Optional project UUID scope.
        """
        path = "/tag/listing"
        if project_uuid:
            validate_id(project_uuid, name="project_uuid")
            path += f"/{project_uuid}"
        data = await ctx.client.get(path)
        return {"ok": True, "operation": "oneprovider_list_tags", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_tags",
        "List tags on the account (optionally scoped to a project).",
        oneprovider_list_tags,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_tags"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_tag(tag_id: str) -> dict[str, Any]:
        """Get one tag's detailed information. Read-only.

        Args:
            tag_id: The tag ID.
        """
        validate_id(tag_id, name="tag_id")
        data = await ctx.client.get(f"/tag/{tag_id}")
        return {"ok": True, "operation": "oneprovider_get_tag", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_get_tag",
        "Get detailed information about one tag.",
        oneprovider_get_tag,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_tag"] = RiskTier.READ_ONLY.value

    # ======================= state-changing =======================

    async def oneprovider_create_tag(
        label: str,
        description: str | None = None,
        project_uuid: str | None = None,
        confirmation_token: str = "",
    ) -> dict[str, Any]:
        """Create a new tag. STATE-CHANGING.

        Args:
            label: Tag name.
            description: Optional description.
            project_uuid: Optional project scope (empty = account-wide).
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        if not label.strip():
            raise ValueError("label must not be empty")
        if project_uuid:
            validate_id(project_uuid, name="project_uuid")
        ctx.confirmations.consume(
            "oneprovider_create_tag",
            {
                "label": label,
                "description": description,
                "project_uuid": project_uuid,
                "confirmation_token": confirmation_token,
            },
            confirmation_token,
        )
        payload: dict[str, Any] = {"label": label}
        if description:
            payload["description"] = description
        if project_uuid:
            payload["project_uuid"] = project_uuid
        data = await ctx.client.post("/tag/add", data=payload)
        return {"ok": True, "operation": "oneprovider_create_tag", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_create_tag",
        "Create a new tag.",
        oneprovider_create_tag,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_create_tag"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_edit_tag(
        tag_id: str,
        label: str,
        description: str | None = None,
        confirmation_token: str = "",
    ) -> dict[str, Any]:
        """Edit a tag's label/description. STATE-CHANGING.

        Args:
            tag_id: The tag ID.
            label: New tag name.
            description: New description.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(tag_id, name="tag_id")
        if not label.strip():
            raise ValueError("label must not be empty")
        ctx.confirmations.consume(
            "oneprovider_edit_tag",
            {
                "tag_id": tag_id,
                "label": label,
                "description": description,
                "confirmation_token": confirmation_token,
            },
            confirmation_token,
        )
        payload: dict[str, Any] = {"tag_id": tag_id, "label": label}
        if description:
            payload["description"] = description
        data = await ctx.client.post("/tag/edit", data=payload)
        return {"ok": True, "operation": "oneprovider_edit_tag", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_edit_tag",
        "Edit a tag's label/description.",
        oneprovider_edit_tag,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_edit_tag"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_assign_tag(
        tag_id: str, service_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Assign a tag to a server/VM. STATE-CHANGING.

        Args:
            tag_id: The tag ID.
            service_id: The server/VM ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(tag_id, name="tag_id")
        validate_id(service_id, name="service_id")
        ctx.confirmations.consume(
            "oneprovider_assign_tag",
            {"tag_id": tag_id, "service_id": service_id},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/tag/assign", data={"tag_id": tag_id, "service_id": service_id}
        )
        return {"ok": True, "operation": "oneprovider_assign_tag", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_assign_tag",
        "Assign a tag to a server/VM.",
        oneprovider_assign_tag,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_assign_tag"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_unassign_tag(
        tag_id: str, service_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Unassign a tag from a server/VM. STATE-CHANGING.

        Args:
            tag_id: The tag ID.
            service_id: The server/VM ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(tag_id, name="tag_id")
        validate_id(service_id, name="service_id")
        ctx.confirmations.consume(
            "oneprovider_unassign_tag",
            {"tag_id": tag_id, "service_id": service_id},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/tag/unassign", data={"tag_id": tag_id, "service_id": service_id}
        )
        return {"ok": True, "operation": "oneprovider_unassign_tag", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_unassign_tag",
        "Unassign a tag from a server/VM.",
        oneprovider_unassign_tag,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_unassign_tag"] = RiskTier.STATE_CHANGING.value

    # ======================= destructive =======================

    async def oneprovider_remove_tag(tag_id: str, confirmation_token: str) -> dict[str, Any]:
        """Delete a tag and all its assignments. DESTRUCTIVE.

        Args:
            tag_id: The tag ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(tag_id, name="tag_id")
        ctx.confirmations.consume("oneprovider_remove_tag", {"tag_id": tag_id}, confirmation_token)
        data = await ctx.client.post("/tag/remove", data={"tag_id": tag_id})
        return {"ok": True, "operation": "oneprovider_remove_tag", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_remove_tag",
        "DESTRUCTIVE: delete a tag and all its assignments.",
        oneprovider_remove_tag,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_remove_tag"] = RiskTier.DESTRUCTIVE.value

    return registered
