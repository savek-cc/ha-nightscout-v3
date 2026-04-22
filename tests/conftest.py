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
    enable_custom_integrations: None,  # noqa: ARG001 — fixture from pytest-homeassistant-custom-component
) -> Generator[None, None, None]:
    """Auto-enable loading the integration in all tests."""
    yield


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Short-circuit async_setup_entry for config-flow-only tests."""
    with patch(
        "custom_components.nightscout_v3.async_setup_entry", return_value=True
    ) as m:
        yield m
