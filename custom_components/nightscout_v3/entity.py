"""Base entity for nightscout_v3."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL

if TYPE_CHECKING:
    from .coordinator import NightscoutCoordinator
    from .feature_registry import FeatureDef


class NightscoutEntity(CoordinatorEntity["NightscoutCoordinator"]):
    """Shared base: unique_id, has_entity_name, device_info, extractor plumbing."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: "NightscoutCoordinator", feature: "FeatureDef") -> None:
        """Initialize the Nightscout entity for the given feature."""
        super().__init__(coordinator)
        self._feature = feature
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{feature.key}"
        self._attr_translation_key = feature.translation_key
        if feature.translation_placeholders:
            self._attr_translation_placeholders = dict(feature.translation_placeholders)
        self._attr_icon = feature.icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=coordinator.config_entry.title,
            configuration_url=coordinator.config_entry.data.get("url"),
        )

    def _extract(self) -> Any:
        """Pull the value from coordinator data using this feature's dotted path."""
        data = self.coordinator.data
        if data is None:
            return None
        for part in self._feature.extractor.split("."):
            if data is None:
                return None
            if isinstance(data, dict):
                data = data.get(part)
            else:
                data = getattr(data, part, None)
        return data

    @property
    def available(self) -> bool:
        """Available only when coordinator last update succeeded AND value is not None."""
        if not super().available:
            return False
        return self._extract() is not None
