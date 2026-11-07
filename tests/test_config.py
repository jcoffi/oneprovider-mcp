"""Configuration loading tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from oneprovider_mcp.config import load_settings
from oneprovider_mcp.exceptions import ConfigurationError

from .conftest import FAKE_API_KEY, FAKE_SECRET


def _write_env(tmp_path: Path, content: str) -> Path:
    p = tmp_path / ".env"
    p.write_text(content)
    return p


def test_missing_credentials_raise(tmp_path, monkeypatch):
    monkeypatch.delenv("ONEPROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("ONEPROVIDER_API_SECRET", raising=False)
    env = _write_env(tmp_path, "UNRELATED=1\n")
    with pytest.raises(ConfigurationError, match="ONEPROVIDER_API_KEY"):
        load_settings(env_file=env)


def test_credentials_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ONEPROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("ONEPROVIDER_API_SECRET", raising=False)
    env = _write_env(
        tmp_path, f"ONEPROVIDER_API_KEY={FAKE_API_KEY}\nONEPROVIDER_API_SECRET={FAKE_SECRET}\n"
    )
    s = load_settings(env_file=env)
    assert s.api_key == FAKE_API_KEY
    assert s.api_secret == FAKE_SECRET


def test_process_env_overrides_env_file(tmp_path, monkeypatch):
    env = _write_env(
        tmp_path, f"ONEPROVIDER_API_KEY={FAKE_API_KEY}\nONEPROVIDER_API_SECRET={FAKE_SECRET}\n"
    )
    monkeypatch.setenv("ONEPROVIDER_API_KEY", "API_env_wins")
    s = load_settings(env_file=env)
    assert s.api_key == "API_env_wins"
    assert s.api_secret == FAKE_SECRET


def test_env_file_never_overrides_process_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ONEPROVIDER_API_KEY", "API_env_value")
    monkeypatch.setenv("ONEPROVIDER_API_SECRET", "CK_env_value")
    env = _write_env(
        tmp_path, f"ONEPROVIDER_API_KEY={FAKE_API_KEY}\nONEPROVIDER_API_SECRET={FAKE_SECRET}\n"
    )
    s = load_settings(env_file=env)
    assert s.api_key == "API_env_value"


def test_invalid_base_url_rejected(tmp_path):
    env = _write_env(
        tmp_path, f"ONEPROVIDER_API_KEY={FAKE_API_KEY}\nONEPROVIDER_API_SECRET={FAKE_SECRET}\n"
    )
    os.environ["ONEPROVIDER_BASE_URL"] = "http://evil.example.com/path"
    try:
        with pytest.raises(ConfigurationError, match="https"):
            load_settings(env_file=env)
    finally:
        os.environ.pop("ONEPROVIDER_BASE_URL", None)


def test_invalid_timeout_rejected(tmp_path):
    env = _write_env(
        tmp_path, f"ONEPROVIDER_API_KEY={FAKE_API_KEY}\nONEPROVIDER_API_SECRET={FAKE_SECRET}\n"
    )
    os.environ["ONEPROVIDER_TIMEOUT_SECONDS"] = "500"
    try:
        with pytest.raises(ConfigurationError, match="TIMEOUT"):
            load_settings(env_file=env)
    finally:
        os.environ.pop("ONEPROVIDER_TIMEOUT_SECONDS", None)


def test_safe_summary_masks_secrets():
    from .conftest import make_settings

    s = make_settings()
    summary = s.safe_summary()
    assert FAKE_API_KEY not in str(summary)
    assert FAKE_SECRET not in str(summary)
    assert summary["api_key"].startswith("API...")
    assert "len=" in summary["api_secret"]


def test_auth_headers_shape():
    from .conftest import make_settings

    headers = make_settings().auth_headers
    assert headers["Api-Key"] == FAKE_API_KEY
    assert headers["Client-Key"] == FAKE_SECRET
    assert headers["X-Pretty-JSON"] == "1"


def test_defaults_are_read_only():
    from .conftest import make_settings

    s = make_settings()
    assert s.enable_writes is False
    assert s.enable_destructive is False
    assert str(s.base_url) == "https://api.oneprovider.com"
