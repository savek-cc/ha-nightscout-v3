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


async def test_sensors_register_for_enabled_features(hass: HomeAssistant, caps) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="u1",
        title="Test",
        data={
            "url": "https://ns.example",
            "access_token": "t",
            "capabilities": caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={
            "enabled_features": {"bg_current": True, "bg_delta": False},
            "stats_windows": [14],
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.nightscout_v3.api.auth.JwtManager.initial_exchange",
            new=AsyncMock(
                return_value=type("S", (), {"token": "j", "iat": 0, "exp": 9999999999})()
            ),
        ),
        patch(
            "custom_components.nightscout_v3.probe_capabilities", new=AsyncMock(return_value=caps)
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
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # enabled feature -> entity exists
    state = hass.states.get("sensor.test_bg_current")
    assert state is not None
    # disabled feature -> no entity
    assert hass.states.get("sensor.test_bg_delta") is None


async def test_parallel_updates_zero():
    import custom_components.nightscout_v3.binary_sensor as bm
    import custom_components.nightscout_v3.sensor as sm

    assert sm.PARALLEL_UPDATES == 0
    assert bm.PARALLEL_UPDATES == 0


def test_sensor_extra_state_attributes_variants(monkeypatch) -> None:
    from types import SimpleNamespace

    from custom_components.nightscout_v3.feature_registry import FEATURE_REGISTRY
    from custom_components.nightscout_v3.sensor import NightscoutSensor

    f_list = next(x for x in FEATURE_REGISTRY if x.key == "loop_pred_bgs")
    f_dict = next(x for x in FEATURE_REGISTRY if x.key == "pump_status")

    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )

    # List value -> wrapped under "items"
    coord = SimpleNamespace(
        data={"loop": {"pred_bgs": [120, 118, 115]}},
        last_update_success=True,
        config_entry=SimpleNamespace(entry_id="e", title="T", data={"url": "x"}),
    )
    ent = NightscoutSensor(coord, f_list)
    ent.coordinator = coord
    assert ent.native_value is None
    assert ent.extra_state_attributes == {"items": [120, 118, 115]}

    # Dict value -> returned as-is
    coord2 = SimpleNamespace(
        data={"pump": {"status_text": {"code": 0, "message": "ok"}}},
        last_update_success=True,
        config_entry=SimpleNamespace(entry_id="e", title="T", data={"url": "x"}),
    )
    ent2 = NightscoutSensor(coord2, f_dict)
    ent2.coordinator = coord2
    assert ent2.native_value is None
    assert ent2.extra_state_attributes == {"code": 0, "message": "ok"}

    # Scalar -> extra_state_attributes is None, native_value returns value
    coord3 = SimpleNamespace(
        data={"pump": {"status_text": "normal"}},
        last_update_success=True,
        config_entry=SimpleNamespace(entry_id="e", title="T", data={"url": "x"}),
    )
    ent3 = NightscoutSensor(coord3, f_dict)
    ent3.coordinator = coord3
    assert ent3.native_value == "normal"
    assert ent3.extra_state_attributes is None


def test_binary_sensor_is_on_value_handling(monkeypatch) -> None:
    from types import SimpleNamespace

    from custom_components.nightscout_v3.binary_sensor import NightscoutBinarySensor
    from custom_components.nightscout_v3.feature_registry import FEATURE_REGISTRY

    f = next(x for x in FEATURE_REGISTRY if x.key == "loop_active")
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )

    coord_on = SimpleNamespace(
        data={"loop": {"active": True}},
        last_update_success=True,
        config_entry=SimpleNamespace(entry_id="e", title="T", data={"url": "x"}),
    )
    ent = NightscoutBinarySensor(coord_on, f)
    ent.coordinator = coord_on
    assert ent.is_on is True

    coord_missing = SimpleNamespace(
        data={"loop": {}},
        last_update_success=True,
        config_entry=SimpleNamespace(entry_id="e", title="T", data={"url": "x"}),
    )
    ent2 = NightscoutBinarySensor(coord_missing, f)
    ent2.coordinator = coord_missing
    assert ent2.is_on is None


async def test_binary_sensor_disabled_feature_skipped(hass, caps) -> None:
    """Covers branch where enabled.get(f.key, f.default_enabled) is False."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="u-skip",
        title="Test",
        data={
            "url": "https://ns.example",
            "access_token": "t",
            "capabilities": caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={
            "enabled_features": {
                "loop_active": False,
                "uploader_online": False,
                "uploader_charging": False,
            },
            "stats_windows": [14],
        },
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.nightscout_v3.api.auth.JwtManager.initial_exchange",
            new=AsyncMock(
                return_value=type("S", (), {"token": "j", "iat": 0, "exp": 9999999999})()
            ),
        ),
        patch(
            "custom_components.nightscout_v3.probe_capabilities", new=AsyncMock(return_value=caps)
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
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_loop_active") is None
