"""Config flow tests — user step."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.nightscout_v3.const import DOMAIN


@pytest.fixture
def valid_caps():
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


async def test_user_step_happy_path(hass: HomeAssistant, valid_caps) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
            new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0)),
        ),
        patch(
            "custom_components.nightscout_v3.config_flow.probe_capabilities",
            new=AsyncMock(return_value=valid_caps),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://ns.example/", "access_token": "tok"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ns.example"
    expected_uid = hashlib.sha256(b"https://ns.example").hexdigest()[:16]
    assert result["result"].unique_id == expected_uid


@pytest.mark.parametrize(
    ("exc", "error_key"),
    [
        ("auth", "invalid_auth"),
        ("api", "cannot_connect"),
        ("unknown", "unknown"),
    ],
)
async def test_user_step_errors(hass, exc, error_key) -> None:
    from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError

    exception_map = {
        "auth": AuthError("401"),
        "api": ApiError("boom", status=503),
        "unknown": Exception("???"),
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
        new=AsyncMock(side_effect=exception_map[exc]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://ns.example/", "access_token": "tok"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}


async def test_user_step_duplicate_aborts(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    existing_uid = hashlib.sha256(b"https://ns.example").hexdigest()[:16]
    MockConfigEntry(domain=DOMAIN, unique_id=existing_uid).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch(
            "custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
            new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0)),
        ),
        patch(
            "custom_components.nightscout_v3.config_flow.probe_capabilities",
            new=AsyncMock(return_value=valid_caps),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://ns.example/", "access_token": "tok"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --- options flow ---


async def test_options_features_sub_step(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid1",
        data={
            "url": "https://ns.example",
            "access_token": "t",
            "capabilities": valid_caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={"enabled_features": {"bg_current": True}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"].name == "MENU"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "features"}
    )
    assert result["type"].name == "FORM"
    assert result["step_id"] == "features"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"bg_current": False, "pump_reservoir": True},
    )
    assert result["type"].name == "CREATE_ENTRY"
    enabled = result["data"]["enabled_features"]
    assert enabled["bg_current"] is False
    assert enabled["pump_reservoir"] is True
    assert result["data"]["stats_windows"] == [14]


async def test_options_stats_windows(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid2",
        data={
            "url": "https://ns.example",
            "access_token": "t",
            "capabilities": valid_caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "stats"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"stats_windows": ["7", "14", "30"]}
    )
    assert result["type"].name == "CREATE_ENTRY"
    assert sorted(result["data"]["stats_windows"]) == [7, 14, 30]


async def test_options_rediscover_updates_capabilities(hass, valid_caps) -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid3",
        data={
            "url": "https://ns.example",
            "access_token": "t",
            "capabilities": valid_caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with (
        patch(
            "custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
            new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0)),
        ),
        patch(
            "custom_components.nightscout_v3.config_flow.probe_capabilities",
            new=AsyncMock(return_value=valid_caps),
        ),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "rediscover"}
        )
    assert result["type"].name == "CREATE_ENTRY"


# --- reauth ---


async def test_reauth_happy_path(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="rauid",
        data={
            "url": "https://ns.example",
            "access_token": "old",
            "capabilities": valid_caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"].name == "FORM"
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
        new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"access_token": "new"}
        )
    assert result["type"].name == "ABORT"
    assert result["reason"] == "reauth_successful"
    assert entry.data["access_token"] == "new"


async def test_options_thresholds_happy_path(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid-thr",
        data={
            "url": "https://ns.example",
            "access_token": "t",
            "capabilities": valid_caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "thresholds"}
    )
    assert result["type"].name == "FORM"
    assert result["step_id"] == "thresholds"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "tir_low_threshold_mgdl": 72,
            "tir_high_threshold_mgdl": 180,
            "tir_very_low_threshold_mgdl": 54,
            "tir_very_high_threshold_mgdl": 250,
        },
    )
    assert result["type"].name == "CREATE_ENTRY"
    assert result["data"]["tir_low_threshold_mgdl"] == 72


async def test_options_polling_happy_path(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid-pol",
        data={
            "url": "https://ns.example",
            "access_token": "t",
            "capabilities": valid_caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "polling"}
    )
    assert result["type"].name == "FORM"
    assert result["step_id"] == "polling"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "poll_fast_seconds": 60,
            "poll_change_detect_minutes": 10,
            "poll_stats_minutes": 90,
        },
    )
    assert result["type"].name == "CREATE_ENTRY"
    assert result["data"]["poll_fast_seconds"] == 60


async def test_options_rediscover_aborts_on_auth_error(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.nightscout_v3.api.exceptions import AuthError

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid-redisc-auth",
        data={
            "url": "https://ns.example",
            "access_token": "t",
            "capabilities": valid_caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(
        "custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
        new=AsyncMock(side_effect=AuthError("401")),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "rediscover"}
        )
    assert result["type"].name == "ABORT"
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("exc", "error_key"),
    [("auth", "invalid_auth"), ("api", "cannot_connect"), ("unknown", "unknown")],
)
async def test_reauth_errors(hass, valid_caps, exc, error_key) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"rauid-{exc}",
        data={
            "url": "https://ns.example",
            "access_token": "old",
            "capabilities": valid_caps.to_dict(),
            "capabilities_probed_at": 0,
        },
        options={},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    exc_map = {"auth": AuthError("401"), "api": ApiError("x"), "unknown": Exception("?")}
    with patch(
        "custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
        new=AsyncMock(side_effect=exc_map[exc]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"access_token": "new"}
        )
    assert result["errors"] == {"base": error_key}
