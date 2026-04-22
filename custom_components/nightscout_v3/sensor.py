"""Sensor platform — one SensorEntity per enabled feature."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import OPT_ENABLED_FEATURES, OPT_STATS_WINDOWS, MANDATORY_STATS_WINDOW
from .entity import NightscoutEntity
from .feature_registry import Category, FEATURE_REGISTRY, FeatureDef, features_for_capabilities, stats_feature_defs
from .models import NightscoutConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: NightscoutConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    enabled = entry.options.get(OPT_ENABLED_FEATURES, {})
    active = features_for_capabilities(data.capabilities)
    entities: list[SensorEntity] = []
    for f in active:
        if f.platform != Platform.SENSOR:
            continue
        if not enabled.get(f.key, f.default_enabled):
            continue
        entities.append(NightscoutSensor(data.coordinator, f))

    windows = sorted(set(entry.options.get(OPT_STATS_WINDOWS, [MANDATORY_STATS_WINDOW])) | {MANDATORY_STATS_WINDOW})
    for w in windows:
        for f in stats_feature_defs(w):
            if not enabled.get(f.key, f.default_enabled):
                continue
            entities.append(NightscoutSensor(data.coordinator, f))

    async_add_entities(entities)


class NightscoutSensor(NightscoutEntity, SensorEntity):
    """One coordinator-backed SensorEntity."""

    def __init__(self, coordinator, feature: FeatureDef) -> None:
        super().__init__(coordinator, feature)
        self._attr_device_class = feature.device_class
        self._attr_state_class = feature.state_class
        self._attr_native_unit_of_measurement = feature.unit

    @property
    def native_value(self) -> Any:
        val = self._extract()
        if isinstance(val, dict | list):
            return None  # complex values are surfaced as extra_state_attributes
        return val

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        val = self._extract()
        if isinstance(val, dict):
            return val
        if isinstance(val, list):
            return {"items": val}
        return None
