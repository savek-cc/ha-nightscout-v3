"""Tests for NightscoutCoordinator staggered-tick behavior."""
from __future__ import annotations

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


async def test_backfill_paginates_until_short_batch(
    hass: HomeAssistant, mock_client, store, entry
) -> None:
    """Initial sync must paginate via before_date, not stop after 1 batch."""
    import time as _time
    now_ms = int(_time.time() * 1000)
    step = 300_000  # 5 minutes
    batch1 = [
        {"identifier": f"a{i}", "date": now_ms - i * step, "sgv": 140, "type": "sgv"}
        for i in range(1000)
    ]
    batch1_min = batch1[-1]["date"]
    batch2 = [
        {"identifier": f"b{i}", "date": batch1_min - (i + 1) * step, "sgv": 150, "type": "sgv"}
        for i in range(500)
    ]
    batch2_min = batch2[-1]["date"]
    mock_client.get_entries.side_effect = [batch1, batch2]

    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    await coord._backfill_entries(entries_lm=42)

    calls = mock_client.get_entries.call_args_list
    assert len(calls) == 2, "second batch had <1000 docs, loop must stop after it"
    assert calls[0].kwargs["before_date"] is None
    assert calls[1].kwargs["before_date"] == batch1_min
    assert all("since_date" not in c.kwargs for c in calls), \
        "date$gte on same request as date$lt gets the $lt silently dropped by v3"
    assert all("last_modified" not in c.kwargs for c in calls), \
        "srvModified filter must not be sent on initial sync"
    state = await store.get_sync_state("entries")
    assert state is not None
    assert state.last_modified == 42
    assert state.oldest_date == batch2_min
    assert state.newest_date == batch1[0]["date"]


async def test_backfill_bails_out_when_server_ignores_before_date(
    hass: HomeAssistant, mock_client, store, entry
) -> None:
    """If the server returns the same newest batch every call, abort fast.

    Regression guard: hitting an endpoint that silently drops `date$lt`
    used to produce an endless loop hammering the server.
    """
    import time as _time
    now_ms = int(_time.time() * 1000)
    step = 300_000
    same_batch = [
        {"identifier": f"x{i}", "date": now_ms - i * step, "sgv": 140, "type": "sgv"}
        for i in range(1000)
    ]
    mock_client.get_entries.return_value = same_batch

    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    await coord._backfill_entries(entries_lm=42)

    # Iter 1 accepts the batch, iter 2 detects no progress and stops.
    assert mock_client.get_entries.call_count == 2


async def test_incremental_entries_extends_window(
    hass: HomeAssistant, mock_client, store, entry
) -> None:
    """Incremental sync asks for entries since last newest_date and merges the window."""
    await store.update_sync_state("entries", last_modified=10, oldest_date=100, newest_date=200)
    mock_client.get_entries.return_value = [
        {"identifier": "new1", "date": 250, "sgv": 145, "type": "sgv"},
        {"identifier": "new2", "date": 210, "sgv": 142, "type": "sgv"},
    ]

    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    newest = await store.get_sync_state("entries")
    await coord._incremental_entries(entries_lm=20, newest=newest)

    call = mock_client.get_entries.call_args
    assert call.kwargs["since_date"] == 200
    state = await store.get_sync_state("entries")
    assert state.last_modified == 20
    assert state.oldest_date == 100  # unchanged
    assert state.newest_date == 250


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
