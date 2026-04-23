"""Binary sensor platform — one BinarySensorEntity per enabled feature."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import OPT_ENABLED_FEATURES
from .coordinator import NightscoutCoordinator
from .entity import NightscoutEntity
from .feature_registry import FeatureDef, features_for_capabilities
from .models import NightscoutConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: NightscoutConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensor entities for enabled features."""
    data = entry.runtime_data
    enabled = entry.options.get(OPT_ENABLED_FEATURES, {})
    entities: list[BinarySensorEntity] = []
    for f in features_for_capabilities(data.capabilities):
        if f.platform != Platform.BINARY_SENSOR:
            continue
        if not enabled.get(f.key, f.default_enabled):
            continue
        entities.append(NightscoutBinarySensor(data.coordinator, f))
    async_add_entities(entities)


class NightscoutBinarySensor(NightscoutEntity, BinarySensorEntity):
    """Coordinator-backed binary sensor."""

    def __init__(self, coordinator: NightscoutCoordinator, feature: FeatureDef) -> None:
        """Initialize the binary sensor for the given feature."""
        super().__init__(coordinator, feature)
        # FeatureDef.device_class may hold either sensor variant; only keep the
        # binary-sensor-side values for this platform.
        if isinstance(feature.device_class, BinarySensorDeviceClass):
            self._attr_device_class = feature.device_class

    @property
    def is_on(self) -> bool | None:
        """Return True/False from the extracted feature value, or None."""
        val = self._extract()
        if val is None:
            return None
        return bool(val)
