# OneProvider MCP Server

A production-ready [Model Context Protocol](https://modelcontextprotocol.io) server for
[OneProvider](https://oneprovider.com) infrastructure: dedicated servers, OneCloud VMs,
the hardware catalog, billing, support tickets, abuse reports and tags.

Built with the official `mcp` SDK (2.x `MCPServer`), `httpx`, `pydantic` and `python-dotenv`.
Registered with OpenCode under the name **`oneprovider`** (local STDIO transport).

- **94 tools across three risk tiers** (37 available in default read-only mode)
- **4 resources**, **3 prompts**
- **88 automated tests** (all API traffic mocked — no real infrastructure touched)
- Credentials auto-loaded from `~/Projects/.env`; never hardcoded, logged, or echoed

---

## Setup

### Requirements

- Python 3.11+ (developed and tested on the uv-managed 3.11 venv; system Python 3.14 also present)
- [uv](https://docs.astral.sh/uv/) (0.12+)
- OneProvider API credentials in `~/Projects/.env`:

  ```dotenv
  ONEPROVIDER_API_KEY=API_...
  ONEPROVIDER_API_SECRET=CK_...
  ```

  These names were verified against the existing `~/Projects/.env`. The file is **never**
  modified by this project; load order gives process environment variables precedence over
  the file (`load_dotenv(override=False)`).

### Install

```bash
cd ~/Projects/oneprovider-mcp
uv sync            # creates .venv and installs all dependencies
```

### Configuration (all optional unless noted)

| Variable | Default | Purpose |
|---|---|---|
| `ONEPROVIDER_API_KEY` | — | **Required.** API key (`API_...`) |
| `ONEPROVIDER_API_SECRET` | — | **Required.** Client/secret key (`CK_...`) |
| `ONEPROVIDER_ENV_FILE` | `~/Projects/.env` | Credential file path |
| `ONEPROVIDER_BASE_URL` | `https://api.oneprovider.com` | API base URL (https enforced) |
| `ONEPROVIDER_TIMEOUT_SECONDS` | `30` | Request timeout (1–120) |
| `ONEPROVIDER_MAX_RETRIES` | `3` | GET-only retry budget (0–8) |
| `ONEPROVIDER_ENABLE_WRITES` | `false` | Enables state-changing tools (tier 2) |
| `ONEPROVIDER_ENABLE_DESTRUCTIVE` | `false` | Additionally enables destructive/financial tools (tier 3) |

---

## Usage

### Run the server (STDIO)

```bash
~/Projects/oneprovider-mcp/.venv/bin/python -m oneprovider_mcp
```

STDIO is the primary transport: stdout carries only MCP protocol messages; all logging
goes to stderr. A console script is also installed: `.venv/bin/oneprovider-mcp`.

### Run tests / lint

```bash
cd ~/Projects/oneprovider-mcp
uv run pytest                 # 88 tests
uv run ruff check .
uv run ruff format --check .
```

### Inspecting tools programmatically

```python
from oneprovider_mcp.config import load_settings
from oneprovider_mcp.client import OneProviderClient
from oneprovider_mcp.safety import ConfirmationManager
from oneprovider_mcp.server import build_server

server = build_server(load_settings(), OneProviderClient(load_settings()), ConfirmationManager())
for t in server.list_tools():
    ...
```

### Tool inventory

**Read-only (always available, 35 tools + 2 meta):**

- Account: `oneprovider_get_account`
- Servers: `oneprovider_list_servers`, `oneprovider_get_server`,
  `oneprovider_get_server_manage_methods`
- OneCloud: `oneprovider_list_vms`, `oneprovider_list_vm_projects`, `oneprovider_get_vm`,
  `oneprovider_search_vm_by_ip`, `oneprovider_list_vm_templates`,
  `oneprovider_list_vm_locations`, `oneprovider_list_vm_sizes`,
  `oneprovider_list_ssh_keys`, `oneprovider_list_vm_images`, `oneprovider_get_vm_rdns`
- Catalog/store: `oneprovider_list_catalog_configs`, `oneprovider_get_catalog_config`,
  `oneprovider_list_config_drives`, `oneprovider_list_config_softwares`,
  `oneprovider_list_config_upgrades`, `oneprovider_list_catalog_upgrades`,
  `oneprovider_list_billing_cycles`, `oneprovider_list_catalog_locations`,
  `oneprovider_list_carts`, `oneprovider_get_cart`
- Billing: `oneprovider_list_invoices`, `oneprovider_get_invoice`,
  `oneprovider_list_orders`, `oneprovider_get_order`
- Support/abuse: `oneprovider_list_support_departments`,
  `oneprovider_list_support_tickets`, `oneprovider_get_support_ticket`*,
  `oneprovider_list_abuses`, `oneprovider_list_server_abuses`
- Tags: `oneprovider_list_tags`, `oneprovider_get_tag`
- Meta: `oneprovider_request_confirmation`, `oneprovider_server_info`

\* Documented API side effect: fetching a ticket marks it read.

**State-changing (requires `ONEPROVIDER_ENABLE_WRITES=true` + confirmation token, 24 tools):**

server power actions/hostname/cancellation-removal, VM boot/shutdown/reboot/force-off,
hostname, boot order, PAE, ISO mount/unmount, rescue on/off, IPv6, bandwidth-suspend
toggle, addons, SSH key create/edit/assign, rDNS set/edit, image create/rename, VNC
credentials/password, root password, projects create/edit/assign, carts create/clear/
items/add/remove/update, order cancel, support tickets create/reply/close/reopen,
tags create/edit/assign/unassign.

**Destructive/financial (requires both flags + confirmation token, 12 tools):**

`oneprovider_destroy_vm`, `oneprovider_reinstall_vm`, `oneprovider_resize_vm`,
`oneprovider_request_server_cancellation`, `oneprovider_delete_ssh_key`,
`oneprovider_delete_vm_rdns`, `oneprovider_delete_vm_image`,
`oneprovider_restore_vm_image`, `oneprovider_delete_project`, `oneprovider_remove_tag`,
`oneprovider_create_order`, `oneprovider_pay_invoice`.

**Resources:** `oneprovider://account`, `oneprovider://servers`,
`oneprovider://vm/catalog`, `oneprovider://catalog/locations`.
**Prompts:** `infrastructure_review`, `server_status_check`, `billing_overview`.

---

## OpenCode

### Registration (already applied)

`~/.config/opencode/opencode.json` (backup made at registration time):

```json
"oneprovider": {
  "type": "local",
  "command": [
    "/home/tripps/Projects/oneprovider-mcp/.venv/bin/python",
    "-m",
    "oneprovider_mcp"
  ],
  "enabled": true,
  "timeout": 120000
}
```

No secrets appear in the config — credentials are discovered from `~/Projects/.env`.

### Commands

```bash
opencode mcp list          # should show: ✓ oneprovider connected
opencode run "Using the oneprovider MCP, list my servers. Read-only."
opencode run "Use the oneprovider MCP to get account info. Do not modify anything."
```

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `oneprovider` missing from `opencode mcp list` | JSON syntax error in `opencode.json`; validate with `python3 -m json.tool` |
| Shows but not connected | Run the command from *Usage* manually; check stderr output (config errors, import errors) |
| `ConfigurationError: Missing OneProvider credentials` | `ONEPROVIDER_API_KEY`/`ONEPROVIDER_API_SECRET` absent from process env **and** `~/Projects/.env` |
| Authentication errors (API code 802) | Wrong key values; keys come from the panel's API page and must be the pair `API_...` + `CK_...` |
| Error code 812 on tickets list | Account is not VIP-tier; endpoint exists but is restricted upstream |
| Write tool missing | Intentional — set `ONEPROVIDER_ENABLE_WRITES=true` in the MCP `environment` block |

---

## Security

1. **Credential handling** — loaded from `~/Projects/.env` (or process env, which wins);
   never logged, never echoed in tool output, never written to the OpenCode config,
   never committed (`.gitignore` blocks `.env`). `Settings.safe_summary()` masks values
   (`API...Kf(len=36)`).
2. **Read-only default** — write tools are *not registered* unless
   `ONEPROVIDER_ENABLE_WRITES=true`; destructive tools additionally need
   `ONEPROVIDER_ENABLE_DESTRUCTIVE=true`. Enforcement is in code (`add_tool`), not prose.
3. **Confirmation tokens** — every write/destructive call requires a token from
   `oneprovider_request_confirmation`; tokens are single-use, 300 s TTL, and bound to
   the exact operation name + parameter digest.
4. **No arbitrary requests** — the client only ever talks to the configured https base
   URL; user-supplied IDs must match `^[A-Za-z0-9_.:@+-]{1,128}$` (blocks path/query
   injection); IPs validated with `ipaddress`.
5. **Safe retries** — only idempotent GETs are retried (bounded, exponential backoff +
   jitter); POSTs are never auto-retried.
6. **Transport hygiene** — stdout reserved for MCP; logs on stderr; secrets redacted
   from logs and error payloads.

---

## API coverage

Source: the official *OneProvider Public Collection* Postman collection (user-supplied,
`OneProvider Public Collection.postman_collection.json`) plus live verification
(2026-11-07) against `https://api.oneprovider.com`. The official docs page
(`https://panel.op-net.com/api`) is Cloudflare-challenge-protected for bots; the
Postman collection is OneProvider's own distribution and was verified empirically.

Verified API behavior: success envelope `{"result":"success","response":…}` at HTTP 200;
errors as `{"error":{"message","code"}}` **often at HTTP 200** (body is authoritative);
observed codes 404 (unknown resource), 802 (invalid token), 812 (VIP-only).

### Capability matrix — READ-ONLY (implemented + verified)

| Operation | Endpoint | Method | MCP tool | Verified |
|---|---|---|---|---|
| Account info | `/account` | GET | `oneprovider_get_account` | live ✓ |
| List servers+VMs | `/server/list` | GET | `oneprovider_list_servers` | live ✓ |
| Server details | `/server/info/{id}` | GET | `oneprovider_get_server` | live ✓ |
| Server manage methods | `/server/manage/{id}` | GET | `oneprovider_get_server_manage_methods` | live ✓ |
| OneCloud projects | `/vm/project/list` | GET | `oneprovider_list_vm_projects` | live ✓ |
| VMs by project | `/vm/listing/{uuid}` | GET | `oneprovider_list_vms` | impl (docs) |
| VM info | `/vm/info/{id}` | GET | `oneprovider_get_vm` | impl (docs) |
| VM search by IP | `/vm/info?ip=` | GET | `oneprovider_search_vm_by_ip` | impl (docs) |
| OS templates | `/vm/templates` | GET | `oneprovider_list_vm_templates` | live ✓ (23 items) |
| OneCloud locations | `/vm/locations` | GET | `oneprovider_list_vm_locations` | live ✓ |
| Instance sizes | `/vm/sizes` | GET | `oneprovider_list_vm_sizes` | live ✓ (46 items) |
| SSH keys | `/vm/sshkeys/list` | GET | `oneprovider_list_ssh_keys` | live ✓ |
| Images | `/vm/images/list` | GET | `oneprovider_list_vm_images` | live ✓ |
| rDNS lookup | `/vm/rdns/get` | POST | `oneprovider_get_vm_rdns` | impl (docs) |
| Catalog configs | `/store/configs` | GET | `oneprovider_list_catalog_configs` | live ✓ |
| Config detail | `/store/configs/{id}` | GET | `oneprovider_get_catalog_config` | impl (docs) |
| Config drives | `/store/configs/{id}/drives` | GET | `oneprovider_list_config_drives` | impl (docs) |
| Config softwares | `/store/configs/{id}/softwares` | GET | `oneprovider_list_config_softwares` | impl (docs) |
| Config upgrades | `/store/configs/{id}/upgrades` | GET | `oneprovider_list_config_upgrades` | impl (docs) |
| Catalog upgrades | `/store/configs/upgrades` | GET | `oneprovider_list_catalog_upgrades` | impl (docs) |
| Billing cycles | `/store/configs/cycles` | GET | `oneprovider_list_billing_cycles` | impl (docs) |
| Catalog locations | `/store/configs/locations` | GET | `oneprovider_list_catalog_locations` | live ✓ |
| Carts | `/store/carts` | GET | `oneprovider_list_carts` | live ✓ |
| Cart detail | `/store/carts/{id}` | GET | `oneprovider_get_cart` | impl (docs) |
| Orders | `/store/orders` | GET | `oneprovider_list_orders` | live ✓ |
| Order detail | `/store/orders/{id}` | GET | `oneprovider_get_order` | impl (docs) |
| Invoices | `/invoices` | GET | `oneprovider_list_invoices` | live ✓ |
| Invoice detail | `/invoices/{id}` | GET | `oneprovider_get_invoice` | impl (docs) |
| Tickets list | `/support/tickets` | GET | `oneprovider_list_support_tickets` | live ✓ (812 VIP-restricted) |
| Ticket detail | `/support/tickets/{id}` | GET | `oneprovider_get_support_ticket` | impl (docs) |
| Departments | `/support/tickets/departments` | GET | `oneprovider_list_support_departments` | impl (docs) |
| Abuses | `/abuses` | GET | `oneprovider_list_abuses` | live ✓ |
| Server abuses | `/abuses/{id}` | GET | `oneprovider_list_server_abuses` | impl (docs) |
| Tags | `/tag/listing/{uuid}` | GET | `oneprovider_list_tags` | impl (docs) |
| Tag detail | `/tag/{id}` | GET | `oneprovider_get_tag` | impl (docs) |

### Capability matrix — STATE-CHANGING (implemented; disabled by default)

| Endpoint | Method | MCP tool |
|---|---|---|
| `/server/action` | POST | `oneprovider_server_power_action` |
| `/server/hostname` | POST | `oneprovider_set_server_hostname` |
| `/server/remove/cancellation` | POST | `oneprovider_remove_server_cancellation` |
| `/vm/boot` `/vm/shutdown` `/vm/reboot` `/vm/poweroff` | POST | `oneprovider_boot_vm` / `shutdown_vm` / `reboot_vm` / `force_poweroff_vm` |
| `/vm/hostname` | POST | `oneprovider_set_vm_hostname` |
| `/vm/bootorder` | POST | `oneprovider_set_vm_boot_order` |
| `/vm/pae` | POST | `oneprovider_set_vm_pae` |
| `/vm/mountiso` `/vm/unmountiso` | POST | `oneprovider_mount_vm_iso` / `unmount_vm_iso` |
| `/vm/rescue/enable` `/vm/rescue/disable` | POST | `oneprovider_enable_vm_rescue_mode` / `disable_vm_rescue_mode` |
| `/vm/ipv6/enable` | POST | `oneprovider_enable_vm_ipv6` |
| `/vm/bandwidth/suspend` | POST | `oneprovider_set_vm_bandwidth_suspend` |
| `/vm/addon/add` `/vm/addon/remove` | POST | `oneprovider_add_vm_addon` / `remove_vm_addon` |
| `/vm/sshkey/new` `/vm/sshkey/edit` `/vm/sshkeys/assign` | POST | `oneprovider_create_ssh_key` / `edit_ssh_key` / `assign_ssh_keys_to_vm` |
| `/vm/rdns/add` `/vm/rdns/edit` | POST | `oneprovider_set_vm_rdns` / `edit_vm_rdns` |
| `/vm/image/create` `/vm/image/rename` | POST | `oneprovider_create_vm_image` / `rename_vm_image` |
| `/vm/vnc` `/vm/vnc/password` `/vm/password` | POST | `oneprovider_get_vnc_credentials` / `set_vnc_password` / `set_vm_root_password` |
| `/vm/project/new` `/vm/project/edit` `/vm/project/assign` | POST | `oneprovider_create_project` / `edit_project` / `assign_vm_to_project` |
| `/store/carts` (POST) + `clear` + `items/…/add` + `items/…/remove` + `update` | POST | `oneprovider_create_or_get_cart` / `clear_cart` / `add_cart_item` / `remove_cart_item` / `update_cart` |
| `/store/orders/{id}/cancel` | POST | `oneprovider_cancel_order` |
| `/support/tickets` (POST) + `reply` + `close` + `reopen` | POST | `oneprovider_create_support_ticket` / `reply_…` / `close_…` / `reopen_…` |
| `/tag/add` `/tag/edit` `/tag/assign` `/tag/unassign` | POST | `oneprovider_create_tag` / `edit_tag` / `assign_tag` / `unassign_tag` |

### Capability matrix — DESTRUCTIVE/FINANCIAL (implemented; disabled by default)

| Endpoint | Method | MCP tool |
|---|---|---|
| `/server/cancel` | POST | `oneprovider_request_server_cancellation` |
| `/vm/destroy` | POST | `oneprovider_destroy_vm` |
| `/vm/reinstall` | POST | `oneprovider_reinstall_vm` |
| `/vm/resize` | POST | `oneprovider_resize_vm` |
| `/vm/sshkey/delete` | POST | `oneprovider_delete_ssh_key` |
| `/vm/rdns/delete` | POST | `oneprovider_delete_vm_rdns` |
| `/vm/image/delete` | POST | `oneprovider_delete_vm_image` |
| `/vm/restore` | POST | `oneprovider_restore_vm_image` |
| `/vm/project/delete` | POST | `oneprovider_delete_project` |
| `/tag/remove` | POST | `oneprovider_remove_tag` |
| `/store/orders` (POST) | POST | `oneprovider_create_order` |
| `/invoices/{id}/pay` | POST | `oneprovider_pay_invoice` |

### Not implemented

- `GET /vm/list/` — explicitly marked **Deprecated** in the collection (superseded by
  `/vm/project/list` + `/vm/listing/{uuid}`).
- `POST /vm/create` (VM provisioning) — deliberately not exposed: instant purchasing
  action; enable-on-request design keeps every *practical* documented operation
  available while purchase-shaped actions stay gated. Add it to `tools/vms.py` with
  `RiskTier.DESTRUCTIVE` if instant VM purchases are wanted.

### Known limitations

- `/support/tickets` (list) returned API code **812 "Access restricted to VIP client"**
  on this account — endpoint is correct but gated upstream by account tier.
- The API documentation site is bot-protected; endpoint coverage therefore relies on
  OneProvider's official Postman collection + live verification.
- No documented rate-limit headers were observed; the client treats HTTP 429 as
  rate-limit and backs off, but exact provider limits are undocumented.
- `tag/listing` without a project UUID is accepted by the tool; if the API requires a
  UUID on some accounts, pass `project_uuid` from `oneprovider_list_vm_projects`.
