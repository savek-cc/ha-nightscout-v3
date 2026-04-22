"""Tests for FEATURE_REGISTRY."""
from __future__ import annotations

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
from custom_components.nightscout_v3.feature_registry import (
    FEATURE_REGISTRY,
    Category,
    features_for_capabilities,
)


def _caps(**overrides) -> ServerCapabilities:
    base = {
        "units": "mg/dl",
        "has_openaps": True,
        "has_pump": True,
        "has_uploader_battery": True,
        "has_entries": True,
        "has_treatments_sensor_change": True,
        "has_treatments_site_change": True,
        "has_treatments_insulin_change": True,
        "has_treatments_pump_battery_change": True,
        "last_probed_at_ms": 0,
    }
    base.update(overrides)
    return ServerCapabilities(**base)


def test_registry_has_unique_keys() -> None:
    keys = [f.key for f in FEATURE_REGISTRY]
    assert len(keys) == len(set(keys))


def test_all_features_have_translation_key() -> None:
    for f in FEATURE_REGISTRY:
        assert f.translation_key, f"{f.key} missing translation_key"


def test_all_categories_represented() -> None:
    cats = {f.category for f in FEATURE_REGISTRY}
    assert Category.BG in cats
    assert Category.PUMP in cats
    assert Category.LOOP in cats
    assert Category.CAREPORTAL in cats
    assert Category.UPLOADER in cats
    # STATISTICS features are generated per-window, not listed here.


def test_full_capabilities_enables_all_features() -> None:
    enabled = features_for_capabilities(_caps())
    keys = {f.key for f in enabled}
    assert "bg_current" in keys
    assert "loop_iob" in keys
    assert "pump_reservoir" in keys
    assert "uploader_online" in keys


def test_minimal_capabilities_excludes_pump_and_loop() -> None:
    caps = _caps(has_openaps=False, has_pump=False, has_uploader_battery=False)
    enabled = features_for_capabilities(caps)
    keys = {f.key for f in enabled}
    assert "bg_current" in keys
    assert "loop_iob" not in keys
    assert "pump_reservoir" not in keys
