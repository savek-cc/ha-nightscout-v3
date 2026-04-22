"""Config flow tests — user step."""
from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.nightscout_v3.const import DOMAIN
from tests.conftest import load_fixture


@pytest.fixture
def valid_caps():
    from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
    return ServerCapabilities(
        units="mg/dl", has_openaps=True, has_pump=True, has_uploader_battery=True,
        has_entries=True, has_treatments_sensor_change=True, has_treatments_site_change=True,
        has_treatments_insulin_change=True, has_treatments_pump_battery_change=True,
        last_probed_at_ms=0,
    )


async def test_user_step_happy_path(hass: HomeAssistant, valid_caps) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
              new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0))),
        patch("custom_components.nightscout_v3.config_flow.probe_capabilities",
              new=AsyncMock(return_value=valid_caps)),
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
    with patch("custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
               new=AsyncMock(side_effect=exception_map[exc])):
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
        patch("custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
              new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0))),
        patch("custom_components.nightscout_v3.config_flow.probe_capabilities",
              new=AsyncMock(return_value=valid_caps)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://ns.example/", "access_token": "tok"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
