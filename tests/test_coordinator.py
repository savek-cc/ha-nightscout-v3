"""Tests for NightscoutCoordinator staggered-tick behavior."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError
from custom_components.nightscout_v3.coordinator import NightscoutCoordinator
from custom_components.nightscout_v3.history_store import HistoryStore


def _caps() -> ServerCapabilities:
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


@pytest.fixture
async def store(tmp_path):
    s = await HistoryStore.open(tmp_path / "c.db")
    try:
        yield s
    finally:
        await s.close()


@pytest.fixture
def entry() -> ConfigEntry:
    e = MagicMock(spec=ConfigEntry)
    e.entry_id = "entry-1"
    e.title = "Test User"
    e.options = {}
    e.data = {"url": "https://ns.example"}
    e.state = ConfigEntryState.SETUP_IN_PROGRESS
    return e


@pytest.fixture
def mock_client():
    c = AsyncMock()
    c.get_entries.return_value = [{"identifier": "e1", "date": 1, "sgv": 140, "direction": "Flat", "type": "sgv", "srvModified": 2}]
    c.get_devicestatus.return_value = [{
        "pump": {"battery": {"percent": 80}, "reservoir": 100.0, "status": {"status": "normal"},
                  "extended": {"ActiveProfile": "P", "BaseBasalRate": 0.85, "LastBolus": "21.04. 12:00",
                                "LastBolusAmount": 2.0, "TempBasalRemaining": 0}},
        "openaps": {"iob": {"iob": 1.0, "basaliob": 0.5, "activity": 0.01},
                     "suggested": {"eventualBG": 120, "targetBG": 105, "COB": 10,
                                    "sensitivityRatio": 1.0, "reason": "ok",
                                    "predBGs": {"IOB": [], "ZT": []}}},
        "created_at": "2026-04-21T23:45:00Z",
        "date": 1_745_009_700_000,
        "uploaderBattery": 65,
        "isCharging": False,
    }]
    c.get_treatments.return_value = []
    c.get_last_modified.return_value = {"collections": {"entries": 1, "devicestatus": 2, "treatments": 3}}
    return c


async def test_first_refresh_populates_data(hass: HomeAssistant, mock_client, store, entry) -> None:
    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    await coord.async_config_entry_first_refresh()
    assert coord.data is not None
    assert coord.data["bg"]["current_sgv"] == 140
    assert coord.data["pump"]["battery_percent"] == 80
    assert coord.data["loop"]["iob"] == 1.0


async def test_auth_error_becomes_config_entry_auth_failed(
    hass: HomeAssistant, mock_client, store, entry
) -> None:
    mock_client.get_entries.side_effect = AuthError("401")
    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    with pytest.raises(ConfigEntryAuthFailed):
        await coord.async_config_entry_first_refresh()


async def test_api_error_becomes_update_failed(
    hass: HomeAssistant, mock_client, store, entry
) -> None:
    from homeassistant.helpers.update_coordinator import UpdateFailed

    mock_client.get_entries.side_effect = ApiError("boom", status=503)
    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


async def test_agp_summary_exposes_per_hour_percentile_lists(
    hass: HomeAssistant, mock_client, store, entry
) -> None:
    """The AGP dashboard relies on p{5,25,50,75,95}_by_hour attributes — keep them in sync."""
    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    await coord.async_config_entry_first_refresh()
    await coord._stats_cycle()
    agp = coord._stats[14]["agp_summary"]
    assert isinstance(agp, dict)
    for key in ("p5_by_hour", "p25_by_hour", "p50_by_hour", "p75_by_hour", "p95_by_hour"):
        assert key in agp, f"missing {key}"
        assert isinstance(agp[key], list)
        assert len(agp[key]) == 24
    # raw rows stay accessible for advanced users
    assert isinstance(agp.get("items"), list)
    assert len(agp["items"]) == 24
