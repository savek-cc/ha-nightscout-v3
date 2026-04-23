"""Tests for NightscoutEntity base: unique_id, placeholders, available, extractor."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.nightscout_v3.entity import NightscoutEntity
from custom_components.nightscout_v3.feature_registry import FEATURE_REGISTRY, stats_feature_defs


def _coordinator(data, last_update_success: bool = True, title: str = "Test") -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        last_update_success=last_update_success,
        config_entry=SimpleNamespace(
            entry_id="entry1",
            title=title,
            data={"url": "https://ns.example"},
        ),
    )


def _feature(key: str):
    return next(f for f in FEATURE_REGISTRY if f.key == key)


def test_entity_sets_unique_id_and_translation_key(monkeypatch) -> None:
    f = _feature("bg_current")
    coord = _coordinator({"bg": {"current_sgv": 120}})
    # Bypass CoordinatorEntity.__init__ cost: patch it
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )
    ent = NightscoutEntity(coord, f)
    ent.coordinator = coord
    assert ent._attr_unique_id == "entry1_bg_current"
    assert ent._attr_translation_key == "bg_current"
    assert not hasattr(ent, "_attr_translation_placeholders")


def test_stats_entity_has_translation_placeholders(monkeypatch) -> None:
    f = next(x for x in stats_feature_defs(14) if x.key == "stat_gmi_14d")
    coord = _coordinator({"stats": {"14d": {"gmi_percent": 6.5}}})
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )
    ent = NightscoutEntity(coord, f)
    assert ent._attr_translation_placeholders == {"window": "14"}


def test_extract_returns_none_when_data_is_none(monkeypatch) -> None:
    f = _feature("bg_current")
    coord = _coordinator(None)
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )
    ent = NightscoutEntity(coord, f)
    ent.coordinator = coord
    assert ent._extract() is None


def test_extract_walks_dotted_path(monkeypatch) -> None:
    f = _feature("bg_current")
    coord = _coordinator({"bg": {"current_sgv": 120}})
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )
    ent = NightscoutEntity(coord, f)
    ent.coordinator = coord
    assert ent._extract() == 120


def test_extract_returns_none_for_missing_key(monkeypatch) -> None:
    f = _feature("bg_current")
    coord = _coordinator({"bg": {}})
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )
    ent = NightscoutEntity(coord, f)
    ent.coordinator = coord
    assert ent._extract() is None


def test_available_false_when_coordinator_down(monkeypatch) -> None:
    f = _feature("bg_current")
    coord = _coordinator({"bg": {"current_sgv": 120}}, last_update_success=False)
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )

    ent = NightscoutEntity(coord, f)
    ent.coordinator = coord
    # Force the CoordinatorEntity.available parent to reflect coordinator state.
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.available",
        property(lambda self: self.coordinator.last_update_success),
    )
    assert ent.available is False


def test_available_false_when_value_missing(monkeypatch) -> None:
    f = _feature("bg_current")
    coord = _coordinator({"bg": {}})
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )
    ent = NightscoutEntity(coord, f)
    ent.coordinator = coord
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.available",
        property(lambda self: self.coordinator.last_update_success),
    )
    assert ent.available is False


def test_extract_returns_none_midtraversal(monkeypatch) -> None:
    """data becomes None mid-traversal; covers the in-loop early return."""
    f = next(x for x in stats_feature_defs(14) if x.key == "stat_gmi_14d")
    coord = _coordinator({"stats": None})
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )
    ent = NightscoutEntity(coord, f)
    ent.coordinator = coord
    assert ent._extract() is None


def test_extract_walks_attribute_path(monkeypatch) -> None:
    f = _feature("bg_current")
    # coordinator.data is a namespace (not dict), exercises getattr branch.
    coord = _coordinator(SimpleNamespace(bg=SimpleNamespace(current_sgv=140)))
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )
    ent = NightscoutEntity(coord, f)
    ent.coordinator = coord
    assert ent._extract() == 140


def test_available_true_when_coordinator_ok_and_value_present(monkeypatch) -> None:
    f = _feature("bg_current")
    coord = _coordinator({"bg": {"current_sgv": 120}})
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, c: None,
    )
    ent = NightscoutEntity(coord, f)
    ent.coordinator = coord
    monkeypatch.setattr(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.available",
        property(lambda self: self.coordinator.last_update_success),
    )
    assert ent.available is True
