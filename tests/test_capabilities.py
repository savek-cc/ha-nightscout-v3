"""Tests for ServerCapabilities.probe."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities, probe_capabilities
from tests.conftest import load_fixture


@pytest.fixture
def client() -> AsyncMock:
    c = AsyncMock()
    c.get_status = AsyncMock(return_value=load_fixture("status")["result"])
    c.get_devicestatus = AsyncMock(return_value=load_fixture("devicestatus_latest")["result"])
    c.get_entries = AsyncMock(return_value=load_fixture("entries_latest")["result"])
    c.get_treatments = AsyncMock(return_value=load_fixture("treatments_sensor_change")["result"])
    return c


async def test_probe_detects_full_aaps_server(client: AsyncMock) -> None:
    caps = await probe_capabilities(client)
    assert caps.units == "mg/dl"
    assert caps.has_openaps is True
    assert caps.has_pump is True
    assert caps.has_entries is True
    assert caps.has_uploader_battery is True
    assert caps.has_treatments_sensor_change is True


async def test_probe_detects_minimal_server(client: AsyncMock) -> None:
    client.get_devicestatus.return_value = []
    client.get_treatments.return_value = []
    caps = await probe_capabilities(client)
    assert caps.has_openaps is False
    assert caps.has_pump is False
    assert caps.has_treatments_sensor_change is False
    assert caps.has_entries is True
    assert caps.units == "mg/dl"


async def test_probe_raises_if_no_entries(client: AsyncMock) -> None:
    client.get_entries.return_value = []
    with pytest.raises(RuntimeError, match="entries"):
        await probe_capabilities(client)


def test_capabilities_round_trip_dict() -> None:
    caps = ServerCapabilities(
        units="mg/dl",
        has_openaps=True,
        has_pump=True,
        has_uploader_battery=False,
        has_entries=True,
        has_treatments_sensor_change=True,
        has_treatments_site_change=False,
        has_treatments_insulin_change=False,
        has_treatments_pump_battery_change=False,
        last_probed_at_ms=1745000000000,
    )
    data = caps.to_dict()
    restored = ServerCapabilities.from_dict(data)
    assert restored == caps
