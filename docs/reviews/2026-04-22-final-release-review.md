# Final Release Review — ha-nightscout-v3 v0.1.0 (Silver)

**Date**: 2026-04-22
**Reviewer**: Final Release Reviewer
**Scope**: whole repo (integration + scripts + tests + dashboards + docs + fixtures)
**Prior gates (trusted)**: phase-5 dashboard, phase-6 docs, silver-audit + silver-audit-pass2

## Summary

Repository is in strong shape. All 168 tests pass at **95.51 %** coverage, prior Silver audit is green, no `print()` / bare `except` / `# type: ignore` markers exist anywhere, and the forbidden-host guard against ProdInstance is in place in both publisher scripts.

Two findings, however, **block the tag**:

1. `api/auth.py:95` can raise an `ApiError` whose message embeds the full JWT-exchange response body, which includes the JWT token. That `ApiError` bubbles to `__init__.py:81` which emits it at `_LOGGER.debug`. The audit checklist calls any log path that can emit a token a blocker.
2. `README.md:123-124` and `docs/architecture.md:21` both promise that diagnostics redact `reason` and `notes`. The actual redaction set at `diagnostics.py:12` is `{"url", "access_token", "api_secret", "identifier", "sub", "token"}` — neither `reason` nor `notes` is in it. The `snapshot` block in the diagnostics payload includes `care.last_note` (free-form announcement text) and `loop.reason` (free-form AAPS decision log), so those leak into diagnostics output verbatim. This is simultaneously a privacy regression and a false documented claim.

In addition, ruff flags 115 findings on production code (mostly D-rule docstring misses on public methods, a handful of unused imports, two unused `# noqa: BLE001` directives, and two long-line violations) that the Silver audit did not catch. Individually minor; collectively they suggest `ruff check` was not run as part of the pre-release verification.

Both blockers are a 3-line fix each. Close them, re-run tests, and the tag is good to go.

**Verdict**: Release **blocked** on two items (log leak + docs-vs-code mismatch).

## Checklist results

| # | Item | Status | Count | Pointer |
|---|---|---|---|---|
| 1 | Placeholder / TODO / FIXME / XXX markers | pass | 0 | Only legitimate `RuleStatus.TODO` enum in `scripts/verify_silver.py` |
| 2 | Unused imports / dead variables (ruff) | findings | 9 F401 / 1 F841 (prod) + 6 F-rule (tests) + 1 ASYNC240 | See Important I-2 |
| 3 | Unused feature-registry keys | pass | 0 | `sensor.py:27-39`, `binary_sensor.py:22-28` iterate the full registry; every stats key also consumed |
| 4 | Typing gaps on public API | pass | 0 | All signatures in `__init__.py`, `coordinator.py`, `api/*.py`, `entity.py`, `config_flow.py`, `diagnostics.py` have full annotations |
| 5 | Log leaks (URL / token / JWT / patient note / treatment string) | **findings** | 1 critical + 1 critical docs-mismatch | See Critical C-1 and C-2 |
| 6 | Docstrings on public API | findings | 37 D102 + 3 D103 + 1 D101 + 0 D100 (prod) | See Important I-1 |
| 7 | `__all__` exports | findings | 0 modules declare it | See Minor M-1 |
| 8 | `print()` calls | pass | 0 | Scripts use `sys.stdout.write` / `sys.stderr.write` consistently |
| 9 | Bare `except:` | pass | 0 | |
| 10 | `# type: ignore` without reason | pass | 0 | No `# type: ignore` anywhere |
| 11 | `# noqa` without reason | findings | 1 missing reason + 2 now unused | See Important I-3 |

Infrastructure sanity (supplementary):
- `scripts/smoke_test.py:18` and `scripts/capture_fixtures.py:26` both carry `FORBIDDEN_HOSTS = {"prod-nightscout.example.invalid"}` and the guard is exercised by `tests/scripts/test_capture_fixtures.py:31-37` and `tests/scripts/test_smoke_test.py:22-24`.
- `dev-nightscout.example.invalid` only appears as test *input* to the anonymizer, and the same test asserts it is scrubbed (`tests/scripts/test_anonymize_fixtures.py:30`). ProdInstance (`prod-nightscout.example.invalid`) is referenced in tests only as the guard-rail positive case.
- Test suite: 168 passed / 0 failed / 95.51 % coverage / ran in 2.00 s on Python 3.14.3.

## Findings

### Critical (must fix before tag)

#### C-1. JWT token can be logged at DEBUG via malformed-response path

**Files**: `custom_components/nightscout_v3/api/auth.py:95` → propagates through `custom_components/nightscout_v3/__init__.py:81`.

At `auth.py:95`:

```python
if token is None or exp is None or iat is None:
    raise ApiError(f"Malformed JWT response: {body}")
```

If the server returns a JSON envelope where `token` is present but one of `exp` / `iat` is missing or non-numeric, the entire `body` — which includes the raw JWT — is embedded in the exception message. `_exchange_with_retry` at line 73 then re-raises a wrapping `ApiError(f"... {last_exc}")` after exhausting retries. That wrapping error flows to `__init__.py:75-81`:

```python
async def _refresh_jwt(_now) -> None:
    try:
        await jwt_manager.refresh()
    except AuthError:
        _LOGGER.warning("JWT refresh rejected; awaiting reauth")
    except ApiError as exc:
        _LOGGER.debug("JWT refresh failed transiently: %s", exc)
```

Result: in the background-refresh code path (runs every 7 h per `JWT_BACKGROUND_REFRESH_HOURS`), a malformed response dumps the JWT at DEBUG level. Home Assistant logs at DEBUG are routinely shared in bug reports. The audit checklist explicitly classifies *any* leak as a blocker.

`README.md:122` advertises "No URLs, tokens, patient notes, or free-text pump strings are logged" — this path violates that promise.

**Fix**: drop the `{body}` interpolation. Either log the shape (`list(body.keys())`) or a fixed string. Something like:

```python
raise ApiError(
    f"Malformed JWT response: missing fields "
    f"{[k for k in ('token','exp','iat') if locals().get(k) is None]}"
)
```

Add a test that feeds `{"result": {"token": "LEAK.ME", "iat": 0}}` (no `exp`), asserts `ApiError` is raised, and asserts `"LEAK.ME" not in str(exc)`.

#### C-2. Diagnostics do not redact `reason` / `notes`, contradicting README and architecture doc

**Files**: `custom_components/nightscout_v3/diagnostics.py:12`, `README.md:123-124`, `docs/architecture.md:21`.

- `diagnostics.py:12`:
  ```python
  _TO_REDACT = {"url", "access_token", "api_secret", "identifier", "sub", "token"}
  ```
- `README.md:123-124`:
  > Diagnostics exports are redacted (`async_redact_data` over URL, token,
  > `reason`, `notes`).
- `docs/architecture.md:21`:
  > `diagnostics.py` | `async_get_config_entry_diagnostics` with `async_redact_data` over `url`, `access_token`, `reason`, `notes`.

The `runtime.snapshot` field in the diagnostics payload is `coordinator.data` (`diagnostics.py:50`), and `coordinator._build_payload` at `coordinator.py:243-250` puts `loop.reason` (AAPS free-text decision log) and `care.last_note` (Nightscout announcement or Note treatment body, copied verbatim at `coordinator.py:198`) into that snapshot. Both fall out of diagnostics uncensored. `loop.reason` also leaks ISF/ratio coefficients that reveal basal/ISF tuning; `care.last_note` is free-form user text.

This was previously flagged as `N-11` in `docs/reviews/2026-04-22-phase-3-ha-integration.md` and never resolved; the silver-audit did not re-check it.

The fix is either (a) wire `reason` and `notes` into `_TO_REDACT` and verify `async_redact_data` actually recurses into `snapshot` with those dict keys (it does — the helper walks nested dicts), or (b) update README + architecture.md to tell the truth about what is redacted. Option (a) is the right one since the promised behaviour is the right behaviour; leaking free-form patient-entered text into a shareable diagnostics blob is the worst-case for an integration that a Type 1 diabetic pastes into a GitHub issue.

Recommended redaction set:

```python
_TO_REDACT = {
    "url", "access_token", "api_secret", "identifier", "sub", "token",
    "reason", "notes", "last_note", "enteredBy",
}
```

Then amend `tests/test_diagnostics.py:58-80` to assert that a snapshot containing `"loop": {"reason": "DETECTED A LEAK"}` and `"care": {"last_note": "private note"}` produces output where neither literal appears.

### Important (should fix before tag; defer only with explicit justification)

#### I-1. Missing docstrings on 41 public surfaces

`.venv/bin/ruff check custom_components/` reports 37× D102 (public method missing docstring), 3× D103 (public function missing docstring), 1× D101 (public class missing docstring). Concentrations:

- `api/client.py` — every public method on `NightscoutV3Client` (`get_status`, `get_last_modified`, `get_devicestatus`, `get_entries`, `get_treatments`, `get_profile`) lacks a docstring. Given the client is the integration's external contract, this is a poor Silver posture.
- `config_flow.py` — `async_step_user`, `async_step_reauth`, `async_step_reauth_confirm`, `async_step_init`, `async_step_features`, `async_step_stats`, `async_step_thresholds`, `async_step_polling`, `async_step_rediscover`, `async_get_options_flow` are all undocumented. HA expects a short sentence on each `async_step_*`.
- `history_store.py` — 8 public methods (`open`, `close`, `schema_version`, `insert_batch`, `entries_in_window`, `get_sync_state`, `update_sync_state`, `prune`, `get_stats_cache`, `set_stats_cache`, `is_corrupt`) — all undocumented. Class docstring exists.
- `coordinator.py` — the four `@property` accessors (`capabilities`, `client`, `store`, `last_tick_summary`) and `_async_update_data` are undocumented. `NightscoutCoordinator` class docstring exists.
- `feature_registry.py:16` — `Category(StrEnum)` has no docstring (`D101`).
- `binary_sensor.py:17` + `diagnostics.py:15` + `sensor.py:20` — the three `async_setup_entry` entry points are undocumented (`D103`).
- `api/capabilities.py:28,32` — `to_dict` / `from_dict` on the dataclass.
- `api/auth.py:40` — the `state` property.

The audit checklist calls this out as "every public method of the integration" requiring a docstring; the Silver scale is more forgiving, but Silver does not retroactively excuse findings surfaced here. These should be closed in a single mechanical sweep; they are essentially zero-risk churn.

#### I-2. Unused imports (production) and one dead variable

Ruff flags 9 `F401` + 1 `F841` + 1 `ASYNC240` in non-test code:

- `__init__.py:15` — `ServerCapabilities` imported but unused.
- `__init__.py:23` — `DOMAIN` imported but unused.
- `coordinator.py:5` — `math` imported but unused.
- `coordinator.py:12` — `ConfigEntryNotReady` imported but unused (previously raised as `N-4` in `docs/reviews/2026-04-22-phase-3-ha-integration.md:211`, deferred).
- `entity.py:6` — `callback` imported but unused.
- `feature_registry.py:7` — `typing.Any` imported but unused.
- `sensor.py:7` — `ConfigEntry` imported but unused.
- `sensor.py:14` — `Category`, `FEATURE_REGISTRY` imported but unused.
- `tests/conftest.py:30` — `fixture = None` dead assignment (F841).
- `scripts/capture_fixtures.py:54` — `dst.mkdir(...)` is a sync call inside an `async def`. Low-risk in a one-shot CLI, but worth migrating to `asyncio.to_thread` or pre-creating the dir in `main()`.

Fixes are mechanical (`ruff check --fix`).

#### I-3. `# noqa: BLE001` directives are unused AND one lacks a reason

`custom_components/nightscout_v3/config_flow.py:102` and `:129` both carry `# noqa: BLE001`. Two issues:

1. BLE001 is not in the project's ruff selection (see `ruff.toml` — only `E, F, W, I, N, UP, B, ASYNC, S, SIM, RUF, D`). Ruff reports both as `RUF100` *unused noqa*. They should be removed.
2. Even if they *were* active, `:129` has no trailing explanation ("`# noqa: BLE001`" full stop), which violates checklist item #11. `:102` has the reason `— catch-all for unknown flow paths`.

#### I-4. `NotReady` exception is dead code

`custom_components/nightscout_v3/api/exceptions.py:20` defines `class NotReady(ApiError)`. Grep confirms it is never raised, caught, or referenced outside its own existence-test (`tests/test_exceptions.py:12`). Phase-1 review noted "usage deferred to Phase 3" and Phase 3 never adopted it — the coordinator uses `UpdateFailed`, and `__init__.py` uses `ConfigEntryNotReady` from HA core. Additionally, `NotReady` triggers `N818` (exception name without `Error` suffix).

Either wire it into the retry path (e.g., raise it from `api/client.py` for 5xx / timeout / DNS, and have the coordinator / `__init__.py` pattern-match on it instead of generic `ApiError`) or delete it with its test. Leaving both in place costs nothing today but confuses future contributors.

#### I-5. Two E501 long-line violations in `config_flow.py`

- `config_flow.py:220` (114 chars): the `chosen = sorted(...)` expression.
- `config_flow.py:242-245` (135-158 chars each): the TIR threshold voluptuous schema.

Split across lines or hoist the expressions. Not a blocker but worth closing so `ruff check .` runs clean.

### Minor (post-release roadmap)

#### M-1. No module declares `__all__`

Per audit item #7, modules that expose public surface should declare `__all__`. None do. The effect is that `from custom_components.nightscout_v3 import *` exposes everything the module imports, which is imperfect hygiene but low-risk because nothing does star-imports from this codebase. Close post-release.

#### M-2. Ruff not wired into CI or a developer Makefile target

`.pre-commit-config.yaml` declares ruff hooks but the current finding surface (134 total) indicates contributors are not running them locally. Consider a `make check` target that runs `.venv/bin/ruff check .` and `.venv/bin/python -m pytest`, and optionally add `ruff` to `requirements-test.txt` so `.venv/bin/ruff` exists by default. Purely process hygiene.

#### M-3. Test-file hygiene (6 F-rule findings)

- `tests/test_config_flow.py:13` — `load_fixture` imported unused.
- `tests/test_coordinator.py:4` — `timedelta` imported unused.
- `tests/test_init.py:7` — `ConfigEntry` imported unused.
- `tests/test_statistics.py:4,5` — `math`, `time` imported unused.
- `tests/conftest.py:30` — dead assignment (also I-2).
- Import sorting (`I001`) in `tests/test_sensor.py:60,67,114` — lazy imports inside tests; either hoist to module level or annotate as intentional.

Tests are covered by the ruff `per-file-ignores = ["D","S","E501"]` block but F-rules still apply.

## Verdict

**Release blocked.** Blockers:

1. **C-1** — JWT token leakage into DEBUG log via `auth.py:95` → `__init__.py:81`.
2. **C-2** — `reason` / `notes` redaction mismatch between diagnostics.py and README/architecture.md; free-form patient text leaks into shareable diagnostics output.

Both are ~3-line fixes each. After they land, re-verify:
- `grep -r "LEAK" .venv/src || echo clean` — add and verify the JWT-body leak test from C-1.
- `pytest tests/test_diagnostics.py -v` with new reason/notes assertions from C-2.
- `.venv/bin/ruff check custom_components/ scripts/` — should continue to show only D-rule findings (I-1 is important but not blocking).
- `.venv/bin/python -m pytest` — expect 170 passed (168 + 2 new) and coverage ≥ 95 %.

Then the tag is good. Importants I-1 through I-5 and all Minor items can go on the roadmap; a short post-release cleanup PR covers them all.
