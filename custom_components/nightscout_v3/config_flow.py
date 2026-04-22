"""Config + Options flow for nightscout_v3."""
from __future__ import annotations

import hashlib
import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api.auth import JwtManager
from .api.capabilities import probe_capabilities
from .api.client import NightscoutV3Client
from .api.exceptions import ApiError, AuthError
from .const import (
    ALLOWED_STATS_WINDOWS,
    CONF_ACCESS_TOKEN,
    CONF_CAPABILITIES,
    CONF_CAPABILITIES_PROBED_AT,
    DEFAULT_POLL_CHANGE_DETECT_MINUTES,
    DEFAULT_POLL_FAST_SECONDS,
    DEFAULT_POLL_STATS_MINUTES,
    DEFAULT_TIR_HIGH,
    DEFAULT_TIR_LOW,
    DEFAULT_TIR_VERY_HIGH,
    DEFAULT_TIR_VERY_LOW,
    DOMAIN,
    MANDATORY_STATS_WINDOW,
    OPT_ENABLED_FEATURES,
    OPT_POLL_CHANGE_DETECT_MINUTES,
    OPT_POLL_FAST_SECONDS,
    OPT_POLL_STATS_MINUTES,
    OPT_STATS_WINDOWS,
    OPT_TIR_HIGH,
    OPT_TIR_LOW,
    OPT_TIR_VERY_HIGH,
    OPT_TIR_VERY_LOW,
)
from .feature_registry import Category, features_for_capabilities

_LOGGER = logging.getLogger(__name__)

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    }
)


def _normalize(url: str) -> str:
    u = urlparse(url.strip())
    scheme = u.scheme or "https"
    netloc = u.netloc.rstrip("/")
    path = u.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


def _unique_id(url: str) -> str:
    return hashlib.sha256(_normalize(url).encode("utf-8")).hexdigest()[:16]


class NightscoutConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._url: str | None = None
        self._token: str | None = None
        self._capabilities: Any | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = _normalize(user_input[CONF_URL])
            token = user_input[CONF_ACCESS_TOKEN]
            await self.async_set_unique_id(_unique_id(url))
            self._abort_if_unique_id_configured()
            try:
                session = async_get_clientsession(self.hass)
                mgr = JwtManager(session, url, token)
                await mgr.initial_exchange()
                client = NightscoutV3Client(session, url, mgr)
                self._capabilities = await probe_capabilities(client)
                self._url = url
                self._token = token
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 — catch-all for unknown flow paths
                _LOGGER.exception("Unhandled error in user step")
                errors["base"] = "unknown"

            if not errors:
                return self._create_entry_from_capabilities()

        return self.async_show_form(step_id="user", data_schema=_USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        self._url = entry_data[CONF_URL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_ACCESS_TOKEN]
            try:
                session = async_get_clientsession(self.hass)
                mgr = JwtManager(session, self._url or "", token)
                await mgr.initial_exchange()
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unhandled error in reauth")
                errors["base"] = "unknown"

            if not errors:
                reauth_entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, CONF_ACCESS_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): cv.string}),
            errors=errors,
        )

    def _create_entry_from_capabilities(self) -> ConfigFlowResult:
        assert self._capabilities is not None and self._url is not None and self._token is not None
        title = urlparse(self._url).netloc or self._url
        enabled = {
            f.key: f.default_enabled for f in features_for_capabilities(self._capabilities)
        }
        return self.async_create_entry(
            title=title,
            data={
                CONF_URL: self._url,
                CONF_ACCESS_TOKEN: self._token,
                CONF_CAPABILITIES: self._capabilities.to_dict(),
                CONF_CAPABILITIES_PROBED_AT: self._capabilities.last_probed_at_ms,
            },
            options={
                OPT_ENABLED_FEATURES: enabled,
                OPT_STATS_WINDOWS: [MANDATORY_STATS_WINDOW],
                OPT_TIR_LOW: DEFAULT_TIR_LOW,
                OPT_TIR_HIGH: DEFAULT_TIR_HIGH,
                OPT_TIR_VERY_LOW: DEFAULT_TIR_VERY_LOW,
                OPT_TIR_VERY_HIGH: DEFAULT_TIR_VERY_HIGH,
                OPT_POLL_FAST_SECONDS: DEFAULT_POLL_FAST_SECONDS,
                OPT_POLL_CHANGE_DETECT_MINUTES: DEFAULT_POLL_CHANGE_DETECT_MINUTES,
                OPT_POLL_STATS_MINUTES: DEFAULT_POLL_STATS_MINUTES,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NightscoutOptionsFlow(config_entry)


class NightscoutOptionsFlow(OptionsFlow):
    """Options: menu + sub-steps (Task 3.5 fills all branches)."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["features", "stats", "thresholds", "polling", "rediscover"],
        )

    # Sub-steps implemented in Task 3.5
