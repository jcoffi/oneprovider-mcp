"""Configuration loading for the OneProvider MCP server.

Credentials are read from ``~/Projects/.env`` by default (file already exists
on this machine and must never be modified). Explicit process environment
variables take precedence over the file. Values are never logged or embedded
in exceptions.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .exceptions import ConfigurationError

# Default credential file (task requirement): ~/Projects/.env
DEFAULT_ENV_FILE = Path.home() / "Projects" / ".env"

_DEFAULT_BASE_URL = "https://api.oneprovider.com"

_SAFE_URL_RE = re.compile(r"^https://[A-Za-z0-9.\-_]+(:\d{1,5})?$")


def _mask(value: str | None) -> str:
    """Return a safely displayable mask of a secret value."""
    if not value:
        return "<unset>"
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}...{value[-2:]}(len={len(value)})"


@dataclass(frozen=True)
class Settings:
    """Resolved server settings."""

    api_key: str
    api_secret: str
    base_url: str = _DEFAULT_BASE_URL
    env_file: Path = DEFAULT_ENV_FILE
    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_base: float = 0.5
    max_page_size: int = 100
    enable_writes: bool = False
    enable_destructive: bool = False
    extra_tags: tuple[str, ...] = field(default_factory=tuple)

    # -- helpers ---------------------------------------------------------

    @property
    def auth_headers(self) -> dict[str, str]:
        """Authentication headers required by the OneProvider API.

        These must only ever be attached to outbound requests, never logged.
        """
        return {
            "Api-Key": self.api_key,
            "Client-Key": self.api_secret,
            "X-Pretty-JSON": "1",
        }

    def safe_summary(self) -> dict:
        """A redacted summary safe for logs and tool output."""
        return {
            "base_url": self.base_url,
            "env_file": str(self.env_file),
            "api_key": _mask(self.api_key),
            "api_secret": _mask(self.api_secret),
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "enable_writes": self.enable_writes,
            "enable_destructive": self.enable_destructive,
        }


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"Environment variable {name} must be a number") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"Environment variable {name} must be an integer") from exc


def load_settings(env_file: Path | None = None, *, require_credentials: bool = True) -> Settings:
    """Load settings from the environment and the user's ``.env`` file.

    Precedence (highest first):
      1. Process environment variables
      2. ``env_file`` (default: ``~/Projects/.env``) -- loaded with
         ``override=False`` so existing process env always wins.

    Raises :class:`ConfigurationError` when required credentials are missing.
    """
    file_path = env_file or Path(os.environ.get("ONEPROVIDER_ENV_FILE", str(DEFAULT_ENV_FILE)))
    if file_path.is_file():
        # Never overwrite values already present in the process environment.
        load_dotenv(dotenv_path=file_path, override=False)

    api_key = os.environ.get("ONEPROVIDER_API_KEY", "").strip()
    api_secret = os.environ.get("ONEPROVIDER_API_SECRET", "").strip()

    if require_credentials:
        missing = [
            name
            for name, value in (
                ("ONEPROVIDER_API_KEY", api_key),
                ("ONEPROVIDER_API_SECRET", api_secret),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError(
                "Missing OneProvider credentials: "
                + ", ".join(missing)
                + f" (looked in process env and {file_path})"
            )

    base_url = os.environ.get("ONEPROVIDER_BASE_URL", _DEFAULT_BASE_URL).strip().rstrip("/")
    if not _SAFE_URL_RE.match(base_url):
        raise ConfigurationError(f"ONEPROVIDER_BASE_URL must be an https:// URL, got: {base_url!r}")

    timeout = _env_float("ONEPROVIDER_TIMEOUT_SECONDS", 30.0)
    if not 1.0 <= timeout <= 120.0:
        raise ConfigurationError("ONEPROVIDER_TIMEOUT_SECONDS must be between 1 and 120")

    max_retries = _env_int("ONEPROVIDER_MAX_RETRIES", 3)
    if not 0 <= max_retries <= 8:
        raise ConfigurationError("ONEPROVIDER_MAX_RETRIES must be between 0 and 8")

    return Settings(
        api_key=api_key,
        api_secret=api_secret,
        base_url=base_url,
        env_file=file_path,
        timeout_seconds=timeout,
        max_retries=max_retries,
        enable_writes=_env_bool("ONEPROVIDER_ENABLE_WRITES", False),
        enable_destructive=_env_bool("ONEPROVIDER_ENABLE_DESTRUCTIVE", False),
    )
