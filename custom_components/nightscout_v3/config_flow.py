"""Config + Options flow for nightscout_v3."""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from urllib.parse import urlparse

import homeassistant.helpers.config_validation as cv
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
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

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
        vol.Required(CONF_URL): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
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
        """Initialize the Nightscout config flow."""
        self._url: str | None = None
        self._token: str | None = None
        self._capabilities: Any | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the user step."""
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
            except Exception:
                _LOGGER.exception("Unhandled error in user step")
                errors["base"] = "unknown"

            if not errors:
                return self._create_entry_from_capabilities()

        return self.async_show_form(step_id="user", data_schema=_USER_SCHEMA, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry (URL + token change)."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            url = _normalize(user_input[CONF_URL])
            token = user_input[CONF_ACCESS_TOKEN]
            await self.async_set_unique_id(_unique_id(url))
            # If URL changed, ensure the new one isn't already configured elsewhere.
            self._abort_if_unique_id_mismatch(reason="unique_id_mismatch")
            try:
                session = async_get_clientsession(self.hass)
                mgr = JwtManager(session, url, token)
                await mgr.initial_exchange()
                client = NightscoutV3Client(session, url, mgr)
                caps = await probe_capabilities(client)
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unhandled error in reconfigure step")
                errors["base"] = "unknown"

            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        **reconfigure_entry.data,
                        CONF_URL: url,
                        CONF_ACCESS_TOKEN: token,
                        CONF_CAPABILITIES: caps.to_dict(),
                        CONF_CAPABILITIES_PROBED_AT: caps.last_probed_at_ms,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=reconfigure_entry.data.get(CONF_URL, "")): str,
                    vol.Required(CONF_ACCESS_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle the reauth step."""
        self._url = entry_data[CONF_URL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth_confirm step."""
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
            except Exception:
                _LOGGER.exception("Unhandled error in reauth")
                errors["base"] = "unknown"

            if not errors:
                reauth_entry = self._get_reauth_entry()
                await self.async_set_unique_id(reauth_entry.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, CONF_ACCESS_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )

    def _create_entry_from_capabilities(self) -> ConfigFlowResult:
        assert self._capabilities is not None and self._url is not None and self._token is not None
        title = urlparse(self._url).netloc or self._url
        enabled = {f.key: f.default_enabled for f in features_for_capabilities(self._capabilities)}
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
        """Return the options flow for this integration."""
        return NightscoutOptionsFlow()


class NightscoutOptionsFlow(OptionsFlow):
    """Options: menu + sub-steps."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the init step."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["features", "stats", "thresholds", "polling", "rediscover"],
        )

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the features step."""
        from .api.capabilities import ServerCapabilities

        caps = ServerCapabilities.from_dict(self.config_entry.data[CONF_CAPABILITIES])
        features = features_for_capabilities(caps)
        current = dict(self.config_entry.options.get(OPT_ENABLED_FEATURES, {}))

        if user_input is not None:
            current.update({f.key: bool(user_input.get(f.key, False)) for f in features})
            return self.async_create_entry(
                title="", data={**self.config_entry.options, OPT_ENABLED_FEATURES: current}
            )

        schema: dict[Any, Any] = {}
        for cat in Category:
            for f in features:
                if f.category != cat:
                    continue
                schema[vol.Optional(f.key, default=current.get(f.key, f.default_enabled))] = bool
        return self.async_show_form(step_id="features", data_schema=vol.Schema(schema))

    async def async_step_stats(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the stats step."""
        if user_input is not None:
            chosen = sorted(
                {int(w) for w in user_input.get(OPT_STATS_WINDOWS, [])} | {MANDATORY_STATS_WINDOW}
            )
            return self.async_create_entry(
                title="", data={**self.config_entry.options, OPT_STATS_WINDOWS: chosen}
            )
        current = [
            str(w)
            for w in self.config_entry.options.get(OPT_STATS_WINDOWS, [MANDATORY_STATS_WINDOW])
        ]
        schema = vol.Schema(
            {
                vol.Optional(OPT_STATS_WINDOWS, default=current): cv.multi_select(
                    {str(w): f"{w}d" for w in ALLOWED_STATS_WINDOWS}
                )
            }
        )
        return self.async_show_form(step_id="stats", data_schema=schema)

    async def async_step_thresholds(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the thresholds step."""
        if user_input is not None:
            coerced = {k: int(v) for k, v in user_input.items()}
            return self.async_create_entry(title="", data={**self.config_entry.options, **coerced})
        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    OPT_TIR_LOW,
                    default=current.get(OPT_TIR_LOW, DEFAULT_TIR_LOW),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=40,
                        max=120,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="mg/dL",
                    ),
                ),
                vol.Optional(
                    OPT_TIR_HIGH,
                    default=current.get(OPT_TIR_HIGH, DEFAULT_TIR_HIGH),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=120,
                        max=300,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="mg/dL",
                    ),
                ),
                vol.Optional(
                    OPT_TIR_VERY_LOW,
                    default=current.get(OPT_TIR_VERY_LOW, DEFAULT_TIR_VERY_LOW),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=30,
                        max=80,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="mg/dL",
                    ),
                ),
                vol.Optional(
                    OPT_TIR_VERY_HIGH,
                    default=current.get(OPT_TIR_VERY_HIGH, DEFAULT_TIR_VERY_HIGH),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=180,
                        max=400,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="mg/dL",
                    ),
                ),
            }
        )
        return self.async_show_form(step_id="thresholds", data_schema=schema)

    async def async_step_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the polling step."""
        if user_input is not None:
            coerced = {k: int(v) for k, v in user_input.items()}
            return self.async_create_entry(title="", data={**self.config_entry.options, **coerced})
        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    OPT_POLL_FAST_SECONDS,
                    default=current.get(
                        OPT_POLL_FAST_SECONDS,
                        DEFAULT_POLL_FAST_SECONDS,
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=30,
                        max=600,
                        step=10,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    ),
                ),
                vol.Optional(
                    OPT_POLL_CHANGE_DETECT_MINUTES,
                    default=current.get(
                        OPT_POLL_CHANGE_DETECT_MINUTES,
                        DEFAULT_POLL_CHANGE_DETECT_MINUTES,
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=60,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    ),
                ),
                vol.Optional(
                    OPT_POLL_STATS_MINUTES,
                    default=current.get(
                        OPT_POLL_STATS_MINUTES,
                        DEFAULT_POLL_STATS_MINUTES,
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=240,
                        step=5,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    ),
                ),
            }
        )
        return self.async_show_form(step_id="polling", data_schema=schema)

    async def async_step_rediscover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the rediscover step."""
        try:
            session = async_get_clientsession(self.hass)
            url = self.config_entry.data[CONF_URL]
            mgr = JwtManager(session, url, self.config_entry.data[CONF_ACCESS_TOKEN])
            await mgr.initial_exchange()
            client = NightscoutV3Client(session, url, mgr)
            caps = await probe_capabilities(client)
        except (AuthError, ApiError):
            return self.async_abort(reason="cannot_connect")

        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_CAPABILITIES: caps.to_dict(),
                CONF_CAPABILITIES_PROBED_AT: caps.last_probed_at_ms,
            },
        )
        # Capabilities just changed: the entity platforms need to re-read
        # FeatureDef.capability() with the new ServerCapabilities, so we
        # reload the config entry. Without this the stale feature set
        # persists until HA restart or a manual reload.
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
        return self.async_create_entry(title="", data=dict(self.config_entry.options))
