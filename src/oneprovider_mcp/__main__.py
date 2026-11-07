"""Entry point: ``python -m oneprovider_mcp`` (STDIO transport).

STDOUT is reserved for the MCP protocol; all logging goes to STDERR.
"""

from __future__ import annotations

import logging
import sys

from .client import OneProviderClient
from .config import load_settings
from .exceptions import ConfigurationError
from .safety import ConfirmationManager
from .server import build_server


def main() -> None:
    # Configure logging BEFORE touching stdout: stderr only.
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    try:
        settings = load_settings()
    except ConfigurationError as exc:
        logging.getLogger("oneprovider_mcp").critical("Configuration error: %s", exc)
        # Configuration errors go to stderr; exit non-zero without stdout noise.
        print(f"oneprovider-mcp: configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    client = OneProviderClient(settings)
    server = build_server(settings, client, ConfirmationManager())

    logging.getLogger("oneprovider_mcp").info(
        "Starting oneprovider MCP over STDIO (base_url=%s, writes=%s, destructive=%s)",
        settings.base_url,
        settings.enable_writes,
        settings.enable_destructive,
    )
    try:
        server.run(transport="stdio")
    finally:
        import anyio

        anyio.run(client.aclose)


if __name__ == "__main__":
    main()
