"""Diagnostics redaction tests."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
from custom_components.nightscout_v3.const import DOMAIN
from custom_components.nightscout_v3.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.fixture
def caps() -> ServerCapabilities:
    return ServerCapabilities(
        units="mg/dl", has_openaps=True, has_pump=True, has_uploader_battery=True,
        has_entries=True, has_treatments_sensor_change=True, has_treatments_site_change=True,
        has_treatments_insulin_change=True, has_treatments_pump_battery_change=True,
        last_probed_at_ms=0,
    )


async def test_diagnostics_redacts_url_and_token(hass: HomeAssistant, caps) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="uid-diag", title="Test",
        data={"url": "https://secret.example", "access_token": "SECRET",
              "capabilities": caps.to_dict(), "capabilities_probed_at": 0},
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.nightscout_v3.diagnostics._collect_runtime",
        return_value={"coordinator": {"tick": 5}, "jwt": {"exp_in_seconds": 120}},
    ):
        diag = await async_get_config_entry_diagnostics(hass, entry)

    dumped = str(diag)
    assert "SECRET" not in dumped
    assert "secret.example" not in dumped
    assert diag["entry"]["data"]["url"] == "**REDACTED**"
    assert diag["entry"]["data"]["access_token"] == "**REDACTED**"
    assert diag["runtime"]["coordinator"]["tick"] == 5
