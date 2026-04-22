"""Shared test fixtures for nightscout_v3."""
from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture by filename (without .json extension)."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Auto-enable loading the integration in all tests (skip for pure unit tests)."""
    # For HA integration tests, we need enable_custom_integrations from pytest-homeassistant-custom-component
    # For pure unit tests, skip this fixture
    try:
        fixture = request.getfixturevalue("enable_custom_integrations")
    except pytest.FixtureLookupError:
        # Not a HA test, no fixture needed
        fixture = None
    yield


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Short-circuit async_setup_entry for config-flow-only tests."""
    with patch(
        "custom_components.nightscout_v3.async_setup_entry", return_value=True
    ) as m:
        yield m
