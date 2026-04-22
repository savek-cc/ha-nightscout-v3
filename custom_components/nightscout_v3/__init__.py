"""Nightscout v3 integration setup."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .api.auth import JwtManager
from .api.capabilities import probe_capabilities
from .api.client import NightscoutV3Client
from .api.exceptions import ApiError, AuthError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CAPABILITIES,
    CONF_CAPABILITIES_PROBED_AT,
    CONF_URL,
    JWT_BACKGROUND_REFRESH_HOURS,
)
from .coordinator import NightscoutCoordinator
from .history_store import HistoryStore
from .models import NightscoutConfigEntry, NightscoutData

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NightscoutConfigEntry) -> bool:
    """Set up nightscout_v3 from a config entry."""
    session = async_get_clientsession(hass)
    url: str = entry.data[CONF_URL]
    token: str = entry.data[CONF_ACCESS_TOKEN]

    jwt_manager = JwtManager(session, url, token)
    client = NightscoutV3Client(session, url, jwt_manager)

    try:
        await jwt_manager.initial_exchange()
    except AuthError as exc:
        raise ConfigEntryAuthFailed(str(exc)) from exc
    except ApiError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    try:
        capabilities = await probe_capabilities(client)
    except AuthError as exc:
        raise ConfigEntryAuthFailed(str(exc)) from exc
    except ApiError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_CAPABILITIES: capabilities.to_dict(),
            CONF_CAPABILITIES_PROBED_AT: capabilities.last_probed_at_ms,
        },
    )

    db_path = hass.config.path(".storage", f"nightscout_v3_{entry.entry_id}.db")
    from pathlib import Path
    store = await HistoryStore.open(Path(db_path))
    if await store.is_corrupt():
        await store.recover_from_corruption()

    coordinator = NightscoutCoordinator(hass, client, capabilities, store, entry)
    await coordinator.async_config_entry_first_refresh()

    async def _refresh_jwt(_now) -> None:
        try:
            await jwt_manager.refresh()
        except AuthError:
            _LOGGER.warning("JWT refresh rejected; awaiting reauth")
        except ApiError as exc:
            _LOGGER.debug("JWT refresh failed transiently: %s", exc)

    jwt_refresh_unsub = async_track_time_interval(
        hass, _refresh_jwt, timedelta(hours=JWT_BACKGROUND_REFRESH_HOURS)
    )

    entry.runtime_data = NightscoutData(
        client=client,
        coordinator=coordinator,
        store=store,
        capabilities=capabilities,
        jwt_manager=jwt_manager,
        jwt_refresh_unsub=jwt_refresh_unsub,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NightscoutConfigEntry) -> bool:
    """Unload a config entry cleanly."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unloaded:
        data = entry.runtime_data
        data.jwt_refresh_unsub()
        await data.coordinator.async_shutdown()
        await data.store.close()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry on options changes."""
    await hass.config_entries.async_reload(entry.entry_id)
