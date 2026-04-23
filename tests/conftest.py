"""Shared test fixtures for nightscout_v3."""

from __future__ import annotations

import contextlib
import inspect
import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _patch_aioresponses_asyncio_compat() -> None:
    """Teach aioresponses to use the non-deprecated coroutine detector.

    aioresponses 0.7.8 still calls `asyncio.iscoroutinefunction`, which emits
    a DeprecationWarning on Python 3.14 and is scheduled for removal in 3.16.
    Patch the dependency in test bootstrap so CI stays quiet and future Python
    versions do not break the suite on this helper.
    """
    with contextlib.suppress(ImportError):
        import aioresponses.core as aioresponses_core

        aioresponses_core.asyncio.iscoroutinefunction = inspect.iscoroutinefunction


_patch_aioresponses_asyncio_compat()


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture by filename (without .json extension)."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Auto-enable loading the integration in all tests (skip for pure unit tests)."""
    # For HA integration tests we need enable_custom_integrations from
    # pytest-homeassistant-custom-component. For pure unit tests, skip.
    with contextlib.suppress(pytest.FixtureLookupError):
        request.getfixturevalue("enable_custom_integrations")
    yield


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Short-circuit async_setup_entry for config-flow-only tests."""
    with patch("custom_components.nightscout_v3.async_setup_entry", return_value=True) as m:
        yield m
