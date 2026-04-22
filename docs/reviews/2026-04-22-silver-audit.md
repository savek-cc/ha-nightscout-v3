# Silver Quality Scale audit — ha-nightscout-v3

Date: 2026-04-22
Auditor: Senior Code Reviewer
Scope: Integration source (`custom_components/nightscout_v3/**`) and tests (`tests/**`) only. Dashboards and README content excluded per Phase 5/6 sign-off.

## Summary

The integration largely satisfies the Silver bar. Runtime data, common modules, typed config entry, reauth flow, PARALLEL_UPDATES on both platforms, coordinator-driven unavailability/logging, and options-flow-backed polling intervals are all in place. Tests pass (168/168) with total coverage 95.25 % — above the 95 % gate.

However the tier is **blocked by two must-fix gaps**:

1. `config-flow-test-coverage` is a **100 %** rule. `config_flow.py` sits at **98 %** — lines 201-202 (the features options-flow submit branch) are never executed by any test.
2. `quality_scale.yaml` still carries `brands: status: todo`, while `manifest.json` already declares `"quality_scale": "silver"`. A Silver declaration is only valid once every Bronze + Silver rule is `done` or `exempt`. For a HACS-only custom component `brands` is soft-enforced, but the two files must agree: either flip `brands` to `done` after the `home-assistant/brands` PR, or mark `exempt` with a comment. Leaving it `todo` while the manifest claims Silver is internally inconsistent and hassfest will flag it if the component is ever submitted to core.

Additionally one **minor** deviation: the reauth flow never calls `async_set_unique_id` + `_abort_if_unique_id_mismatch`. Low practical risk because the reauth form only takes a new token (URL cannot change), but the reference doc explicitly prescribes the pattern.

## Rule-by-rule table

| Rule | Self-declared | Verified | Evidence |
|---|---|---|---|
| **Bronze** | | | |
| action-setup | exempt | pass | No `hass.services.async_register` anywhere under `custom_components/nightscout_v3/`. v0.1.0 registers no services. `quality_scale.yaml:3-5` exempt with comment. |
| appropriate-polling | done | pass | `coordinator.py:78-84` `update_interval=timedelta(seconds=COORDINATOR_TICK_SECONDS)` with tick = 30 s; user-visible cadences read from options (`coordinator.py:117-124`). Options flow exposes `poll_fast_seconds`, `poll_change_detect_minutes`, `poll_stats_minutes` (`config_flow.py:248-261`). |
| brands | todo | **fail** | `quality_scale.yaml:7-9` still `todo`. `manifest.json:11` already declares `"quality_scale": "silver"`. Tier is only valid when every rule at that tier and below is `done` or `exempt`. Must resolve. |
| common-modules | done | pass | `custom_components/nightscout_v3/coordinator.py` houses `NightscoutCoordinator(DataUpdateCoordinator)`; `entity.py` houses `NightscoutEntity(CoordinatorEntity)`. `__init__.py` contains only setup/unload. |
| config-flow-test-coverage | done | **fail** | `.venv/bin/python -m pytest` reports `config_flow.py` at **98 %**, missing lines **201-202** — the submit branch of `async_step_features` (`config_flow.py:200-204`). Rule requires 100 %. |
| config-flow | done | pass | `manifest.json:5` `"config_flow": true`. `config_flow.py:73` `class NightscoutConfigFlow(ConfigFlow, domain=DOMAIN)` with `async_step_user` at `:83`. Secrets in `data`, tunables in `options` (`:152-171`). `strings.json:8-14` has both `data` and `data_description` for every user-step field. All three error keys and `already_configured` abort translated (`strings.json:30-38`). |
| dependency-transparency | done | pass | `manifest.json:12` `"requirements": ["aiosqlite==0.20.0", "orjson==3.10.7"]` — both pinned, OSI-licensed, on PyPI with public GitHub provenance. |
| docs-actions | exempt | pass | Taken at face value per audit scope; no services registered to document. |
| docs-high-level-description | done | pass | Taken at face value (Phase 6 review). |
| docs-installation-instructions | done | pass | Taken at face value (Phase 6 review). |
| docs-removal-instructions | done | pass | Taken at face value (Phase 6 review). |
| entity-event-setup | exempt | pass | Entities subclass `CoordinatorEntity` only; no `async_added_to_hass`/`async_will_remove_from_hass` overrides under `entity.py`, `sensor.py`, `binary_sensor.py`. Exemption comment present (`quality_scale.yaml:26-30`). The JWT refresh timer in `__init__.py:83` is entry-level and cleaned up on unload (`:106`). |
| entity-unique-id | done | pass | `entity.py:26` `self._attr_unique_id = f"{entry_id}_{feature.key}"`. Entry id is stable across restarts; feature.key is unique per platform. Stats features carry a `_{w}d` suffix (`feature_registry.py:188-244`). |
| has-entity-name | done | pass | `entity.py:20` `_attr_has_entity_name = True`. `DeviceInfo` set at `:31-37` with `identifiers`, `manufacturer`, `model`, `name=entry.title`, `configuration_url`. Each entity uses `translation_key` via feature registry; strings provide short names (`strings.json:73-128`). |
| runtime-data | done | pass | `models.py:16-28` typed `@dataclass(slots=True) NightscoutData` + `type NightscoutConfigEntry = ConfigEntry[NightscoutData]`. `__init__.py:87-94` assigns `entry.runtime_data = NightscoutData(...)`. Sensor/binary_sensor platforms consume via `entry.runtime_data` (`sensor.py:23`, `binary_sensor.py:20`). No `hass.data[DOMAIN]` usage anywhere (grep: zero hits). |
| test-before-configure | done | pass | `config_flow.py:90-104` calls `mgr.initial_exchange()` and `probe_capabilities(client)` before `async_create_entry`; on `AuthError` sets `errors["base"] = "invalid_auth"`, on `ApiError` `cannot_connect`, and on `Exception` `unknown` with `_LOGGER.exception`. Exercised by `test_config_flow.py:57-73` (parametrized over all three error types) plus recovery via happy-path `test_config_flow.py:27`. |
| test-before-setup | done | pass | `__init__.py:44-55` raises `ConfigEntryAuthFailed` on `AuthError` and `ConfigEntryNotReady` on `ApiError` during both JWT exchange and capability probe. `coordinator.py:133-138` re-raises `AuthError→ConfigEntryAuthFailed`, `ApiError→UpdateFailed`, network errors→`UpdateFailed`. Covered by `test_init.py:69-126` (four parametrized SETUP_RETRY / SETUP_ERROR variants) and `test_coordinator.py:84-101`. |
| unique-config-entry | done | pass | `config_flow.py:86-89` normalises URL (`_normalize`) → deterministic 16-char sha256 (`_unique_id`) → `async_set_unique_id` + `_abort_if_unique_id_configured`. Verified by `test_config_flow.py:76-94` (ABORT `already_configured`). Minor: set before probing rather than after — acceptable because the id is a deterministic hash of user input and does not depend on server state, so "know the id is real" has no meaning here. |
| **Silver** | | | |
| action-exceptions | exempt | pass | No service handlers; exemption comment present (`quality_scale.yaml:38-40`). |
| config-entry-unloading | done | pass | `__init__.py:101-109` defines `async_unload_entry`, awaits `async_unload_platforms(entry, _PLATFORMS)`, and on success calls `data.jwt_refresh_unsub()`, `await data.coordinator.async_shutdown()`, `await data.store.close()`. Covered by `test_init.py:31-56` (LOADED → NOT_LOADED round-trip). |
| docs-configuration-parameters | done | pass | Taken at face value (Phase 6). |
| docs-installation-parameters | done | pass | Taken at face value (Phase 6). |
| entity-unavailable | done | pass | `entity.py:54-58` overrides `available` to return `super().available and self._extract() is not None` — stricter than the inherited default. Covered by `test_entity.py:88-119`. `native_value` in `sensor.py:53-58` guards against dict/list shapes by returning `None`. |
| integration-owner | done | pass | `manifest.json:4` `"codeowners": ["@savek-cc"]`. `iot_class: cloud_polling` is correct (`:9`). |
| log-when-unavailable | done | pass | `coordinator.py:135-138` raises `UpdateFailed` on `ApiError`/timeout/OSError; `:133-134` raises `ConfigEntryAuthFailed` on `AuthError`. `DataUpdateCoordinator` in HA core handles once-on-down / once-on-recovery throttling itself. JWT-refresh timer in `__init__.py:76-81` logs at WARNING once per auth failure (no retry spam) and DEBUG for transient — correct levels. |
| parallel-updates | done | pass | `sensor.py:17` `PARALLEL_UPDATES = 0` (module-level). `binary_sensor.py:14` `PARALLEL_UPDATES = 0`. Verified by `test_sensor.py:59-63` assertion. |
| reauthentication-flow | done | mostly pass | `config_flow.py:111-144` implements `async_step_reauth` and `async_step_reauth_confirm`; uses `self._get_reauth_entry()` and `async_update_reload_and_abort` (`:134-138`). Happy path `test_config_flow.py:165-188` asserts ABORT `reauth_successful` and `entry.data["access_token"]` update. Errors covered by parametrized `test_reauth_errors` at `:269-292`. **Minor gap:** no `async_set_unique_id(reauth_entry.unique_id)` + `_abort_if_unique_id_mismatch()` before the update — see Findings. |
| test-coverage | done | pass | `pyproject.toml:20` `--cov-fail-under=95`. Latest run: `TOTAL 95.25%` (168 passed). Note this is the *aggregate* rule; `config_flow.py` has its own 100 % rule that is **not** met (see above). |

## Findings

### Critical (must fix before Silver)

**C-1. `config_flow.py` coverage is 98 %, not 100 %.**
- **File:** `custom_components/nightscout_v3/config_flow.py:200-204`
- **Missed lines:** 201-202, the body of `if user_input is not None:` inside `async_step_features` — where the selected feature toggles are applied and the options entry is written.
- **Why it matters:** Bronze rule `config-flow-test-coverage` explicitly requires 100 %. The options-flow features submit path is the central user-facing interaction for enabling/disabling feature entities. Leaving it untested means regressions will slip through silently.
- **Recommendation:** extend `test_options_features_sub_step` in `tests/test_config_flow.py` (currently stops at the FORM step at `:109-116`) to actually submit the features form and assert CREATE_ENTRY + the resulting `enabled_features` dict. Mirror the pattern already used in `test_options_stats_windows` and `test_options_thresholds_happy_path`.

**C-2. `quality_scale.yaml` and `manifest.json` disagree on `brands`.**
- **Files:** `custom_components/nightscout_v3/quality_scale.yaml:7-9` (`status: todo`), `custom_components/nightscout_v3/manifest.json:11` (`"quality_scale": "silver"`).
- **Why it matters:** Per the reference (`docs/references/ha-silver-quality-scale.md:126`), the manifest's `quality_scale: silver` declaration is only valid once every Bronze rule is `done` or `exempt`. `todo` does not qualify.
- **Recommendation:** either
  - (a) submit the `home-assistant/brands` PR (the canonical fix), then flip `brands: done`; or
  - (b) mark the rule `exempt` in `quality_scale.yaml` with a comment citing HACS-only distribution (e.g. `comment: Custom component distributed exclusively via HACS; brands repo is core-only.`) — this matches the soft-enforcement note in the reference doc at line 880.

Until one of those lands, either roll `manifest.json` back to `"quality_scale": "bronze"` or keep both files in sync.

### Important

None.

### Minor / nice-to-have

**M-1. Reauth flow does not pin the unique_id.**
- **File:** `custom_components/nightscout_v3/config_flow.py:115-144`
- **Observation:** After successful token validation the handler calls `async_update_reload_and_abort` without first calling `await self.async_set_unique_id(reauth_entry.unique_id)` + `self._abort_if_unique_id_mismatch()`.
- **Risk today:** very low — the reauth form only asks for a new token; `self._url` is pulled verbatim from the existing entry at `:112`, so the user cannot accidentally re-auth against a different site.
- **Why still worth fixing:** the reference (`docs/references/ha-silver-quality-scale.md:702-706`) explicitly prescribes the pattern, and hassfest / reviewers may flag it. It is a one-line addition and future-proofs the flow if reauth is ever widened to re-enter the URL.
- **Recommendation:** before the `async_update_reload_and_abort` call at `:135`, add:
  ```python
  await self.async_set_unique_id(reauth_entry.unique_id)
  self._abort_if_unique_id_mismatch()
  ```

**M-2. `diagnostics.py` uses untyped `ConfigEntry` in the signature.**
- **File:** `custom_components/nightscout_v3/diagnostics.py:15`
- **Observation:** `async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry)` — the other entry points use `NightscoutConfigEntry` from `models.py`. Consistency nit; does not affect runtime correctness.
- **Recommendation:** swap to `NightscoutConfigEntry` so `entry.runtime_data` is typed. Non-blocking.

**M-3. `unique-config-entry` timing (observation, not a bug).**
- **File:** `custom_components/nightscout_v3/config_flow.py:86-89`
- **Observation:** `async_set_unique_id` is called before the server probe rather than after. The reference prefers after-probe so you "know the id is real". Here the id is a deterministic sha256 of the URL, so the early call is harmless — but if the implementation ever switches to pulling a server-assigned id (e.g. site UUID from `/api/v3/status`), the order will need to flip.
- **Recommendation:** leave as-is; note for future work.

### Notes on items taken at face value

Per scope, `docs-high-level-description`, `docs-installation-instructions`, `docs-removal-instructions`, `docs-configuration-parameters`, `docs-installation-parameters` are accepted as `done` on the strength of Phase 6 (`docs/reviews/2026-04-22-phase-6-docs.md`). This auditor did not re-read README content.

## Verdict

**Silver: blocked.**

Must-fix before flipping `manifest.json` to silver (if not already) and tagging v0.1.0:

1. Cover lines 201-202 of `config_flow.py` (features options-flow submit) — needed for `config-flow-test-coverage` (100 % rule).
2. Resolve the `brands` inconsistency in `quality_scale.yaml` versus `manifest.json`.

Once those two are closed, the integration is clean for Silver. The minor findings (M-1, M-2, M-3) are recommended but not blocking.
