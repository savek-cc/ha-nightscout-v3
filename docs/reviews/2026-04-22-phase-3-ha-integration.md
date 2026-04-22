# Phase 3 Review — HA Integration Layer

**Reviewer:** code-reviewer subagent
**Date:** 2026-04-22
**Scope:** commits `3f3719f`, `6861418`, `7fcbed0`, `de44954`, `605cd83`, `43cc055`, `df05fc2`, `5f4dd8e`
**Plan reference:** `docs/plans/2026-04-22-ha-nightscout-v3-plan.md` Phase 3 (lines 2463–4266)
**Silver reference:** `docs/references/ha-silver-quality-scale.md`

---

## Verdict

**Request changes (minor) — approve with one blocking-flavored fix.**

Phase 3 lands a coherent HA integration layer that satisfies the Silver
structural rules on paper (runtime-data, has-entity-name, unique-id, parallel-
updates, reauth, test-before-configure/setup, unique-config-entry, integration-
owner). All 75 tests pass and the per-module coverage on the high-signal files
is respectable. Two items keep this from being a clean "Approve":

1. **I-1 (important).** The stats sensors declare their friendly name via a
   `{window}` placeholder in the translations but the base entity never sets
   `_attr_translation_placeholders`. That's a known HA 2026.x pitfall
   (recorded in the user's own feedback file `feedback_ha_translation_placeholders.md`):
   with `has_entity_name=True`, HA will render the literal string
   `"Mean BG ({window}d)"`, and every stats entity for a given window will
   collide on that name because the `translation_key` is shared across windows.
2. **I-2 (important).** `quality_scale.yaml` still lists every Silver rule as
   `todo` even though Phase 3 delivered them. This is cosmetic but the file
   is what hassfest reads; leaving it `todo` hides progress and will
   embarrassingly flip on a `brands` PR review.

Neither breaks tests or the happy path, but (1) will visibly degrade the UX
on first install and I'd want it fixed before Phase 4 builds dashboards on
top of the entity names. Everything else is nits or "fill me in later"
coverage gaps that fall out naturally in Phases 4–7.

---

## Summary of work reviewed

Phase 3 adds `entity.py` (shared base with unique-id / has-entity-name /
device-info / dotted-path extractor / `available` override), `coordinator.py`
(staggered fast 60 s / change-detect 5 min / stats 60 min cycles with
`_tick`-based scheduling and a full `_build_payload` that projects bg / pump
/ loop / uploader / care blocks), `__init__.py` + `models.py` (runtime-data
typed `ConfigEntry[NightscoutData]`, test-before-setup via
`ConfigEntryAuthFailed` / `ConfigEntryNotReady`, JWT background refresh via
`async_track_time_interval`, clean unload), `config_flow.py` (user step with
sha256-unique-id-before-probe, reauth, and a 5-branch options flow), sensor /
binary_sensor platforms (`PARALLEL_UPDATES = 0`, registry-driven), and
diagnostics (redacted). Entity-level translations for all 36 durable + 14 stat
+ 3 binary keys were added to `strings.json` and `translations/en.json`.

---

## Silver Quality Scale compliance

| Rule | Status | Notes |
|---|---|---|
| `runtime-data` | ✓ | `entry.runtime_data = NightscoutData(...)` at `__init__.py:87`; consumers read via `entry.runtime_data`. No `hass.data[DOMAIN]` cache anywhere. |
| `has-entity-name` | ~ | `_attr_has_entity_name = True` at `entity.py:20`. Platforms inherit. **But** stats entities need `translation_placeholders` to render `{window}` — see I-1. |
| `entity-unique-id` | ✓ | `self._attr_unique_id = f"{entry_id}_{feature.key}"` (`entity.py:26`). Stats keys already embed the window suffix via `stats_feature_defs`, so uniqueness survives multi-window. |
| `parallel-updates` | ✓ | `PARALLEL_UPDATES = 0` at `sensor.py:17` and `binary_sensor.py:14`. Correct for coordinator-backed read-only platforms. |
| `config-entry-unloading` | ✓ | `async_unload_entry` at `__init__.py:101` calls `async_unload_platforms` first, then `jwt_refresh_unsub()` → `coordinator.async_shutdown()` → `store.close()`. Ordering is correct (platforms must release entities before the coordinator dies). The update-listener subscription is released automatically by `entry.async_on_unload(...)` (`__init__.py:97`). |
| `entity-unavailable` | ✓ | `NightscoutEntity.available` (`entity.py:51–56`) combines coordinator success with a `None`-check on the extracted value — the stricter side of the Silver contract. |
| `reauthentication-flow` | ✓ | `async_step_reauth` + `async_step_reauth_confirm` at `config_flow.py:111–144`. Uses `self._get_reauth_entry()` and `async_update_reload_and_abort`, which is the 2024.11+ blessed helper. `invalid_auth` / `cannot_connect` / `unknown` are all covered by parametrized tests. |
| `test-before-configure` | ✓ | `async_step_user` calls `JwtManager.initial_exchange()` then `probe_capabilities()` *before* `async_create_entry`. `async_set_unique_id` + `_abort_if_unique_id_configured` run *before* probing — good, we don't probe a server we'll just reject. |
| `test-before-setup` | ✓ | `async_setup_entry` raises `ConfigEntryAuthFailed` on `AuthError` and `ConfigEntryNotReady` on `ApiError` before `async_forward_entry_setups` is called (`__init__.py:44–55`). Same pattern wrapped in the coordinator — `_async_update_data` maps `AuthError` → `ConfigEntryAuthFailed` and `ApiError` → `UpdateFailed`. Two-layer defense is good. |
| `unique-config-entry` | ✓ | `_unique_id` = sha256(_normalize(url))[:16] at `config_flow.py:61–70`. Normalizer strips trailing slashes + defaults scheme to `https`. `test_user_step_duplicate_aborts` verifies the abort path. |
| `log-when-unavailable` | ✓ | Delegated to `DataUpdateCoordinator` (Silver reference §3.7): `_async_update_data` raises `UpdateFailed` on `ApiError`/`TimeoutError`/`OSError` → HA logs once and suppresses. No manual `_LOGGER.warning` spam in the update loop. |
| `integration-owner` | ✓ | `manifest.json:4` — `"codeowners": ["@savek-cc"]`. `config_flow: true` also present. |

Legend: ✓ pass, ~ pass with caveat, ✗ fail.

---

## Critical findings

*None.* Nothing blocks the platform from loading or the tests from passing.

---

## Important findings

### I-1. Stats sensor names will render literal `{window}` and collide on friendly name

**Files:** `custom_components/nightscout_v3/entity.py` (no placeholder setter),
`custom_components/nightscout_v3/strings.json:108–121` (14 `stat_*` entries
with `{window}` in the `name` template), `translations/en.json:108–121`
(same), `feature_registry.py:182–228` (`stats_feature_defs` reuses one
`translation_key` per sensor across all windows).

**What happens at runtime:** HA resolves `translation_key` → localized
`name`. If the name contains `{variable}` and no `translation_placeholders`
dict is supplied on the entity, HA (as of 2024.x / 2026.x behavior) leaves
the literal placeholder in the string. Result: every `stat_gmi_*` entity
across every window registers with the exact name `"Mean BG ({window}d)"`.
That collides on friendly name (HA will auto-suffix `_2`, `_3`, etc., which
is both ugly and order-dependent), and the unique-id stability story for
renaming in the UI is broken. For a user with three windows enabled (1d, 14d,
30d), they'd see `Mean BG ({window}d)`, `Mean BG ({window}d) 2`, `Mean BG
({window}d) 3` — not what the plan promised.

**User-feedback file that documents the fix:**
`feedback_ha_translation_placeholders.md` — use `_attr_translation_placeholders`
set inside `__init__`, not a `name_translation_placeholders` property
(the latter pattern no longer works).

**Suggested fix** (not implemented per review scope):

```python
# entity.py, inside NightscoutEntity.__init__ after setting translation_key:
# Stats feature keys look like "stat_gmi_14d"; extract the window suffix if any.
if feature.key.endswith("d") and "_" in feature.key:
    tail = feature.key.rsplit("_", 1)[-1]       # "14d"
    if tail[:-1].isdigit():
        self._attr_translation_placeholders = {"window": tail[:-1]}
```

A cleaner alternative is to add an explicit `translation_placeholders`
field to `FeatureDef` and set it in `stats_feature_defs`:

```python
# feature_registry.py, FeatureDef
translation_placeholders: dict[str, str] | None = None
# stats_feature_defs:
FeatureDef(f"stat_gmi_{w}d", ..., translation_placeholders={"window": str(w)})
# entity.py:
if feature.translation_placeholders:
    self._attr_translation_placeholders = dict(feature.translation_placeholders)
```

I prefer the latter — it's declarative, lives in the same table as the
translation_key, and doesn't rely on string-suffix inspection.

**Evidence this isn't already handled:** the Phase 3 test suite doesn't
instantiate a stats entity and assert on `entity.name`. `test_sensor.py`
only checks `sensor.test_bg_current` exists. The issue will surface the
first time a user opens their Entities page with ≥ 2 stats windows enabled.

### I-2. `quality_scale.yaml` still says `todo` for rules Phase 3 just delivered

**File:** `custom_components/nightscout_v3/quality_scale.yaml:2–44`.

Every Silver rule (and most Bronze ones) is tagged `todo`, but Phase 3
actually implements:

- Bronze: `config-flow`, `runtime-data`, `test-before-configure`,
  `test-before-setup`, `unique-config-entry`, `entity-unique-id`,
  `has-entity-name`
- Silver: `config-entry-unloading`, `entity-unavailable`, `integration-owner`,
  `log-when-unavailable`, `parallel-updates`, `reauthentication-flow`

These should be flipped to `done`. `test-coverage`, `brands`, and the
`docs-*` items are legitimately still `todo`. `appropriate-polling` could
argue `done` (coordinator + staggered cycles) or `todo` (waiting on docs).

Not a code-correctness issue, but hassfest scans this file on CI, and the
core-repo reviewer will read it before merging a HACS → core promotion PR.

### I-3. `_uploader_block` uses `or` as null-coalesce — swallows zero-battery readings

**File:** `custom_components/nightscout_v3/coordinator.py:350`.

```python
"battery_percent": ds.get("uploaderBattery") or (((ds.get("pump") or {}).get("battery") or {}).get("percent")),
```

If `uploaderBattery == 0` (dead uploader phone), the expression falls
through to pump battery. For the phone-on-the-charger case this matters;
for a diabetic whose phone died overnight, a sensor that silently reports
the pump's 80% as the uploader battery is deceptive.

Fix:

```python
ub = ds.get("uploaderBattery")
pump_pct = (((ds.get("pump") or {}).get("battery") or {}).get("percent"))
battery = ub if ub is not None else pump_pct
```

Low priority because (a) an uploader reading 0 is already a failure state
the user will notice other ways and (b) the existing BG stale-minutes sensor
catches the phone-offline case. Still worth the 3-line fix.

---

## Nit findings

### N-1. Unused import `math` in `coordinator.py:5`

`math` is imported but never referenced. `ruff` would catch this.

### N-2. Unused imports in `sensor.py:14`

`from .feature_registry import Category, FEATURE_REGISTRY, FeatureDef,
features_for_capabilities, stats_feature_defs` — `Category` and
`FEATURE_REGISTRY` are imported but only `FeatureDef`,
`features_for_capabilities`, and `stats_feature_defs` are used. Drop the two
unused names.

### N-3. Unused import `ServerCapabilities` at `coordinator.py:15`

The only reference is via the `capabilities` property type hint
(`coordinator.py:98`). The field `self._capabilities: ServerCapabilities` is
type-elided by `from __future__ import annotations`, so the runtime import
is technically redundant — but it's needed for Sphinx / IDE introspection
and the property annotation is load-bearing. Leave as-is; this is fine.

### N-4. Unused import `ConfigEntryNotReady` at `coordinator.py:12`

`ConfigEntryNotReady` is imported but never raised. The coordinator maps
`ApiError` → `UpdateFailed`, not `ConfigEntryNotReady` (HA core translates
`UpdateFailed` from the first refresh into `ConfigEntryNotReady`
automatically). Drop the import or leave a comment that it's reserved.

### N-5. `ConfigEntry` import in `models.py:7` could be behind `TYPE_CHECKING`

`models.py` uses `ConfigEntry` only in the `type NightscoutConfigEntry =
ConfigEntry[NightscoutData]` type alias. With `from __future__ import
annotations` this *could* be under a `TYPE_CHECKING` block, but since
`type X = ...` statements (PEP 695) are evaluated at runtime the import
must stay runtime. Leave as-is.

### N-6. `CONF_URL` double sourcing

`config_flow.py:16` imports `CONF_URL` from `homeassistant.const`, but
`__init__.py:18` imports `CONF_URL` from `.const` (which also defines it).
Both resolve to the string `"url"`, so behavior is identical, but the
inconsistency invites future drift (e.g., someone renames `.const.CONF_URL`).
Pick one source — preferably `homeassistant.const` since HA owns the
canonical name.

### N-7. Options-flow `rediscover` may double-reload

**File:** `config_flow.py:263–283`.

`async_step_rediscover` calls `async_update_entry` (which fires the update
listener → reload) then returns `async_create_entry` with the existing
options (which also fires the listener → another reload). Tested by
`test_options_rediscover_updates_capabilities`, which only asserts
`CREATE_ENTRY` — it doesn't observe the double-reload. In practice the
second reload is a no-op on unchanged options, but it's wasteful and could
surface as test flakes under slower CI. Consider passing fresh data+options
in a single `async_update_entry` and then `self.async_abort(reason="...")`.

### N-8. Late `from pathlib import Path` inside `async_setup_entry`

**File:** `__init__.py:67–68`.

The import is lazy inside the function. Not a functional problem, but it
bucks the module-top-imports convention used everywhere else. Move to the
top of the file.

### N-9. `binary_sensor.py` does not import `OPT_STATS_WINDOWS` or stats features

That's correct (stats are sensor-only), and explicitly OK by the plan. No
action needed — noting for reviewers who scan imports defensively.

### N-10. `test_coordinator.py` tests don't exercise `_change_detect_cycle` or `_stats_cycle`

Three tests (`test_first_refresh_populates_data`, `test_auth_error_*`,
`test_api_error_*`) only touch the fast cycle. The 86% line coverage reflects
this. See "Coverage analysis" below.

### N-11. `diagnostics.py:48 snapshot` dumps raw coordinator data

`data.coordinator.data` could contain the `loop.reason` free-text AAPS log
or `care.last_note` — both user-free-text fields. The redaction set doesn't
include them. Low risk because the dump is local-download-only, but worth
a note: consider redacting `reason` and `last_note` if the diagnostics file
is intended for bug reports that might be pasted into public issues.

### N-12. No test asserts `coordinator.async_shutdown()` was awaited on unload

`test_setup_and_unload` asserts the entry ends in `NOT_LOADED` but doesn't
patch a spy on `async_shutdown` / `store.close` to verify they were called.
If `runtime_data = None` after unload (the code doesn't set it to None — HA
core handles entry lifecycle), and `async_unload_platforms` returns False,
the cleanup is silently skipped. Add a 2-line assertion in a follow-up
commit.

---

## Coverage analysis

| Module | Stmts covered | Notes on uncovered lines |
|---|---|---|
| `diagnostics.py` | 48% | Only the happy-path `async_get_config_entry_diagnostics` with redaction is exercised. Uncovered: `_collect_runtime` with real `runtime_data` (the test patches it out). **Recommend closing** with a fixture that builds a fake `NightscoutData` and verifies `jwt.exp_in_seconds` is computed correctly + `snapshot` is present. This is the cheapest coverage win in the phase (~5 minutes). |
| `__init__.py` | 77% | Uncovered: the `ConfigEntryAuthFailed` branch (AuthError from `jwt_manager.initial_exchange`), the `ConfigEntryNotReady` branch (ApiError from `probe_capabilities`), and the `_refresh_jwt` callback's error handling (`AuthError` → warning, `ApiError` → debug). **Important to close** for test-before-setup Silver rule — it's the whole point of the rule. Two parametrized tests at ~10 lines each. **Recommend closing before Phase 3 is declared done.** |
| `entity.py` | 81% | Uncovered: `_extract` fall-through when `data` is a non-dict non-object (unreachable on realistic payloads), and `available` returning False from `_extract() is None`. **Recommend closing** the `available=False` branch — it's the visible face of `entity-unavailable`. |
| `coordinator.py` | 86% | Uncovered: `_change_detect_cycle` when entries_lm > cached (whole treatments-aware refresh block), `_stats_cycle` happy path (computing + caching stats), and the `OSError`/`TimeoutError` → `UpdateFailed` branch. **Important to close** — this is the integration's core loop and the `log-when-unavailable` rule's evidence. **Phase 7 smoke tests will hit it organically, but a dedicated unit test in Phase 3 polish would be higher-signal.** |
| `config_flow.py` | 88% | Uncovered: reauth with `self._url = None` edge case (happens when `async_step_reauth_confirm` is called directly without `async_step_reauth`), and the `async_step_thresholds` + `async_step_polling` happy paths (menu-driven sub-steps). **Recommend closing** the sub-step happy paths — it's 2 short tests and lifts this to ~95%. **Defer** the `self._url is None` corner. |

### What to close in a Phase-3-polish commit

1. `__init__.py` auth + not-ready branches → +~5 pp, makes test-before-setup
   defensible.
2. `entity.py` `available=False` branch → +~5 pp, demonstrates entity-
   unavailable compliance.
3. `diagnostics.py` real-runtime path → +~40 pp on that module.
4. `config_flow.py` thresholds + polling happy paths → +~5 pp.
5. I-1 fix (translation_placeholders) and associated test.

All five together are a ~30-minute commit and would put the full project
over the 95% gate set in `pyproject.toml`.

### What to defer to Phase 7

- `coordinator.py` `_change_detect_cycle` / `_stats_cycle` / `OSError`
  branches. These need a multi-tick simulation that is easier to express as
  an integration smoke test against recorded fixtures than as a tight
  unit test.
- `config_flow.py` reauth-with-missing-url edge case.
- `entity.py` non-dict fall-through in `_extract`.

---

## Plan-alignment notes

No behavioral drift from the Phase 3 spec. The three "plan-bug corrections"
called out in the prompt are all correct:

1. `test_init.py` patches `nightscout_v3.probe_capabilities` (not
   `api.capabilities.probe_capabilities`) — required because `__init__.py`
   does `from .api.capabilities import probe_capabilities`, which binds
   the name in the `__init__` module namespace. Patching the definition
   site wouldn't hit the rebound name. Same story for `JwtManager`.
   Correct.
2. `test_init.py` patches `_PLATFORMS = []` — a scoped pragmatic workaround
   to avoid the sensor platform trying to hit the state machine during
   a setup/unload smoke test. Acceptable; the sensor path has its own test.
3. Entity translations (36 + 14 + 3 = 53 keys) added to both `strings.json`
   and `translations/en.json`. This is a plan extension, not a drift —
   the plan ended at Task 3.7 / 3.8 without specifying entity strings,
   but `has_entity_name=True` without a translation key yields an empty
   name. Correct to fold in.

### Minor plan-vs-code gaps that aren't drift

- Plan `:3237` lazy-imports `Path` inside `async_setup_entry`; code preserves
  the same pattern (N-8 above). Not a drift, just a nit inherited from the
  plan.
- Plan does not mention `translation_placeholders` for stats — this is the
  root cause of I-1. So the plan itself needs updating alongside the fix.

---

## Recommendation

**Merge-ready with a short Phase-3-polish commit.** Suggested sequence:

1. Fix I-1: add `translation_placeholders` field to `FeatureDef`, populate
   it in `stats_feature_defs`, and apply it in `NightscoutEntity.__init__`.
   Add a test that instantiates a `stat_gmi_14d` sensor and asserts
   `entity.translation_placeholders == {"window": "14"}`. Update plan
   alongside.
2. Fix I-2: flip the 13 Silver/Bronze `todo` rules to `done` in
   `quality_scale.yaml`, keep `test-coverage` / `docs-*` / `brands` as
   `todo`.
3. Fix I-3: replace `or`-based null-coalesce in `_uploader_block`.
4. Close the 4 cheap coverage gaps from the list above (diagnostics +
   __init__ auth/not-ready + entity available=False + thresholds/polling
   happy paths). This lifts total coverage from 91% through the 95% gate
   set in `pyproject.toml`.
5. Update `docs/plans/2026-04-22-ha-nightscout-v3-plan.md` with a short
   note under Phase 3 review describing the stats-placeholder issue (so
   Phase 4 doesn't re-surface it).

After that, Phase 3 is cleanly `done` and Phase 4 can start on dashboards
and docs with a known-good entity-name contract.

---

*End of report.*
