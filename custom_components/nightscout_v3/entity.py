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

    def __init__(self, coordinator: NightscoutCoordinator, feature: FeatureDef) -> None:
        """Initialize the Nightscout entity for the given feature."""
        super().__init__(coordinator)
        self._feature = feature
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{feature.key}"
        self._attr_translation_key = feature.translation_key
        if feature.translation_placeholders:
            self._attr_translation_placeholders = dict(feature.translation_placeholders)
        if feature.entity_category is not None:
            self._attr_entity_category = feature.entity_category
        # Gold rule `entity-disabled-by-default`: noisy/advanced features are
        # registered but disabled by default so users enable them via the
        # standard entity-registry UI.
        self._attr_entity_registry_enabled_default = feature.default_enabled
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=coordinator.config_entry.title,
            configuration_url=coordinator.config_entry.data.get("url"),
        )

    def _extract(self) -> Any:
        """Pull the value from coordinator data using this feature's dotted path."""
        data: Any = self.coordinator.data
        for part in self._feature.extractor.split("."):
            if not isinstance(data, dict):
                return None
            data = data.get(part)
        return data

    # `available` is inherited from CoordinatorEntity; we do NOT override
    # it to also gate on `_extract() is not None`. A successful poll that
    # returns `None` for a given feature (e.g. last_bolus_time before the
    # first bolus of the day) is a legitimate "no value yet" state and
    # should surface as `unknown`, not `unavailable`.
