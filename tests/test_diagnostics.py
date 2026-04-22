"""Diagnostics redaction tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
from custom_components.nightscout_v3.const import DOMAIN
from custom_components.nightscout_v3.diagnostics import (
    _collect_runtime,
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


async def test_diagnostics_redacts_reason_and_notes(hass: HomeAssistant, caps) -> None:
    """Free-form loop.reason and care.last_note must not leak.

    Regression test for the final release review C-2: the README and
    architecture doc promise `reason` and `notes` are redacted. This
    pins the invariant on the actual diagnostics output.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="uid-diag-reason", title="Test",
        data={"url": "https://x.example", "access_token": "t",
              "capabilities": caps.to_dict(), "capabilities_probed_at": 0},
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)

    leak_reason = "LEAK_REASON_ISF_1.25_ratio_0.8"
    leak_note = "LEAK_NOTE_private_message"
    leak_uploader = "LEAK_UPLOADER_phone_name"

    with patch(
        "custom_components.nightscout_v3.diagnostics._collect_runtime",
        return_value={
            "coordinator": {"tick": 1},
            "snapshot": {
                "loop": {"reason": leak_reason},
                "care": {"last_note": leak_note},
                "uploader": {"enteredBy": leak_uploader},
            },
        },
    ):
        diag = await async_get_config_entry_diagnostics(hass, entry)

    dumped = str(diag)
    assert leak_reason not in dumped
    assert leak_note not in dumped
    assert leak_uploader not in dumped
    assert diag["runtime"]["snapshot"]["loop"]["reason"] == "**REDACTED**"
    assert diag["runtime"]["snapshot"]["care"]["last_note"] == "**REDACTED**"


def test_collect_runtime_no_runtime_data() -> None:
    entry = MagicMock()
    entry.runtime_data = None
    assert _collect_runtime(entry) == {}


def test_collect_runtime_full_snapshot(caps) -> None:
    jwt_state = SimpleNamespace(iat=100, exp=10_000_000_000)
    jwt_manager = SimpleNamespace(state=jwt_state)
    coordinator = SimpleNamespace(
        last_update_success=True,
        last_tick_summary={"tick": 42, "entries_age_s": 60},
        data={"bg": {"current_sgv": 120}},
    )
    runtime_data = SimpleNamespace(
        coordinator=coordinator, jwt_manager=jwt_manager, capabilities=caps
    )
    entry = MagicMock()
    entry.runtime_data = runtime_data

    result = _collect_runtime(entry)

    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["tick"] == 42
    assert result["jwt"]["iat"] == 100
    assert result["jwt"]["exp"] == 10_000_000_000
    assert result["jwt"]["exp_in_seconds"] >= 0
    assert result["capabilities"]["units"] == "mg/dl"
    assert result["snapshot"]["bg"]["current_sgv"] == 120


def test_collect_runtime_without_jwt_state(caps) -> None:
    jwt_manager = SimpleNamespace(state=None)
    coordinator = SimpleNamespace(
        last_update_success=False, last_tick_summary={}, data=None
    )
    runtime_data = SimpleNamespace(
        coordinator=coordinator, jwt_manager=jwt_manager, capabilities=caps
    )
    entry = MagicMock()
    entry.runtime_data = runtime_data

    result = _collect_runtime(entry)
    assert result["jwt"] == {}
    assert result["snapshot"] is None
