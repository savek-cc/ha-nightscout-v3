"""Smoke tests for the shipped dashboard YAML.

The dashboard is a convention — it assumes the user's config entry produces
entities named ``sensor.nightscout_v3_<feature_key>`` / ``binary_sensor.nightscout_v3_<feature_key>``.
If the config entry title differs, users search-and-replace as documented in
``docs/dashboard-setup.md``. These tests enforce that every referenced entity
key resolves to a real feature in ``FEATURE_REGISTRY`` or
``stats_feature_defs(14)`` (14 d is a mandatory window, see spec §4.5).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from custom_components.nightscout_v3.feature_registry import (
    FEATURE_REGISTRY,
    stats_feature_defs,
)
from homeassistant.const import Platform

DASH = Path("dashboards/nightscout.yaml")

REQUIRED_VIEWS = {"Übersicht", "Trend", "AGP", "Statistik", "Loop"}


def _load_dashboard() -> dict:
    return yaml.safe_load(DASH.read_text(encoding="utf-8"))


def test_dashboard_parses() -> None:
    data = _load_dashboard()
    assert isinstance(data, dict)
    assert "views" in data


def test_has_required_views() -> None:
    data = _load_dashboard()
    titles = {v.get("title") for v in data["views"]}
    assert REQUIRED_VIEWS <= titles, f"missing views: {REQUIRED_VIEWS - titles}"


def _known_sensor_keys() -> set[str]:
    static = {f.key for f in FEATURE_REGISTRY if f.platform == Platform.SENSOR}
    stats_14d = {f.key for f in stats_feature_defs(14) if f.platform == Platform.SENSOR}
    return static | stats_14d


def _known_binary_keys() -> set[str]:
    return {f.key for f in FEATURE_REGISTRY if f.platform == Platform.BINARY_SENSOR}


def test_sensor_references_resolve_to_feature_keys() -> None:
    text = DASH.read_text(encoding="utf-8")
    referenced = set(re.findall(r"\bsensor\.nightscout_v3_([a-z_0-9]+)", text))
    known = _known_sensor_keys()
    unknown = referenced - known
    assert not unknown, f"dashboard references unknown sensor keys: {sorted(unknown)}"


def test_binary_sensor_references_resolve_to_feature_keys() -> None:
    text = DASH.read_text(encoding="utf-8")
    referenced = set(re.findall(r"\bbinary_sensor\.nightscout_v3_([a-z_0-9]+)", text))
    known = _known_binary_keys()
    unknown = referenced - known
    assert not unknown, f"dashboard references unknown binary_sensor keys: {sorted(unknown)}"
