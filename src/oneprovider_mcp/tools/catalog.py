"""Store/catalog tools: configurations, locations, carts.

Verified endpoints:
- GET  /store/configs, /store/configs/{config_id},
       /store/configs/{config_id}/drives|softwares|upgrades,
       /store/configs/upgrades, /store/configs/cycles,
       /store/configs/locations
- GET/POST /store/carts, /store/carts/{cart_id},
       /store/carts/{cart_id}/clear,
       /store/carts/{cart_id}/items/{config_id}/add|remove,
       /store/carts/{cart_id}/update
"""

from __future__ import annotations

from typing import Any

from ..client import validate_id
from ..safety import RiskTier
from .types import AddToolFn, AppContext, MCPServer

_BILLING_CYCLES = {
    "1": "Monthly",
    "3": "Quarterly",
    "6": "Semi-Annually",
    "12": "Annually",
    "24": "Biennially",
    "36": "Triennially",
}


def register(server: MCPServer, ctx: AppContext, add: AddToolFn) -> dict[str, str]:
    registered: dict[str, str] = {}

    # ======================= read-only =======================

    async def oneprovider_list_catalog_configs(
        page: int = 1,
        limit: int = 20,
        config_ids: str | None = None,
        cpu_maker: str | None = None,
        core_amount: int | None = None,
        cpu_frequency: int | None = None,
        benchmark: int | None = None,
        memory: int | None = None,
        storage_amount: int | None = None,
        storage_port_type: str | None = None,
        storage_type: str | None = None,
        drive_amount: int | None = None,
        ip_amount: int | None = None,
        bandwidth_speed: int | None = None,
        bandwidth_limit: int | None = None,
        cities: str | None = None,
        countries: str | None = None,
        regions: str | None = None,
        sla_tier: int | None = None,
        upgrades: str | None = None,
        is_soldout: bool | None = None,
        is_in_promotion: bool | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        gpu_maker: str | None = None,
        gpu_model: str | None = None,
        vram: int | None = None,
        max_pages: int = 1,
    ) -> dict[str, Any]:
        """Search the dedicated-server catalog with rich filters. Read-only.

        Args:
            page: 1-based page. limit: 1..100.
            config_ids: Comma-separated config IDs.
            cpu_maker: ``AMD`` or ``Intel``.
            core_amount: Minimum CPU cores. cpu_frequency: Minimum MHz.
            benchmark: Minimum CPU benchmark.
            memory: Minimum RAM (MB). storage_amount: Minimum storage (GB).
            storage_port_type: ``SATA`` or ``SAS``.
            storage_type: ``HDD``, ``SSD`` or ``NVMe``.
            drive_amount: Minimum number of drives. ip_amount: Minimum IPs.
            bandwidth_speed: Minimum bandwidth (Mbps).
            bandwidth_limit: Minimum bandwidth quota (GB).
            cities/countries/regions: Comma-separated IDs.
            sla_tier: 1..5 (1=Platinum .. 5=Best Effort).
            upgrades: Comma-separated upgrade type IDs.
            is_soldout: Filter sold-out configs.
            is_in_promotion: Filter configs in promotion.
            min_price/max_price: Price bounds.
            gpu_maker: ``AMD`` or ``NVIDIA``. gpu_model: GPU name substring.
            vram: GPU RAM (GB).
            max_pages: Aggregate up to N pages (<=10) in one call.
        """
        if cpu_maker not in (None, "AMD", "Intel"):
            raise ValueError("cpu_maker must be AMD or Intel")
        if storage_port_type not in (None, "SATA", "SAS"):
            raise ValueError("storage_port_type must be SATA or SAS")
        if storage_type not in (None, "HDD", "SSD", "NVMe"):
            raise ValueError("storage_type must be HDD, SSD or NVMe")
        if gpu_maker not in (None, "AMD", "NVIDIA"):
            raise ValueError("gpu_maker must be AMD or NVIDIA")
        if sla_tier is not None and sla_tier not in (1, 2, 3, 4, 5):
            raise ValueError("sla_tier must be 1..5")
        params: dict[str, Any] = {
            "config_ids": config_ids,
            "cpu_maker": cpu_maker,
            "core_amount": core_amount,
            "cpu_frequency": cpu_frequency,
            "benchmark": benchmark,
            "memory": memory,
            "storage_amount": storage_amount,
            "storage_port_type": storage_port_type,
            "storage_type": storage_type,
            "drive_amount": drive_amount,
            "ip_amount": ip_amount,
            "bandwidth_speed": bandwidth_speed,
            "bandwidth_limit": bandwidth_limit,
            "cities": cities,
            "countries": countries,
            "regions": regions,
            "sla_tier": sla_tier,
            "upgrades": upgrades,
            "min_price": min_price,
            "max_price": max_price,
            "gpu_maker": gpu_maker,
            "gpu_model": gpu_model,
            "vram": vram,
        }
        if is_soldout is not None:
            params["is_soldout"] = int(is_soldout)
        if is_in_promotion is not None:
            params["is_in_promotion"] = int(is_in_promotion)
        data = await ctx.client.get_paginated(
            "/store/configs",
            entries_key="configs",
            page=page,
            limit=limit,
            params=params,
            max_pages=max_pages,
        )
        return {
            "ok": True,
            "operation": "oneprovider_list_catalog_configs",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_list_catalog_configs",
        "Search the OneProvider dedicated-server catalog (CPU/RAM/storage/GPU/price filters).",
        oneprovider_list_catalog_configs,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_catalog_configs"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_catalog_config(config_id: str) -> dict[str, Any]:
        """Get details of one catalog configuration. Read-only.

        Args:
            config_id: The configuration ID.
        """
        validate_id(config_id, name="config_id")
        data = await ctx.client.get(f"/store/configs/{config_id}")
        return {"ok": True, "operation": "oneprovider_get_catalog_config", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_get_catalog_config",
        "Get details of one catalog configuration (pricing, hardware).",
        oneprovider_get_catalog_config,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_catalog_config"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_config_drives(
        config_id: str, page: int = 1, limit: int = 20
    ) -> dict[str, Any]:
        """List selectable drives for a configuration. Read-only.

        Args:
            config_id: The configuration ID.
            page: 1-based page. limit: 1..100.
        """
        validate_id(config_id, name="config_id")
        data = await ctx.client.get_paginated(
            f"/store/configs/{config_id}/drives",
            entries_key="drives",
            page=page,
            limit=limit,
        )
        return {"ok": True, "operation": "oneprovider_list_config_drives", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_config_drives",
        "List selectable drive options for a catalog configuration.",
        oneprovider_list_config_drives,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_config_drives"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_config_softwares(
        config_id: str, page: int = 1, limit: int = 20
    ) -> dict[str, Any]:
        """List installable software for a configuration. Read-only.

        Args:
            config_id: The configuration ID.
            page: 1-based page. limit: 1..100.
        """
        validate_id(config_id, name="config_id")
        data = await ctx.client.get_paginated(
            f"/store/configs/{config_id}/softwares",
            entries_key="softwares",
            page=page,
            limit=limit,
        )
        return {
            "ok": True,
            "operation": "oneprovider_list_config_softwares",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_list_config_softwares",
        "List installable OS/software options for a catalog configuration.",
        oneprovider_list_config_softwares,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_config_softwares"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_config_upgrades(
        config_id: str, page: int = 1, limit: int = 20
    ) -> dict[str, Any]:
        """List available upgrade options for a configuration. Read-only.

        Args:
            config_id: The configuration ID.
            page: 1-based page. limit: 1..100.
        """
        validate_id(config_id, name="config_id")
        data = await ctx.client.get_paginated(
            f"/store/configs/{config_id}/upgrades",
            entries_key="upgrades",
            page=page,
            limit=limit,
        )
        return {
            "ok": True,
            "operation": "oneprovider_list_config_upgrades",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_list_config_upgrades",
        "List available upgrade options for a catalog configuration.",
        oneprovider_list_config_upgrades,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_config_upgrades"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_catalog_upgrades(page: int = 1, limit: int = 20) -> dict[str, Any]:
        """List upgrade types available across the catalog. Read-only.

        Args:
            page: 1-based page. limit: 1..100.
        """
        data = await ctx.client.get_paginated(
            "/store/configs/upgrades", entries_key="upgrades", page=page, limit=limit
        )
        return {
            "ok": True,
            "operation": "oneprovider_list_catalog_upgrades",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_list_catalog_upgrades",
        "List upgrade types available across the catalog.",
        oneprovider_list_catalog_upgrades,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_catalog_upgrades"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_billing_cycles(page: int = 1, limit: int = 20) -> dict[str, Any]:
        """List billing cycles available when ordering configs. Read-only.

        Args:
            page: 1-based page. limit: 1..100.
        """
        data = await ctx.client.get_paginated(
            "/store/configs/cycles", entries_key="cycles", page=page, limit=limit
        )
        return {
            "ok": True,
            "operation": "oneprovider_list_billing_cycles",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_list_billing_cycles",
        "List billing cycles (monthly/quarterly/...) available for ordering.",
        oneprovider_list_billing_cycles,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_billing_cycles"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_catalog_locations(
        page: int = 1,
        limit: int = 100,
        regions: str | None = None,
        countries: str | None = None,
    ) -> dict[str, Any]:
        """List datacenter locations where configurations are available.
        Read-only.

        Args:
            page: 1-based page. limit: 1..100.
            regions: Optional comma-separated region IDs.
            countries: Optional comma-separated country IDs.
        """
        data = await ctx.client.get_paginated(
            "/store/configs/locations",
            entries_key="locations",
            page=page,
            limit=limit,
            params={"regions": regions, "countries": countries},
        )
        return {
            "ok": True,
            "operation": "oneprovider_list_catalog_locations",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_list_catalog_locations",
        "List datacenter locations available for dedicated configurations.",
        oneprovider_list_catalog_locations,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_catalog_locations"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_carts(
        page: int = 1, limit: int = 20, status: str | None = None
    ) -> dict[str, Any]:
        """List your shopping carts. Read-only.

        Args:
            page: 1-based page. limit: 1..100.
            status: Optional filter ``Active`` or ``Ordered``.
        """
        if status not in (None, "Active", "Ordered"):
            raise ValueError("status must be 'Active' or 'Ordered'")
        data = await ctx.client.get_paginated(
            "/store/carts",
            entries_key="carts",
            page=page,
            limit=limit,
            params={"status": status},
        )
        return {"ok": True, "operation": "oneprovider_list_carts", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_carts",
        "List your OneProvider shopping carts.",
        oneprovider_list_carts,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_carts"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_cart(cart_id: str) -> dict[str, Any]:
        """Get a shopping cart's contents. Read-only.

        Args:
            cart_id: The cart ID.
        """
        validate_id(cart_id, name="cart_id")
        data = await ctx.client.get(f"/store/carts/{cart_id}")
        return {"ok": True, "operation": "oneprovider_get_cart", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_get_cart",
        "Get the contents of one shopping cart.",
        oneprovider_get_cart,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_cart"] = RiskTier.READ_ONLY.value

    # ======================= state-changing =======================

    async def oneprovider_create_or_get_cart(confirmation_token: str) -> dict[str, Any]:
        """Create a new shopping cart or return the current active one.
        STATE-CHANGING.

        Args:
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        ctx.confirmations.consume(
            "oneprovider_create_or_get_cart",
            {"confirmation_token": confirmation_token},
            confirmation_token,
        )
        data = await ctx.client.post("/store/carts")
        return {"ok": True, "operation": "oneprovider_create_or_get_cart", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_create_or_get_cart",
        "Create a shopping cart or return the current active one.",
        oneprovider_create_or_get_cart,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_create_or_get_cart"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_clear_cart(cart_id: str, confirmation_token: str) -> dict[str, Any]:
        """Empty and reset a cart's settings. STATE-CHANGING.

        Args:
            cart_id: The cart ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(cart_id, name="cart_id")
        ctx.confirmations.consume(
            "oneprovider_clear_cart", {"cart_id": cart_id}, confirmation_token
        )
        data = await ctx.client.post(f"/store/carts/{cart_id}/clear")
        return {"ok": True, "operation": "oneprovider_clear_cart", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_clear_cart",
        "Empty and reset a shopping cart.",
        oneprovider_clear_cart,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_clear_cart"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_add_cart_item(
        cart_id: str,
        config_id: str,
        quantity: int = 1,
        drives: str | None = None,
        software: str | None = None,
        upgrades: str | None = None,
        confirmation_token: str = "",
    ) -> dict[str, Any]:
        """Add or update an item in a cart. STATE-CHANGING (does not purchase).

        Args:
            cart_id: The cart ID.
            config_id: The configuration ID to add.
            quantity: Quantity (>=1).
            drives: Optional comma-separated drive IDs.
            software: Optional software ID (required when not self-install).
            upgrades: Optional JSON object mapping upgrade type ID -> choice ID,
                e.g. {"10": 1175}.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(cart_id, name="cart_id")
        validate_id(config_id, name="config_id")
        if quantity < 1:
            raise ValueError("quantity must be >= 1")
        ctx.confirmations.consume(
            "oneprovider_add_cart_item",
            {
                "cart_id": cart_id,
                "config_id": config_id,
                "quantity": quantity,
                "drives": drives,
                "software": software,
                "upgrades": upgrades,
                "confirmation_token": confirmation_token,
            },
            confirmation_token,
        )
        payload: dict[str, Any] = {"quantity": quantity}
        if drives:
            payload["drives"] = drives
        if software:
            payload["software"] = software
        if upgrades:
            payload["upgrades"] = upgrades
        data = await ctx.client.post(f"/store/carts/{cart_id}/items/{config_id}/add", data=payload)
        return {"ok": True, "operation": "oneprovider_add_cart_item", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_add_cart_item",
        "Add or update an item in a shopping cart (no purchase yet).",
        oneprovider_add_cart_item,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_add_cart_item"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_remove_cart_item(
        cart_id: str, config_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Remove an item from a cart. STATE-CHANGING.

        Args:
            cart_id: The cart ID.
            config_id: The configuration ID to remove.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(cart_id, name="cart_id")
        validate_id(config_id, name="config_id")
        ctx.confirmations.consume(
            "oneprovider_remove_cart_item",
            {"cart_id": cart_id, "config_id": config_id},
            confirmation_token,
        )
        data = await ctx.client.post(f"/store/carts/{cart_id}/items/{config_id}/remove")
        return {"ok": True, "operation": "oneprovider_remove_cart_item", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_remove_cart_item",
        "Remove an item from a shopping cart.",
        oneprovider_remove_cart_item,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_remove_cart_item"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_update_cart(
        cart_id: str,
        billing_cycle: str,
        promotion: str | None = None,
        confirmation_token: str = "",
    ) -> dict[str, Any]:
        """Update a cart's billing cycle (and optional promotion).
        STATE-CHANGING.

        Args:
            cart_id: The cart ID.
            billing_cycle: ``1`` Monthly, ``3`` Quarterly, ``6`` Semi-Annually,
                ``12`` Annually, ``24`` Biennially, ``36`` Triennially.
            promotion: Optional promotion code.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(cart_id, name="cart_id")
        if billing_cycle not in _BILLING_CYCLES:
            raise ValueError(f"billing_cycle must be one of {sorted(_BILLING_CYCLES)}")
        ctx.confirmations.consume(
            "oneprovider_update_cart",
            {
                "cart_id": cart_id,
                "billing_cycle": billing_cycle,
                "promotion": promotion,
                "confirmation_token": confirmation_token,
            },
            confirmation_token,
        )
        payload: dict[str, Any] = {"billing_cycle": billing_cycle}
        if promotion:
            payload["promotion"] = promotion
        data = await ctx.client.post(f"/store/carts/{cart_id}/update", data=payload)
        return {"ok": True, "operation": "oneprovider_update_cart", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_update_cart",
        "Update a cart's billing cycle / promotion.",
        oneprovider_update_cart,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_update_cart"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_cancel_order(order_id: str, confirmation_token: str) -> dict[str, Any]:
        """Send an order cancellation request. STATE-CHANGING.

        Args:
            order_id: The order ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(order_id, name="order_id")
        ctx.confirmations.consume(
            "oneprovider_cancel_order", {"order_id": order_id}, confirmation_token
        )
        data = await ctx.client.post(f"/store/orders/{order_id}/cancel")
        return {"ok": True, "operation": "oneprovider_cancel_order", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_cancel_order",
        "Send a cancellation request for an order.",
        oneprovider_cancel_order,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_cancel_order"] = RiskTier.STATE_CHANGING.value

    # ======================= destructive / financial =======================

    async def oneprovider_create_order(cart_id: str, confirmation_token: str) -> dict[str, Any]:
        """Create an order from a cart. FINANCIALLY CONSEQUENTIAL: this is a
        purchase request which may create payable invoices. Requires the
        destructive tier to be enabled plus a confirmation token.

        Args:
            cart_id: The cart ID to order.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(cart_id, name="cart_id")
        ctx.confirmations.consume(
            "oneprovider_create_order", {"cart_id": cart_id}, confirmation_token
        )
        data = await ctx.client.post("/store/orders", data={"cart_id": cart_id})
        return {
            "ok": True,
            "operation": "oneprovider_create_order",
            "data": data,
            "warning": "This created an order; check invoices via oneprovider_list_invoices.",
        }

    if add(
        server,
        ctx,
        "oneprovider_create_order",
        "FINANCIAL: create an order (purchase) from a shopping cart.",
        oneprovider_create_order,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_create_order"] = RiskTier.DESTRUCTIVE.value

    return registered
