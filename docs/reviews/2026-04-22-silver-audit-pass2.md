# Silver Quality Scale audit — ha-nightscout-v3 (pass 2)

Date: 2026-04-22
Auditor: Senior Code Reviewer
Scope: Integration source (`custom_components/nightscout_v3/**`) and tests (`tests/**`) only. Dashboards and README content excluded per Phase 5/6 sign-off.
Base: follow-up to `docs/reviews/2026-04-22-silver-audit.md`; verifies commits `54a86a6`, `ccf5ac0`, `6942ae9`, `cd09905`.

## Summary

All four gaps from pass 1 (C-1 config-flow coverage, C-2 brands rule / manifest mismatch, M-1 reauth unique_id pin, M-2 diagnostics typing) land exactly where the commit messages claim. Full pytest run: **168 passed**; `config_flow.py` now reports **100 % stmt and 100 % branch** coverage (141 stmts, 22/22 branches). `scripts/verify_silver --strict-manifest` exits 0 with `silver: ok`. No regressions observed — the four touched files are consistent with the rest of the integration, and items previously marked passing (runtime-data typing, PARALLEL_UPDATES, has-entity-name, coordinator unavailability, translations parity, test-coverage gate at 95 %) remain green.

## Fix verification

| id  | status | evidence (file:line)                                                                               |
| --- | ------ | -------------------------------------------------------------------------------------------------- |
| C-1 | closed | `tests/test_config_flow.py:99-125` submits features form and asserts `CREATE_ENTRY` + merged `enabled_features` (`bg_current: False`, `pump_reservoir: True`, untouched `stats_windows`). Coverage run: `config_flow.py  141  0  22  0  100%`. |
| C-2 | closed | `custom_components/nightscout_v3/quality_scale.yaml:7-13` — `brands: status: exempt` with a five-line comment explicitly referencing HACS-only distribution and the `home-assistant/brands` registry. `verify_silver.py --strict-manifest` returns `silver: ok` (stdout). |
| M-1 | closed | `custom_components/nightscout_v3/config_flow.py:134-140` — inside `async_step_reauth_confirm`, `await self.async_set_unique_id(reauth_entry.unique_id)` + `self._abort_if_unique_id_mismatch()` run immediately before `async_update_reload_and_abort(...)`. |
| M-2 | closed | `custom_components/nightscout_v3/diagnostics.py:10` imports `NightscoutConfigEntry` from `.models`; signatures at `:16` (`async_get_config_entry_diagnostics`) and `:31` (`_collect_runtime`) use it. No `from homeassistant.config_entries import ConfigEntry` remains in the file. |

## Regression spot-checks

- **Options flow submit branch**: test at `test_config_flow.py:99-125` passes cleanly and exercises the `Category` loop + `current.update(...)` path at `config_flow.py:202-206`. Existing options sub-step tests (stats, thresholds, polling, rediscover) still pass.
- **Reauth happy path**: `test_reauth_happy_path` (`test_config_flow.py:174-197`) still returns `reauth_successful` after the unique_id pin — confirms the new guard does not block the current URL-fixed reauth form. Parametrised error cases (`invalid_auth` / `cannot_connect` / `unknown`) unaffected.
- **Diagnostics typing**: all 4 tests in `tests/test_diagnostics.py` pass. The function signatures accept `MockConfigEntry` at runtime because `NightscoutConfigEntry` is a PEP 695 `type` alias of `ConfigEntry[NightscoutData]` (`models.py:28`) — pure structural change, no runtime surface.
- **quality_scale.yaml shape**: `verify_silver.check_quality_scale_yaml` correctly enforces the "exempt requires a non-empty comment" rule (`scripts/verify_silver.py:62-66`); the new `brands` entry has a multi-line folded comment, so the check passes.
- **manifest ↔ scale consistency**: `manifest.json:11` declares `"quality_scale": "silver"`; every rule in `SILVER_RULES_REQUIRED` (`scripts/verify_silver.py:19-27`) is either `done` or `exempt` in `quality_scale.yaml`.
- **Coverage gate**: global coverage 95.51 % (gate 95 %), all 168 tests pass in 3.43 s. `config_flow.py` and `diagnostics.py` both at 100 %. No file regressed vs pass 1.

## New findings

None. No new issues introduced by the four fixes. The `ConfigEntry` import still present in `__init__.py:7` is legitimate (the `_async_update_listener` signature at `:112` is the callback for `add_update_listener`, which is not specific to this entry's runtime_data type) — not a typing inconsistency.

## Verdict

**Silver: approved.** Zero gaps remain. Green light for the Task 7.5 final release review.
