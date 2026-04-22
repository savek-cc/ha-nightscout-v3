"""Tests for sensor / binary_sensor platform registration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
from custom_components.nightscout_v3.const import DOMAIN
from tests.conftest import load_fixture


@pytest.fixture
def caps() -> ServerCapabilities:
    return ServerCapabilities(
        units="mg/dl", has_openaps=True, has_pump=True, has_uploader_battery=True,
        has_entries=True, has_treatments_sensor_change=True, has_treatments_site_change=True,
        has_treatments_insulin_change=True, has_treatments_pump_battery_change=True,
        last_probed_at_ms=0,
    )


async def test_sensors_register_for_enabled_features(hass: HomeAssistant, caps) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="u1", title="Test",
        data={"url": "https://ns.example", "access_token": "t",
              "capabilities": caps.to_dict(), "capabilities_probed_at": 0},
        options={"enabled_features": {"bg_current": True, "bg_delta": False},
                 "stats_windows": [14]},
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.nightscout_v3.api.auth.JwtManager.initial_exchange",
              new=AsyncMock(return_value=type("S", (), {"token": "j", "iat": 0, "exp": 9999999999})())),
        patch("custom_components.nightscout_v3.probe_capabilities",
              new=AsyncMock(return_value=caps)),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_entries",
              new=AsyncMock(return_value=load_fixture("entries_latest")["result"])),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_devicestatus",
              new=AsyncMock(return_value=load_fixture("devicestatus_latest")["result"])),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_last_modified",
              new=AsyncMock(return_value=load_fixture("lastmodified")["result"])),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_treatments",
              new=AsyncMock(return_value=[])),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # enabled feature -> entity exists
    state = hass.states.get("sensor.test_bg_current")
    assert state is not None
    # disabled feature -> no entity
    assert hass.states.get("sensor.test_bg_delta") is None


async def test_parallel_updates_zero():
    import custom_components.nightscout_v3.sensor as sm
    import custom_components.nightscout_v3.binary_sensor as bm
    assert sm.PARALLEL_UPDATES == 0
    assert bm.PARALLEL_UPDATES == 0
