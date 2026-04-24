"""Sensor platform — one SensorEntity per enabled feature."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MANDATORY_STATS_WINDOW, OPT_ENABLED_FEATURES, OPT_STATS_WINDOWS
from .coordinator import NightscoutCoordinator
from .entity import NightscoutEntity
from .feature_registry import FeatureDef, features_for_capabilities, stats_feature_defs
from .models import NightscoutConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: NightscoutConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Nightscout sensor entities from a config entry."""
    data = entry.runtime_data
    enabled = entry.options.get(OPT_ENABLED_FEATURES, {})
    active = features_for_capabilities(data.capabilities)
    entities: list[SensorEntity] = []
    for f in active:
        if f.platform != Platform.SENSOR:
            continue
        # Only apply the options-flow enabled-features dict to default-ON features
        # (user opt-out). Default-OFF features are always registered and rely on
        # entity_registry_enabled_default=False so users opt them in via the
        # entity-registry UI.
        if f.default_enabled and not enabled.get(f.key, True):
            continue
        entities.append(NightscoutSensor(data.coordinator, f))

    windows = sorted(
        set(entry.options.get(OPT_STATS_WINDOWS, [MANDATORY_STATS_WINDOW]))
        | {MANDATORY_STATS_WINDOW}
    )
    for w in windows:
        for f in stats_feature_defs(w):
            if f.default_enabled and not enabled.get(f.key, True):
                continue
            entities.append(NightscoutSensor(data.coordinator, f))

    async_add_entities(entities)


class NightscoutSensor(NightscoutEntity, SensorEntity):
    """One coordinator-backed SensorEntity."""

    def __init__(self, coordinator: NightscoutCoordinator, feature: FeatureDef) -> None:
        """Initialize the Nightscout sensor for a feature."""
        super().__init__(coordinator, feature)
        # FeatureDef.device_class is SensorDeviceClass | BinarySensorDeviceClass | None;
        # on the sensor platform the non-None values are always Sensor-side.
        if isinstance(feature.device_class, SensorDeviceClass):
            self._attr_device_class = feature.device_class
        self._attr_state_class = feature.state_class
        self._attr_native_unit_of_measurement = feature.unit

    @property
    def native_value(self) -> Any:
        """Return the sensor state, or None for complex (dict/list) values."""
        val = self._extract()
        if isinstance(val, dict | list):
            return None  # complex values are surfaced as extra_state_attributes
        return val

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return complex values as extra state attributes, else None."""
        val = self._extract()
        if isinstance(val, dict):
            return val
        if isinstance(val, list):
            return {"items": val}
        return None
