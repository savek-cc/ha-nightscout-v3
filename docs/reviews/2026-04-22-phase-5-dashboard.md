# Phase 5 Review — Dashboard

**Reviewer**: superpowers:code-reviewer (subagent)
**Date**: 2026-04-22
**Commits under review**: `e556165`, `a4f4e22`
**Follow-up fix commit**: `d008197`

## Scope

- `dashboards/nightscout.yaml` — 5-view user dashboard
- `dashboards/examples/{bg_card,agp_card,loop_card}.yaml`
- `tests/dashboards/test_yaml_shape.py`, `test_examples.py`

## Findings

### Critical

**C-1. AGP attribute names referenced in YAML did not exist at runtime.**
- `stat_agp_14d` extractor `stats.14d.agp_summary` was aliased in
  `coordinator._stats_cycle` to the raw `agp_percentiles` list.
- Sensor platform wraps lists as `extra_state_attributes = {"items": [...]}`.
- So `p05_by_hour` … `p95_by_hour` attributes were fabricated — AGP view
  and example card would render blank.
- **Fixed in `d008197`**: coordinator now builds `agp_summary` as a dict
  with `p5_by_hour`, `p25_by_hour`, `p50_by_hour`, `p75_by_hour`,
  `p95_by_hour` lists (24 entries each), plus `sample_count` and raw
  `items`. Dicts pass through as attributes directly. YAML updated to
  `p5_by_hour` (not `p05_*`). New coordinator test pins the shape.

### Important

**I-1. Test regex soundness.**  Confirmed adequate — no false negatives.
Validates both `sensor.nightscout_v3_*` and `binary_sensor.nightscout_v3_*`
against static + 14 d stats feature keys.

**I-2. HACS prerequisites.**  Dashboard relies on `custom:apexcharts-card`,
`custom:mushroom-*`, `custom:mini-graph-card`, `custom:card-mod`. The
shipped YAML has a header comment calling this out; README/docs/dashboard-setup
need to list these as prerequisites in Phase 6.

**I-3. `opacity` at apexcharts series level is not a valid key.** Harmless
(ignored at runtime) but misleading. **Fixed in `d008197`**: dropped opacity
from both the main dashboard and the example snippet.

### Minor

- **M-1** `mdi:water` icon ambiguous for BG — left as-is.
- **M-2/M-3/M-4** No action required.

## Verdict

**Approved after C-1/I-3 fix**. AGP chart path is now honest; every entity
reference resolves to a real feature key; coverage 95.25%; 137 tests pass.
