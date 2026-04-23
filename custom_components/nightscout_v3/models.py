"""Runtime-data dataclass for nightscout_v3."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .api.auth import JwtManager
from .api.capabilities import ServerCapabilities
from .api.client import NightscoutV3Client
from .coordinator import NightscoutCoordinator
from .history_store import HistoryStore


@dataclass(slots=True)
class NightscoutData:
    """Everything a config entry owns at runtime."""

    client: NightscoutV3Client
    coordinator: NightscoutCoordinator
    store: HistoryStore
    capabilities: ServerCapabilities
    jwt_manager: JwtManager
    jwt_refresh_unsub: Callable[[], None]


type NightscoutConfigEntry = ConfigEntry[NightscoutData]
