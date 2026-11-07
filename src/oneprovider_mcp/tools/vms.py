"""OneCloud VM tools.

Verified endpoints (OneProvider Postman collection, official):
- GET  /vm/project/list, /vm/listing/{project_uuid}, /vm/info/{vm_id},
       /vm/info?ip=..., /vm/templates, /vm/locations, /vm/sizes,
       /vm/sshkeys/list, /vm/images/list
- POST /vm/rdns/get (read semantics), /vm/boot, /vm/shutdown, /vm/reboot,
       /vm/poweroff, /vm/hostname, /vm/bootorder, /vm/pae, /vm/mountiso,
       /vm/unmountiso, /vm/rescue/enable, /vm/rescue/disable,
       /vm/ipv6/enable, /vm/bandwidth/suspend, /vm/addon/add,
       /vm/addon/remove, /vm/sshkey/new, /vm/sshkey/edit,
       /vm/sshkey/delete, /vm/sshkeys/assign, /vm/rdns/add, /vm/rdns/edit,
       /vm/rdns/delete, /vm/image/create, /vm/image/delete,
       /vm/image/rename, /vm/restore, /vm/password, /vm/vnc,
       /vm/vnc/password, /vm/project/new, /vm/project/edit,
       /vm/project/assign, /vm/project/delete, /vm/create, /vm/resize,
       /vm/reinstall, /vm/destroy
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from ..client import validate_id
from ..safety import RiskTier
from .types import AddToolFn, AppContext, MCPServer

_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-.]{0,251}[A-Za-z0-9])?$")


def _valid_ip(value: str, name: str = "ip") -> str:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {name}: {value!r} is not an IP address") from exc
    return value


def register(server: MCPServer, ctx: AppContext, add: AddToolFn) -> dict[str, str]:
    registered: dict[str, str] = {}

    # ======================= read-only =======================

    async def oneprovider_list_vm_projects() -> dict[str, Any]:
        """List all OneCloud projects on the account. Read-only."""
        data = await ctx.client.get("/vm/project/list")
        return {"ok": True, "operation": "oneprovider_list_vm_projects", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_vm_projects",
        "List OneCloud projects (project UUIDs used to group instances).",
        oneprovider_list_vm_projects,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_vm_projects"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_vms(project_uuid: str | None = None) -> dict[str, Any]:
        """List virtual servers, aggregated across all projects (or for one
        project). Read-only.

        Args:
            project_uuid: Optional project UUID to scope the listing.
        """
        if project_uuid is None:
            projects = await ctx.client.get("/vm/project/list")
            plist = projects.get("projects", []) if isinstance(projects, dict) else []
            aggregated: list[Any] = []
            project_count = 0
            for p in plist:
                uuid = p.get("uuid") if isinstance(p, dict) else None
                if not uuid:
                    continue
                project_count += 1
                try:
                    listing = await ctx.client.get(f"/vm/listing/{uuid}")
                except Exception as exc:  # keep going; report per-project failure
                    aggregated.append({"project_uuid": uuid, "error": str(exc)})
                    continue
                if isinstance(listing, dict):
                    vms = listing.get("vms", listing.get("instances", []))
                    aggregated.extend(vms if isinstance(vms, list) else [listing])
                elif isinstance(listing, list):
                    aggregated.extend(listing)
            return {
                "ok": True,
                "operation": "oneprovider_list_vms",
                "projects_scanned": project_count,
                "data": aggregated,
            }
        validate_id(project_uuid, name="project_uuid")
        data = await ctx.client.get(f"/vm/listing/{project_uuid}")
        return {"ok": True, "operation": "oneprovider_list_vms", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_vms",
        "List OneCloud virtual servers across all projects (or one project).",
        oneprovider_list_vms,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_vms"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_vm(vm_id: str) -> dict[str, Any]:
        """Get a virtual server's full information: status, templates, ISO
        images, IPs. Read-only.

        Args:
            vm_id: The virtual server ID.
        """
        validate_id(vm_id, name="vm_id")
        data = await ctx.client.get(f"/vm/info/{vm_id}")
        return {"ok": True, "operation": "oneprovider_get_vm", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_get_vm",
        "Get a virtual server's information: status, IPs, available templates and ISOs.",
        oneprovider_get_vm,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_vm"] = RiskTier.READ_ONLY.value

    async def oneprovider_search_vm_by_ip(
        ip: str, project_uuid: str | None = None
    ) -> dict[str, Any]:
        """Find a virtual server by its IP address. Read-only.

        Args:
            ip: The VM's IP address.
            project_uuid: Optional project UUID to scope the search.
        """
        _valid_ip(ip)
        params: dict[str, Any] = {"ip": ip}
        if project_uuid:
            validate_id(project_uuid, name="project_uuid")
            params["project_uuid"] = project_uuid
        data = await ctx.client.get("/vm/info", params=params)
        return {"ok": True, "operation": "oneprovider_search_vm_by_ip", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_search_vm_by_ip",
        "Find a OneCloud virtual server by its IP address.",
        oneprovider_search_vm_by_ip,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_search_vm_by_ip"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_vm_templates() -> dict[str, Any]:
        """List available OS templates for OneCloud instances. Read-only."""
        data = await ctx.client.get("/vm/templates")
        return {"ok": True, "operation": "oneprovider_list_vm_templates", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_vm_templates",
        "List available OS templates for OneCloud instances.",
        oneprovider_list_vm_templates,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_vm_templates"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_vm_locations() -> dict[str, Any]:
        """List available OneCloud locations. Read-only."""
        data = await ctx.client.get("/vm/locations")
        return {"ok": True, "operation": "oneprovider_list_vm_locations", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_vm_locations",
        "List available OneCloud locations.",
        oneprovider_list_vm_locations,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_vm_locations"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_vm_sizes() -> dict[str, Any]:
        """List available OneCloud instance sizes (plans) with prices and
        addon definitions. Read-only."""
        data = await ctx.client.get("/vm/sizes")
        return {"ok": True, "operation": "oneprovider_list_vm_sizes", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_vm_sizes",
        "List available OneCloud instance sizes/plans (CPU, RAM, prices, addons).",
        oneprovider_list_vm_sizes,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_vm_sizes"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_ssh_keys() -> dict[str, Any]:
        """List SSH public keys registered on the account. Read-only."""
        data = await ctx.client.get("/vm/sshkeys/list")
        return {"ok": True, "operation": "oneprovider_list_ssh_keys", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_ssh_keys",
        "List SSH public keys registered on the account.",
        oneprovider_list_ssh_keys,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_ssh_keys"] = RiskTier.READ_ONLY.value

    async def oneprovider_list_vm_images() -> dict[str, Any]:
        """List saved images (snapshots) of your instances. Read-only."""
        data = await ctx.client.get("/vm/images/list")
        return {"ok": True, "operation": "oneprovider_list_vm_images", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_list_vm_images",
        "List saved images/snapshots of your OneCloud instances.",
        oneprovider_list_vm_images,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_list_vm_images"] = RiskTier.READ_ONLY.value

    async def oneprovider_get_vm_rdns(ip: str) -> dict[str, Any]:
        """Get the reverse DNS (PTR) record associated with an IP.
        Read-only semantics (documented as a POST endpoint by the API).

        Args:
            ip: The IP address to query.
        """
        _valid_ip(ip)
        data = await ctx.client.post("/vm/rdns/get", data={"ip": ip})
        return {"ok": True, "operation": "oneprovider_get_vm_rdns", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_get_vm_rdns",
        "Get the reverse DNS (PTR) record for an IP. Read-only despite the POST verb.",
        oneprovider_get_vm_rdns,
        RiskTier.READ_ONLY,
        idempotent=True,
    ):
        registered["oneprovider_get_vm_rdns"] = RiskTier.READ_ONLY.value

    # ======================= state-changing =======================

    async def oneprovider_boot_vm(vm_id: str, confirmation_token: str) -> dict[str, Any]:
        """Boot (power on) a virtual server. STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        ctx.confirmations.consume("oneprovider_boot_vm", {"vm_id": vm_id}, confirmation_token)
        data = await ctx.client.post("/vm/boot", data={"vm_id": vm_id})
        return {"ok": True, "operation": "oneprovider_boot_vm", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_boot_vm",
        "Boot (power on) a OneCloud virtual server.",
        oneprovider_boot_vm,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_boot_vm"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_shutdown_vm(vm_id: str, confirmation_token: str) -> dict[str, Any]:
        """Gracefully shut down a virtual server (waits for processes).
        STATE-CHANGING: interrupts service.

        Args:
            vm_id: The virtual server ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        ctx.confirmations.consume("oneprovider_shutdown_vm", {"vm_id": vm_id}, confirmation_token)
        data = await ctx.client.post("/vm/shutdown", data={"vm_id": vm_id})
        return {"ok": True, "operation": "oneprovider_shutdown_vm", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_shutdown_vm",
        "Gracefully shut down a OneCloud virtual server.",
        oneprovider_shutdown_vm,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_shutdown_vm"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_reboot_vm(vm_id: str, confirmation_token: str) -> dict[str, Any]:
        """Reboot a virtual server. STATE-CHANGING: interrupts service.

        Args:
            vm_id: The virtual server ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        ctx.confirmations.consume("oneprovider_reboot_vm", {"vm_id": vm_id}, confirmation_token)
        data = await ctx.client.post("/vm/reboot", data={"vm_id": vm_id})
        return {"ok": True, "operation": "oneprovider_reboot_vm", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_reboot_vm",
        "Reboot a OneCloud virtual server.",
        oneprovider_reboot_vm,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_reboot_vm"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_force_poweroff_vm(vm_id: str, confirmation_token: str) -> dict[str, Any]:
        """Force power-off a virtual server WITHOUT waiting for processes
        (equivalent to pulling the plug; may corrupt data).
        STATE-CHANGING, destructive-flavored.

        Args:
            vm_id: The virtual server ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        ctx.confirmations.consume(
            "oneprovider_force_poweroff_vm", {"vm_id": vm_id}, confirmation_token
        )
        data = await ctx.client.post("/vm/poweroff", data={"vm_id": vm_id})
        return {"ok": True, "operation": "oneprovider_force_poweroff_vm", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_force_poweroff_vm",
        "Force power-off a OneCloud VM (hard off; does not wait for processes).",
        oneprovider_force_poweroff_vm,
        RiskTier.STATE_CHANGING,
        destructive=True,
    ):
        registered["oneprovider_force_poweroff_vm"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_set_vm_hostname(
        vm_id: str, hostname: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Change a virtual server's hostname. STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            hostname: New hostname.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        if not _HOSTNAME_RE.match(hostname):
            raise ValueError("hostname contains invalid characters")
        ctx.confirmations.consume(
            "oneprovider_set_vm_hostname",
            {"vm_id": vm_id, "hostname": hostname},
            confirmation_token,
        )
        data = await ctx.client.post("/vm/hostname", data={"vm_id": vm_id, "hostname": hostname})
        return {"ok": True, "operation": "oneprovider_set_vm_hostname", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_set_vm_hostname",
        "Change a OneCloud VM's hostname.",
        oneprovider_set_vm_hostname,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_set_vm_hostname"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_set_vm_boot_order(
        vm_id: str, bootorder: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Change a VM's boot device order. Allowed values: ``cda``
        (1:Hard Disk, 2:CDROM) or ``dca`` (1:CDROM, 2:Hard Disk).
        STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            bootorder: ``cda`` or ``dca``.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        if bootorder not in ("cda", "dca"):
            raise ValueError("bootorder must be 'cda' or 'dca'")
        ctx.confirmations.consume(
            "oneprovider_set_vm_boot_order",
            {"vm_id": vm_id, "bootorder": bootorder},
            confirmation_token,
        )
        data = await ctx.client.post("/vm/bootorder", data={"vm_id": vm_id, "bootorder": bootorder})
        return {"ok": True, "operation": "oneprovider_set_vm_boot_order", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_set_vm_boot_order",
        "Change a OneCloud VM's boot order (cda = disk first, dca = CDROM first).",
        oneprovider_set_vm_boot_order,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_set_vm_boot_order"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_set_vm_pae(
        vm_id: str, pae: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Turn PAE (Physical Address Extension) on/off on a VM.
        STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            pae: ``on`` or ``off``.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        if pae not in ("on", "off"):
            raise ValueError("pae must be 'on' or 'off'")
        ctx.confirmations.consume(
            "oneprovider_set_vm_pae", {"vm_id": vm_id, "pae": pae}, confirmation_token
        )
        data = await ctx.client.post("/vm/pae", data={"vm_id": vm_id, "pae": pae})
        return {"ok": True, "operation": "oneprovider_set_vm_pae", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_set_vm_pae",
        "Toggle PAE on/off on a OneCloud VM.",
        oneprovider_set_vm_pae,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_set_vm_pae"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_mount_vm_iso(
        vm_id: str, iso: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Mount an ISO image on a virtual server (ISO list is in
        oneprovider_get_vm output). STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            iso: ISO identifier from the VM's info.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        validate_id(iso, name="iso")
        ctx.confirmations.consume(
            "oneprovider_mount_vm_iso", {"vm_id": vm_id, "iso": iso}, confirmation_token
        )
        data = await ctx.client.post("/vm/mountiso", data={"vm_id": vm_id, "iso": iso})
        return {"ok": True, "operation": "oneprovider_mount_vm_iso", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_mount_vm_iso",
        "Mount an ISO image on a OneCloud VM.",
        oneprovider_mount_vm_iso,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_mount_vm_iso"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_unmount_vm_iso(vm_id: str, confirmation_token: str) -> dict[str, Any]:
        """Unmount the ISO image from a virtual server. STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        ctx.confirmations.consume(
            "oneprovider_unmount_vm_iso", {"vm_id": vm_id}, confirmation_token
        )
        data = await ctx.client.post("/vm/unmountiso", data={"vm_id": vm_id})
        return {"ok": True, "operation": "oneprovider_unmount_vm_iso", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_unmount_vm_iso",
        "Unmount the ISO from a OneCloud VM.",
        oneprovider_unmount_vm_iso,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_unmount_vm_iso"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_enable_vm_rescue_mode(
        vm_id: str, password: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Enable rescue mode on a VM with the given rescue password.
        STATE-CHANGING: reboots the VM into the rescue environment.

        Args:
            vm_id: The virtual server ID.
            password: Password used to access the rescue environment.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        if len(password) < 8:
            raise ValueError("rescue password must be at least 8 characters")
        ctx.confirmations.consume(
            "oneprovider_enable_vm_rescue_mode",
            {"vm_id": vm_id, "password": password},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/rescue/enable", data={"vm_id": vm_id, "password": password}
        )
        return {
            "ok": True,
            "operation": "oneprovider_enable_vm_rescue_mode",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_enable_vm_rescue_mode",
        "Enable rescue mode on a OneCloud VM (reboots into rescue environment).",
        oneprovider_enable_vm_rescue_mode,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_enable_vm_rescue_mode"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_disable_vm_rescue_mode(
        vm_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Disable rescue mode on a VM. STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        ctx.confirmations.consume(
            "oneprovider_disable_vm_rescue_mode", {"vm_id": vm_id}, confirmation_token
        )
        data = await ctx.client.post("/vm/rescue/disable", data={"vm_id": vm_id})
        return {
            "ok": True,
            "operation": "oneprovider_disable_vm_rescue_mode",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_disable_vm_rescue_mode",
        "Disable rescue mode on a OneCloud VM.",
        oneprovider_disable_vm_rescue_mode,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_disable_vm_rescue_mode"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_enable_vm_ipv6(vm_id: str, confirmation_token: str) -> dict[str, Any]:
        """Enable IPv6 on a virtual server (adds an addon). STATE-CHANGING
        (may have billing implications).

        Args:
            vm_id: The virtual server ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        ctx.confirmations.consume(
            "oneprovider_enable_vm_ipv6", {"vm_id": vm_id}, confirmation_token
        )
        data = await ctx.client.post("/vm/ipv6/enable", data={"vm_id": vm_id})
        return {"ok": True, "operation": "oneprovider_enable_vm_ipv6", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_enable_vm_ipv6",
        "Enable IPv6 on a OneCloud VM (addon; may have billing implications).",
        oneprovider_enable_vm_ipv6,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_enable_vm_ipv6"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_set_vm_bandwidth_suspend(
        vm_id: str, toggle_to: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Toggle automatic bandwidth suspension when the traffic limit is
        reached. STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            toggle_to: ``on`` or ``off``.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        if toggle_to not in ("on", "off"):
            raise ValueError("toggle_to must be 'on' or 'off'")
        ctx.confirmations.consume(
            "oneprovider_set_vm_bandwidth_suspend",
            {"vm_id": vm_id, "toggle_to": toggle_to},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/bandwidth/suspend", data={"vm_id": vm_id, "toggleTo": toggle_to}
        )
        return {
            "ok": True,
            "operation": "oneprovider_set_vm_bandwidth_suspend",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_set_vm_bandwidth_suspend",
        "Toggle auto-suspension of a VM when its bandwidth limit is reached (on/off).",
        oneprovider_set_vm_bandwidth_suspend,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_set_vm_bandwidth_suspend"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_add_vm_addon(
        vm_id: str, addon_name: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Add an addon to a VM. STATE-CHANGING and potentially billable.

        Args:
            vm_id: The virtual server ID.
            addon_name: Addon name (from oneprovider_list_vm_sizes addons).
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        validate_id(addon_name, name="addon_name")
        ctx.confirmations.consume(
            "oneprovider_add_vm_addon",
            {"vm_id": vm_id, "addon_name": addon_name},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/addon/add", data={"vm_id": vm_id, "addon_name": addon_name}
        )
        return {"ok": True, "operation": "oneprovider_add_vm_addon", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_add_vm_addon",
        "Add an addon to a OneCloud VM (may incur charges).",
        oneprovider_add_vm_addon,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_add_vm_addon"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_remove_vm_addon(
        vm_id: str, addon_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Remove an addon from a VM (addon IDs come from
        oneprovider_get_vm). STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            addon_id: The addon ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        validate_id(addon_id, name="addon_id")
        ctx.confirmations.consume(
            "oneprovider_remove_vm_addon",
            {"vm_id": vm_id, "addon_id": addon_id},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/addon/remove", data={"vm_id": vm_id, "addon_id": addon_id}
        )
        return {"ok": True, "operation": "oneprovider_remove_vm_addon", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_remove_vm_addon",
        "Remove an addon from a OneCloud VM.",
        oneprovider_remove_vm_addon,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_remove_vm_addon"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_create_ssh_key(
        key_name: str, key_value: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Register a new SSH public key on the account. STATE-CHANGING.

        Args:
            key_name: Display name for the key.
            key_value: The public key material (e.g. ``ssh-ed25519 AAAA...``).
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        if not key_name.strip():
            raise ValueError("key_name must not be empty")
        if not (
            key_value.startswith("ssh-")
            or key_value.startswith("ecdsa-")
            or key_value.startswith("sk-")
        ):
            raise ValueError("key_value does not look like a public SSH key")
        ctx.confirmations.consume(
            "oneprovider_create_ssh_key",
            {"key_name": key_name, "key_value": key_value},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/sshkey/new", data={"key_name": key_name, "key_value": key_value}
        )
        return {"ok": True, "operation": "oneprovider_create_ssh_key", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_create_ssh_key",
        "Register a new SSH public key on the account.",
        oneprovider_create_ssh_key,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_create_ssh_key"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_edit_ssh_key(
        ssh_key: str, key_name: str, key_value: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Edit an SSH key's name and/or value. STATE-CHANGING.

        Args:
            ssh_key: The SSH key UUID.
            key_name: New name.
            key_value: New public key material.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(ssh_key, name="ssh_key")
        ctx.confirmations.consume(
            "oneprovider_edit_ssh_key",
            {"ssh_key": ssh_key, "key_name": key_name, "key_value": key_value},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/sshkey/edit",
            data={"ssh_key": ssh_key, "key_name": key_name, "key_value": key_value},
        )
        return {"ok": True, "operation": "oneprovider_edit_ssh_key", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_edit_ssh_key",
        "Edit an SSH key's name/value on the account.",
        oneprovider_edit_ssh_key,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_edit_ssh_key"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_assign_ssh_keys_to_vm(
        vm_id: str, ssh_keys: list[str], confirmation_token: str
    ) -> dict[str, Any]:
        """Assign one or more SSH keys (UUIDs) to a VM. STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            ssh_keys: List of SSH key UUIDs.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        for k in ssh_keys:
            validate_id(k, name="ssh_keys[]")
        ctx.confirmations.consume(
            "oneprovider_assign_ssh_keys_to_vm",
            {"vm_id": vm_id, "ssh_keys": ssh_keys},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/sshkeys/assign", data={"vm_id": vm_id, "ssh_keys": ssh_keys}
        )
        return {
            "ok": True,
            "operation": "oneprovider_assign_ssh_keys_to_vm",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_assign_ssh_keys_to_vm",
        "Assign SSH keys to a OneCloud VM.",
        oneprovider_assign_ssh_keys_to_vm,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_assign_ssh_keys_to_vm"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_set_vm_rdns(
        ip: str, domain: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Set (add) a reverse DNS record for an IP. STATE-CHANGING.

        Args:
            ip: The IP address.
            domain: The PTR domain name to associate.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        _valid_ip(ip)
        if not _HOSTNAME_RE.match(domain):
            raise ValueError("domain contains invalid characters")
        ctx.confirmations.consume(
            "oneprovider_set_vm_rdns", {"ip": ip, "domain": domain}, confirmation_token
        )
        data = await ctx.client.post("/vm/rdns/add", data={"ip": ip, "domain": domain})
        return {"ok": True, "operation": "oneprovider_set_vm_rdns", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_set_vm_rdns",
        "Set a reverse DNS (PTR) record for an IP.",
        oneprovider_set_vm_rdns,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_set_vm_rdns"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_edit_vm_rdns(
        ip: str, domain: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Edit an existing reverse DNS record for an IP. STATE-CHANGING.

        Args:
            ip: The IP address.
            domain: The new PTR domain name.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        _valid_ip(ip)
        if not _HOSTNAME_RE.match(domain):
            raise ValueError("domain contains invalid characters")
        ctx.confirmations.consume(
            "oneprovider_edit_vm_rdns", {"ip": ip, "domain": domain}, confirmation_token
        )
        data = await ctx.client.post("/vm/rdns/edit", data={"ip": ip, "domain": domain})
        return {"ok": True, "operation": "oneprovider_edit_vm_rdns", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_edit_vm_rdns",
        "Edit a reverse DNS (PTR) record for an IP.",
        oneprovider_edit_vm_rdns,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_edit_vm_rdns"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_create_vm_image(vm_id: str, confirmation_token: str) -> dict[str, Any]:
        """Create a saved image (snapshot) from an instance. STATE-CHANGING;
        image storage may be billed.

        Args:
            vm_id: The virtual server ID to snapshot.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        ctx.confirmations.consume(
            "oneprovider_create_vm_image", {"vm_id": vm_id}, confirmation_token
        )
        data = await ctx.client.post("/vm/image/create", data={"vm_id": vm_id})
        return {"ok": True, "operation": "oneprovider_create_vm_image", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_create_vm_image",
        "Create a saved image (snapshot) from a OneCloud instance (storage may be billed).",
        oneprovider_create_vm_image,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_create_vm_image"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_rename_vm_image(
        image: str, new_name: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Rename a saved image. STATE-CHANGING.

        Args:
            image: The image ID.
            new_name: New display name.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(image, name="image")
        if not new_name.strip():
            raise ValueError("new_name must not be empty")
        ctx.confirmations.consume(
            "oneprovider_rename_vm_image",
            {"image": image, "new_name": new_name},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/image/rename", data={"image": image, "new_name": new_name}
        )
        return {"ok": True, "operation": "oneprovider_rename_vm_image", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_rename_vm_image",
        "Rename a saved VM image.",
        oneprovider_rename_vm_image,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_rename_vm_image"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_get_vnc_credentials(
        vm_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Get VNC session credentials for a VM. Read-semantics but exposed
        via POST and may issue fresh credentials; gated behind the write
        tier. Result contains a password -- treat as sensitive.

        Args:
            vm_id: The virtual server ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        ctx.confirmations.consume(
            "oneprovider_get_vnc_credentials", {"vm_id": vm_id}, confirmation_token
        )
        data = await ctx.client.post("/vm/vnc", data={"vm_id": vm_id})
        return {
            "ok": True,
            "operation": "oneprovider_get_vnc_credentials",
            "data": data,
            "warning": "VNC credentials are sensitive; do not store or share.",
        }

    if add(
        server,
        ctx,
        "oneprovider_get_vnc_credentials",
        "Get VNC session credentials for a OneCloud VM (sensitive output).",
        oneprovider_get_vnc_credentials,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_get_vnc_credentials"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_set_vnc_password(
        vm_id: str, password: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Change a VM's VNC session password. STATE-CHANGING.

        Args:
            vm_id: The virtual server ID.
            password: New VNC password (min 8 chars).
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        ctx.confirmations.consume(
            "oneprovider_set_vnc_password",
            {"vm_id": vm_id, "password": password},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/vnc/password", data={"vm_id": vm_id, "password": password}
        )
        return {"ok": True, "operation": "oneprovider_set_vnc_password", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_set_vnc_password",
        "Change a OneCloud VM's VNC password.",
        oneprovider_set_vnc_password,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_set_vnc_password"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_set_vm_root_password(
        vm_id: str, password: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Change a VM's root password. STATE-CHANGING and sensitive.

        Args:
            vm_id: The virtual server ID.
            password: New root password (min 8 chars).
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        ctx.confirmations.consume(
            "oneprovider_set_vm_root_password",
            {"vm_id": vm_id, "password": password},
            confirmation_token,
        )
        data = await ctx.client.post("/vm/password", data={"vm_id": vm_id, "password": password})
        return {
            "ok": True,
            "operation": "oneprovider_set_vm_root_password",
            "data": data,
            "warning": "Root password changed; store it securely.",
        }

    if add(
        server,
        ctx,
        "oneprovider_set_vm_root_password",
        "Change a OneCloud VM's root password (sensitive).",
        oneprovider_set_vm_root_password,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_set_vm_root_password"] = RiskTier.STATE_CHANGING.value

    # ---- projects ----

    async def oneprovider_create_project(
        name: str, is_default: bool = False, confirmation_token: str = ""
    ) -> dict[str, Any]:
        """Create a new OneCloud project. STATE-CHANGING.

        Args:
            name: Project name.
            is_default: Make this the new default project.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        if not name.strip():
            raise ValueError("name must not be empty")
        ctx.confirmations.consume(
            "oneprovider_create_project",
            {
                "name": name,
                "is_default": is_default,
                "confirmation_token": confirmation_token,
            },
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/project/new", data={"name": name, "is_default": int(is_default)}
        )
        return {"ok": True, "operation": "oneprovider_create_project", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_create_project",
        "Create a OneCloud project.",
        oneprovider_create_project,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_create_project"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_edit_project(
        project_uuid: str,
        name: str | None = None,
        is_default: bool | None = None,
        confirmation_token: str = "",
    ) -> dict[str, Any]:
        """Edit a project's name or default flag. STATE-CHANGING.

        Args:
            project_uuid: The project UUID.
            name: New name (optional).
            is_default: Make default (optional).
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(project_uuid, name="project_uuid")
        if name is None and is_default is None:
            raise ValueError("Provide at least one of name / is_default")
        ctx.confirmations.consume(
            "oneprovider_edit_project",
            {
                "project_uuid": project_uuid,
                "name": name,
                "is_default": is_default,
                "confirmation_token": confirmation_token,
            },
            confirmation_token,
        )
        payload: dict[str, Any] = {"project_uuid": project_uuid}
        if name is not None:
            payload["name"] = name
        if is_default is not None:
            payload["is_default"] = int(is_default)
        data = await ctx.client.post("/vm/project/edit", data=payload)
        return {"ok": True, "operation": "oneprovider_edit_project", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_edit_project",
        "Edit a OneCloud project's name or default flag.",
        oneprovider_edit_project,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_edit_project"] = RiskTier.STATE_CHANGING.value

    async def oneprovider_assign_vm_to_project(
        project_uuid: str, instance_id: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Move an instance to a different project. STATE-CHANGING.

        Args:
            project_uuid: Destination project UUID.
            instance_id: The VM ID to move.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(project_uuid, name="project_uuid")
        validate_id(instance_id, name="instance_id")
        ctx.confirmations.consume(
            "oneprovider_assign_vm_to_project",
            {"project_uuid": project_uuid, "instance_id": instance_id},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/project/assign",
            data={"project_uuid": project_uuid, "instance_id": instance_id},
        )
        return {
            "ok": True,
            "operation": "oneprovider_assign_vm_to_project",
            "data": data,
        }

    if add(
        server,
        ctx,
        "oneprovider_assign_vm_to_project",
        "Move a OneCloud instance to a different project.",
        oneprovider_assign_vm_to_project,
        RiskTier.STATE_CHANGING,
    ):
        registered["oneprovider_assign_vm_to_project"] = RiskTier.STATE_CHANGING.value

    # ======================= destructive =======================

    async def oneprovider_delete_ssh_key(ssh_key: str, confirmation_token: str) -> dict[str, Any]:
        """Delete an SSH key from the account. DESTRUCTIVE.

        Args:
            ssh_key: The SSH key UUID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(ssh_key, name="ssh_key")
        ctx.confirmations.consume(
            "oneprovider_delete_ssh_key", {"ssh_key": ssh_key}, confirmation_token
        )
        data = await ctx.client.post("/vm/sshkey/delete", data={"ssh_key": ssh_key})
        return {"ok": True, "operation": "oneprovider_delete_ssh_key", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_delete_ssh_key",
        "DESTRUCTIVE: delete an SSH key from the account.",
        oneprovider_delete_ssh_key,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_delete_ssh_key"] = RiskTier.DESTRUCTIVE.value

    async def oneprovider_delete_vm_rdns(ip: str, confirmation_token: str) -> dict[str, Any]:
        """Delete the reverse DNS record of an IP. DESTRUCTIVE.

        Args:
            ip: The IP address.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        _valid_ip(ip)
        ctx.confirmations.consume("oneprovider_delete_vm_rdns", {"ip": ip}, confirmation_token)
        data = await ctx.client.post("/vm/rdns/delete", data={"ip": ip})
        return {"ok": True, "operation": "oneprovider_delete_vm_rdns", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_delete_vm_rdns",
        "DESTRUCTIVE: delete a reverse DNS (PTR) record.",
        oneprovider_delete_vm_rdns,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_delete_vm_rdns"] = RiskTier.DESTRUCTIVE.value

    async def oneprovider_delete_vm_image(image: str, confirmation_token: str) -> dict[str, Any]:
        """Delete a saved image. DESTRUCTIVE: the image cannot be recovered.

        Args:
            image: The image ID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(image, name="image")
        ctx.confirmations.consume(
            "oneprovider_delete_vm_image", {"image": image}, confirmation_token
        )
        data = await ctx.client.post("/vm/image/delete", data={"image": image})
        return {"ok": True, "operation": "oneprovider_delete_vm_image", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_delete_vm_image",
        "DESTRUCTIVE: delete a saved VM image.",
        oneprovider_delete_vm_image,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_delete_vm_image"] = RiskTier.DESTRUCTIVE.value

    async def oneprovider_restore_vm_image(
        vm_id: str, image: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Restore an image onto an instance. DESTRUCTIVE: replaces the
        instance's current disk contents.

        Args:
            vm_id: The virtual server ID.
            image: The image ID to restore.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        validate_id(image, name="image")
        ctx.confirmations.consume(
            "oneprovider_restore_vm_image",
            {"vm_id": vm_id, "image": image},
            confirmation_token,
        )
        data = await ctx.client.post("/vm/restore", data={"vm_id": vm_id, "image": image})
        return {"ok": True, "operation": "oneprovider_restore_vm_image", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_restore_vm_image",
        "DESTRUCTIVE: restore an image onto a OneCloud instance (overwrites disk).",
        oneprovider_restore_vm_image,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_restore_vm_image"] = RiskTier.DESTRUCTIVE.value

    async def oneprovider_delete_project(
        project_uuid: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Delete a project (must be empty). DESTRUCTIVE.

        Args:
            project_uuid: The project UUID.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(project_uuid, name="project_uuid")
        ctx.confirmations.consume(
            "oneprovider_delete_project",
            {"project_uuid": project_uuid},
            confirmation_token,
        )
        data = await ctx.client.post("/vm/project/delete", data={"project_uuid": project_uuid})
        return {"ok": True, "operation": "oneprovider_delete_project", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_delete_project",
        "DESTRUCTIVE: delete an empty OneCloud project.",
        oneprovider_delete_project,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_delete_project"] = RiskTier.DESTRUCTIVE.value

    async def oneprovider_reinstall_vm(
        vm_id: str,
        template: str,
        ssh_keys: list[str] | None = None,
        confirmation_token: str = "",
    ) -> dict[str, Any]:
        """Reinstall a VM's OS from a template or image. DESTRUCTIVE: all
        data on the instance is lost.

        Args:
            vm_id: The virtual server ID.
            template: OS template ID (oneprovider_list_vm_templates) or image UUID.
            ssh_keys: Optional SSH key UUIDs to install.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        validate_id(template, name="template")
        for k in ssh_keys or []:
            validate_id(k, name="ssh_keys[]")
        ctx.confirmations.consume(
            "oneprovider_reinstall_vm",
            {
                "vm_id": vm_id,
                "template": template,
                "ssh_keys": ssh_keys,
                "confirmation_token": confirmation_token,
            },
            confirmation_token,
        )
        payload: dict[str, Any] = {"vm_id": vm_id, "template": template}
        if ssh_keys:
            payload["ssh_keys"] = ssh_keys
        data = await ctx.client.post("/vm/reinstall", data=payload)
        return {"ok": True, "operation": "oneprovider_reinstall_vm", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_reinstall_vm",
        "DESTRUCTIVE: reinstall a OneCloud VM's OS (all data lost).",
        oneprovider_reinstall_vm,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_reinstall_vm"] = RiskTier.DESTRUCTIVE.value

    async def oneprovider_resize_vm(
        vm_id: str, instance_size: str, confirmation_token: str
    ) -> dict[str, Any]:
        """Resize a VM to a different instance size. DESTRUCTIVE /
        financially consequential (plan change; may require reboot and may
        alter billing).

        Args:
            vm_id: The virtual server ID.
            instance_size: Size ID from oneprovider_list_vm_sizes.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        validate_id(instance_size, name="instance_size")
        ctx.confirmations.consume(
            "oneprovider_resize_vm",
            {"vm_id": vm_id, "instance_size": instance_size},
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/resize", data={"vm_id": vm_id, "instance_size": instance_size}
        )
        return {"ok": True, "operation": "oneprovider_resize_vm", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_resize_vm",
        "DESTRUCTIVE/FINANCIAL: resize a OneCloud VM to another plan.",
        oneprovider_resize_vm,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_resize_vm"] = RiskTier.DESTRUCTIVE.value

    async def oneprovider_destroy_vm(
        vm_id: str, confirm_close: bool = True, confirmation_token: str = ""
    ) -> dict[str, Any]:
        """Destroy (permanently delete) a virtual server. DESTRUCTIVE:
        irreversible; ``confirm_close`` acknowledges any bandwidth overage
        charges.

        Args:
            vm_id: The virtual server ID.
            confirm_close: Confirm acceptance of possible bandwidth overage charges.
            confirmation_token: Token from oneprovider_request_confirmation.
        """
        validate_id(vm_id, name="vm_id")
        if not confirm_close:
            raise ValueError("confirm_close must be true to acknowledge possible overage charges")
        ctx.confirmations.consume(
            "oneprovider_destroy_vm",
            {
                "vm_id": vm_id,
                "confirm_close": confirm_close,
                "confirmation_token": confirmation_token,
            },
            confirmation_token,
        )
        data = await ctx.client.post(
            "/vm/destroy", data={"vm_id": vm_id, "confirm_close": int(confirm_close)}
        )
        return {"ok": True, "operation": "oneprovider_destroy_vm", "data": data}

    if add(
        server,
        ctx,
        "oneprovider_destroy_vm",
        "DESTRUCTIVE: permanently destroy a OneCloud VM (irreversible).",
        oneprovider_destroy_vm,
        RiskTier.DESTRUCTIVE,
    ):
        registered["oneprovider_destroy_vm"] = RiskTier.DESTRUCTIVE.value

    return registered
