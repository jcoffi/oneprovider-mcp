"""Shared fixtures for the OneProvider MCP test suite.

All external API traffic is mocked with respx -- no real infrastructure is
touched by these tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import respx

from oneprovider_mcp.client import OneProviderClient
from oneprovider_mcp.config import Settings
from oneprovider_mcp.safety import ConfirmationManager
from oneprovider_mcp.server import build_server

FAKE_API_KEY = "API_test_key_for_unit_tests"
FAKE_SECRET = "CK_test_secret_for_unit_tests"
BASE_URL = "https://api.oneprovider.com"


def make_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "api_key": FAKE_API_KEY,
        "api_secret": FAKE_SECRET,
        "base_url": BASE_URL,
        "env_file": Path("/nonexistent/.env"),
    }
    defaults.update(overrides)
    return Settings(**defaults)


def envelope_ok(response: Any) -> dict[str, Any]:
    return {"result": "success", "response": response}


def envelope_error(code: int, message: str) -> dict[str, Any]:
    return {"error": {"message": message, "code": code}}


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def writes_settings() -> Settings:
    return make_settings(enable_writes=True)


@pytest.fixture
def destructive_settings() -> Settings:
    return make_settings(enable_writes=True, enable_destructive=True)


@pytest.fixture
def client(settings: Settings) -> OneProviderClient:
    return OneProviderClient(settings)


@pytest.fixture
def confirmations() -> ConfirmationManager:
    return ConfirmationManager(ttl_seconds=300)


@pytest.fixture
@respx.mock
def router() -> respx.MockRouter:
    """A fresh respx mock router; API base URL is matched automatically."""
    with respx.mock(base_url=BASE_URL, assert_all_mocked=False) as mock:
        yield mock


@pytest.fixture
def ro_server(settings: Settings, client: OneProviderClient, confirmations: ConfirmationManager):
    return build_server(settings, client, confirmations)


@pytest.fixture
def write_server(
    writes_settings: Settings, client: OneProviderClient, confirmations: ConfirmationManager
):
    return build_server(writes_settings, client, confirmations)


@pytest.fixture
def destructive_server(
    destructive_settings: Settings, client: OneProviderClient, confirmations: ConfirmationManager
):
    return build_server(destructive_settings, client, confirmations)
