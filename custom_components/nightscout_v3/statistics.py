"""Pure-Python diabetes statistics computations (no IO, no HA deps)."""
from __future__ import annotations

import math
import time
from typing import Any

TIR_LOW = 70
TIR_HIGH = 180
TIR_VERY_LOW = 54
TIR_VERY_HIGH = 250


def compute_all(
    entries: list[dict[str, Any]],
    window_days: int,
    *,
    tir_low: int = TIR_LOW,
    tir_high: int = TIR_HIGH,
    tir_very_low: int = TIR_VERY_LOW,
    tir_very_high: int = TIR_VERY_HIGH,
) -> dict[str, Any]:
    """Compute all statistics for a window of entries. Empty input returns zeroed payload."""
    sgvs = [int(e["sgv"]) for e in entries if e.get("sgv") is not None]
    n = len(sgvs)

    if n == 0:
        return _empty_payload(window_days)

    mean = sum(sgvs) / n
    variance = sum((x - mean) ** 2 for x in sgvs) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(variance)
    cv = (sd / mean * 100) if mean else 0.0

    gmi = 3.31 + 0.02392 * mean
    hba1c_dcct = (mean + 46.7) / 28.7

    tir_in = 100 * sum(tir_low <= x <= tir_high for x in sgvs) / n
    tir_lo = 100 * sum(x < tir_low for x in sgvs) / n
    tir_vlo = 100 * sum(x < tir_very_low for x in sgvs) / n
    tir_hi = 100 * sum(x > tir_high for x in sgvs) / n
    tir_vhi = 100 * sum(x > tir_very_high for x in sgvs) / n

    lbgi, hbgi = _bgi(sgvs)

    return {
        "window_days": window_days,
        "sample_count": n,
        "mean_mgdl": round(mean, 2),
        "sd_mgdl": round(sd, 2),
        "cv_percent": round(cv, 2),
        "gmi_percent": round(gmi, 2),
        "hba1c_dcct_percent": round(hba1c_dcct, 2),
        "tir_in_range_percent": round(tir_in, 2),
        "tir_low_percent": round(tir_lo, 2),
        "tir_very_low_percent": round(tir_vlo, 2),
        "tir_high_percent": round(tir_hi, 2),
        "tir_very_high_percent": round(tir_vhi, 2),
        "lbgi": round(lbgi, 2),
        "hbgi": round(hbgi, 2),
        "hourly_profile": _hourly_profile(entries),
        "agp_percentiles": _agp_percentiles(entries),
        "computed_at_ms": int(time.time() * 1000),
    }


def _empty_payload(window_days: int) -> dict[str, Any]:
    return {
        "window_days": window_days,
        "sample_count": 0,
        "mean_mgdl": 0.0,
        "sd_mgdl": 0.0,
        "cv_percent": 0.0,
        "gmi_percent": 0.0,
        "hba1c_dcct_percent": 0.0,
        "tir_in_range_percent": 0.0,
        "tir_low_percent": 0.0,
        "tir_very_low_percent": 0.0,
        "tir_high_percent": 0.0,
        "tir_very_high_percent": 0.0,
        "lbgi": 0.0,
        "hbgi": 0.0,
        "hourly_profile": [
            {"hour": h, "mean": 0, "median": 0, "min": 0, "max": 0, "n": 0}
            for h in range(24)
        ],
        "agp_percentiles": [
            {"hour": h, "p5": 0, "p25": 0, "p50": 0, "p75": 0, "p95": 0, "n": 0}
            for h in range(24)
        ],
        "computed_at_ms": int(time.time() * 1000),
    }


def _bgi(sgvs: list[int]) -> tuple[float, float]:
    """Low Blood Glucose Index & High Blood Glucose Index (Kovatchev 1997)."""
    low = 0.0
    high = 0.0
    for x in sgvs:
        f = 1.509 * (math.log(max(x, 1)) ** 1.084 - 5.381)
        rl = 10 * (f**2) if f < 0 else 0.0
        rh = 10 * (f**2) if f > 0 else 0.0
        low += rl
        high += rh
    return low / len(sgvs), high / len(sgvs)


def _bucket_by_hour(entries: list[dict[str, Any]]) -> list[list[int]]:
    buckets: list[list[int]] = [[] for _ in range(24)]
    for e in entries:
        sgv = e.get("sgv")
        date = e.get("date")
        if sgv is None or date is None:
            continue
        h = int((int(date) // 1000 % 86_400) // 3600)
        buckets[h].append(int(sgv))
    return buckets


def _hourly_profile(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = _bucket_by_hour(entries)
    out = []
    for h, xs in enumerate(buckets):
        if not xs:
            out.append({"hour": h, "mean": 0, "median": 0, "min": 0, "max": 0, "n": 0})
            continue
        xs_sorted = sorted(xs)
        out.append(
            {
                "hour": h,
                "mean": round(sum(xs) / len(xs), 2),
                "median": xs_sorted[len(xs) // 2],
                "min": xs_sorted[0],
                "max": xs_sorted[-1],
                "n": len(xs),
            }
        )
    return out


def _percentile(sorted_values: list[int], q: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(sorted_values[int(k)])
    return sorted_values[lo] * (hi - k) + sorted_values[hi] * (k - lo)


def _agp_percentiles(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = _bucket_by_hour(entries)
    out = []
    for h, xs in enumerate(buckets):
        if not xs:
            out.append({"hour": h, "p5": 0, "p25": 0, "p50": 0, "p75": 0, "p95": 0, "n": 0})
            continue
        sorted_xs = sorted(xs)
        out.append(
            {
                "hour": h,
                "p5": round(_percentile(sorted_xs, 0.05), 2),
                "p25": round(_percentile(sorted_xs, 0.25), 2),
                "p50": round(_percentile(sorted_xs, 0.50), 2),
                "p75": round(_percentile(sorted_xs, 0.75), 2),
                "p95": round(_percentile(sorted_xs, 0.95), 2),
                "n": len(xs),
            }
        )
    return out
