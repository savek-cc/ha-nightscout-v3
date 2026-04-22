"""Tests for statistics.compute_all."""
from __future__ import annotations

import math
import time

import pytest

from custom_components.nightscout_v3.statistics import compute_all


def _entry(offset_seconds: int, sgv: int) -> dict:
    now_ms = 1_745_000_000_000
    return {"date": now_ms - offset_seconds * 1000, "sgv": sgv}


def test_empty_input_returns_zero_samples() -> None:
    result = compute_all([], window_days=14)
    assert result["sample_count"] == 0
    assert result["mean_mgdl"] == 0.0


def test_gmi_matches_formula() -> None:
    entries = [_entry(i * 300, 154) for i in range(288)]
    result = compute_all(entries, window_days=1)
    # GMI = 3.31 + 0.02392 * 154 = 6.99
    assert result["gmi_percent"] == pytest.approx(6.99, abs=0.01)


def test_tir_buckets_partition_to_100() -> None:
    # 50% in range, 20% low, 20% high, 5% very low, 5% very high
    entries = (
        [_entry(i, 120) for i in range(50)]
        + [_entry(100 + i, 60) for i in range(20)]
        + [_entry(200 + i, 200) for i in range(20)]
        + [_entry(300 + i, 50) for i in range(5)]
        + [_entry(400 + i, 260) for i in range(5)]
    )
    r = compute_all(entries, window_days=1)
    total = r["tir_in_range_percent"] + r["tir_low_percent"] + r["tir_high_percent"]
    # tir_very_low is a subset of tir_low; tir_very_high is a subset of tir_high
    assert total == pytest.approx(100.0, abs=0.1)
    assert r["tir_very_low_percent"] == pytest.approx(5.0, abs=0.5)
    assert r["tir_very_high_percent"] == pytest.approx(5.0, abs=0.5)


def test_sd_and_cv() -> None:
    entries = [_entry(i * 60, v) for i, v in enumerate([100, 120, 140, 160, 180])]
    r = compute_all(entries, window_days=1)
    assert r["mean_mgdl"] == pytest.approx(140.0)
    assert r["sd_mgdl"] == pytest.approx(31.62, abs=0.1)
    assert r["cv_percent"] == pytest.approx(22.59, abs=0.1)


def test_hba1c_dcct_matches_formula() -> None:
    entries = [_entry(i * 300, 150) for i in range(288)]
    r = compute_all(entries, window_days=1)
    # (150 + 46.7) / 28.7 = 6.85
    assert r["hba1c_dcct_percent"] == pytest.approx(6.85, abs=0.01)


def test_hourly_profile_has_24_buckets() -> None:
    entries = [_entry(h * 3600, 100 + h) for h in range(24)]
    r = compute_all(entries, window_days=1)
    assert len(r["hourly_profile"]) == 24
    assert all(b["hour"] == i for i, b in enumerate(r["hourly_profile"]))


def test_agp_percentiles_are_ordered() -> None:
    entries = [_entry(i * 300, 100 + (i % 60)) for i in range(720)]
    r = compute_all(entries, window_days=1)
    assert len(r["agp_percentiles"]) == 24
    for band in r["agp_percentiles"]:
        if band["n"] == 0:
            continue
        assert band["p5"] <= band["p25"] <= band["p50"] <= band["p75"] <= band["p95"]


def test_lbgi_hbgi_are_nonnegative() -> None:
    entries = [_entry(i * 300, v) for i, v in enumerate([55, 70, 100, 140, 200, 260])]
    r = compute_all(entries, window_days=1)
    assert r["lbgi"] >= 0
    assert r["hbgi"] >= 0
