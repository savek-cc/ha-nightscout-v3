"""Tests for async_setup_entry / async_unload_entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nightscout_v3.const import DOMAIN
from tests.conftest import load_fixture


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="abc1234567890def",
        title="Test User",
        data={
            "url": "https://ns.example",
            "access_token": "access-test",
            "capabilities": None,
            "capabilities_probed_at": 0,
        },
        options={"enabled_features": {}, "stats_windows": [14]},
    )


async def test_setup_and_unload(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)

    with (
        patch("custom_components.nightscout_v3._PLATFORMS", []),
        patch(
            "custom_components.nightscout_v3.JwtManager.initial_exchange",
            new=AsyncMock(return_value=MagicMock(token="jwt", iat=0, exp=9999999999)),
        ),
        patch(
            "custom_components.nightscout_v3.probe_capabilities",
            new=AsyncMock(return_value=_caps()),
        ),
        patch(
            "custom_components.nightscout_v3.api.client.NightscoutV3Client.get_entries",
            new=AsyncMock(return_value=load_fixture("entries_latest")["result"]),
        ),
        patch(
            "custom_components.nightscout_v3.api.client.NightscoutV3Client.get_devicestatus",
            new=AsyncMock(return_value=load_fixture("devicestatus_latest")["result"]),
        ),
        patch(
            "custom_components.nightscout_v3.api.client.NightscoutV3Client.get_last_modified",
            new=AsyncMock(return_value=load_fixture("lastmodified")["result"]),
        ),
        patch(
            "custom_components.nightscout_v3.api.client.NightscoutV3Client.get_treatments",
            new=AsyncMock(return_value=[]),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


def _caps():
    from custom_components.nightscout_v3.api.capabilities import ServerCapabilities

    return ServerCapabilities(
        units="mg/dl",
        has_openaps=True,
        has_pump=True,
        has_uploader_battery=True,
        has_entries=True,
        has_treatments_sensor_change=True,
        has_treatments_site_change=True,
        has_treatments_insulin_change=True,
        has_treatments_pump_battery_change=True,
        last_probed_at_ms=0,
    )


async def test_setup_auth_error_triggers_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    from custom_components.nightscout_v3.api.exceptions import AuthError

    config_entry.add_to_hass(hass)
    with (
        patch("custom_components.nightscout_v3._PLATFORMS", []),
        patch(
            "custom_components.nightscout_v3.JwtManager.initial_exchange",
            new=AsyncMock(side_effect=AuthError("401")),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_api_error_is_retry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    from custom_components.nightscout_v3.api.exceptions import ApiError

    config_entry.add_to_hass(hass)
    with (
        patch("custom_components.nightscout_v3._PLATFORMS", []),
        patch(
            "custom_components.nightscout_v3.JwtManager.initial_exchange",
            new=AsyncMock(side_effect=ApiError("503", status=503)),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_capabilities_auth_error_triggers_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    from custom_components.nightscout_v3.api.exceptions import AuthError

    config_entry.add_to_hass(hass)
    with (
        patch("custom_components.nightscout_v3._PLATFORMS", []),
        patch(
            "custom_components.nightscout_v3.JwtManager.initial_exchange",
            new=AsyncMock(return_value=MagicMock(token="jwt", iat=0, exp=9999999999)),
        ),
        patch(
            "custom_components.nightscout_v3.probe_capabilities",
            new=AsyncMock(side_effect=AuthError("forbidden")),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_capabilities_api_error_is_retry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    from custom_components.nightscout_v3.api.exceptions import ApiError

    config_entry.add_to_hass(hass)
    with (
        patch("custom_components.nightscout_v3._PLATFORMS", []),
        patch(
            "custom_components.nightscout_v3.JwtManager.initial_exchange",
            new=AsyncMock(return_value=MagicMock(token="jwt", iat=0, exp=9999999999)),
        ),
        patch(
            "custom_components.nightscout_v3.probe_capabilities",
            new=AsyncMock(side_effect=ApiError("nope", status=502)),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
