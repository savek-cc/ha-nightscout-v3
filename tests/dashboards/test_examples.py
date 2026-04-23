"""Every example snippet must be valid YAML, non-empty, and reference only
known feature keys.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from homeassistant.const import Platform

from custom_components.nightscout_v3.feature_registry import (
    FEATURE_REGISTRY,
    stats_feature_defs,
)

EXAMPLES = Path("dashboards/examples")
SNIPPETS = ["bg_card.yaml", "agp_card.yaml", "loop_card.yaml"]


def _known_sensor_keys() -> set[str]:
    static = {f.key for f in FEATURE_REGISTRY if f.platform == Platform.SENSOR}
    stats = {f.key for f in stats_feature_defs(14) if f.platform == Platform.SENSOR}
    return static | stats


def _known_binary_keys() -> set[str]:
    return {f.key for f in FEATURE_REGISTRY if f.platform == Platform.BINARY_SENSOR}


@pytest.mark.parametrize("name", SNIPPETS)
def test_example_is_valid_yaml(name: str) -> None:
    data = yaml.safe_load((EXAMPLES / name).read_text(encoding="utf-8"))
    assert data is not None
    assert isinstance(data, dict | list)


@pytest.mark.parametrize("name", SNIPPETS)
def test_example_references_known_features(name: str) -> None:
    text = (EXAMPLES / name).read_text(encoding="utf-8")
    sensors = set(re.findall(r"\bsensor\.nightscout_v3_([a-z_0-9]+)", text))
    bins = set(re.findall(r"\bbinary_sensor\.nightscout_v3_([a-z_0-9]+)", text))
    unknown_s = sensors - _known_sensor_keys()
    unknown_b = bins - _known_binary_keys()
    assert not unknown_s, f"{name} references unknown sensors: {sorted(unknown_s)}"
    assert not unknown_b, f"{name} references unknown binary sensors: {sorted(unknown_b)}"
