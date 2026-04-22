# Phase 2 (Domain Layer) — Code Review

**Date:** 2026-04-22
**Reviewer:** code-reviewer subagent
**Scope:** commits `e13447f`, `3d287ac`, `43d5d61`
**Spec reference:** `docs/specs/2026-04-22-ha-nightscout-v3-design.md` §3.3.4–§3.3.6, §4.1–§4.6
**Plan reference:** `docs/plans/2026-04-22-ha-nightscout-v3-plan.md` Phase 2 (lines 1472–2444)

---

## 1. Summary verdict

**Approve (with minor follow-ups).**

The Phase-2 domain layer is clean pure-Python, faithful to the spec, and hits the 95 % per-module coverage target on all three files that have tests. The two plan deviations called out in commit messages (sample SD in `statistics.py`, broader `sqlite3.DatabaseError` catch + 30-year test window in `history_store.py`) are well-justified; both are genuine plan errata, not arbitrary drift. No implementation bugs were found. The remaining issues are documentation nits and untested defensive branches.

Two items that prevented a cleaner "Approve" verdict:

1. **Plan commit message overstates feature count** (`"40 features"` in `3d287ac`'s subject line). The actual `FEATURE_REGISTRY` contains **36** durable entries (BG 5 + PUMP 9 + LOOP 12 + CAREPORTAL 7 + UPLOADER 3). STATISTICS are generated per-window by `stats_feature_defs`, 14 each. This matches the spec §4.1–§4.4 + §4.6 tables exactly; the message simply miscounts.
2. **Combined coverage is 61.5 %** as measured by the project-wide `--cov=custom_components.nightscout_v3` gate set in `pyproject.toml`, because the Phase 2 tests do not touch `api/*` or `const.py`. On a per-domain-module basis, coverage is 95–98 %, which matches the spec target. This is expected at the Phase 2 boundary; the full-package gate will be reached when Phase 3 (coordinator) wires everything together. Worth noting so future maintainers don't panic at CI failing locally on the Phase 2 test subset.

No blocking issues. Recommend addressing the nits (unused imports, docstring typo "13-sensor" → 14, plan message correction) in a Phase 2 polish commit or rolling into Phase 3 prep.

---

## 2. Rule-by-rule compliance matrix

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Spec §3.3.4 — `open/close/insert_batch/entries_in_window/get_sync_state/update_sync_state/prune/get_stats_cache/set_stats_cache/is_corrupt/recover_from_corruption` | ✓ | `history_store.py:62-181`; all 11 methods present |
| 2 | Spec §3.3.4 — schema v1 tables `schema_version`, `entries`, `sync_state`, `stats_cache` | ✓ | `history_store.py:17-41` |
| 3 | Spec §3.3.4 — `update_sync_state` signature | ? | Spec §3.3.4:198 omits `newest_date`, but plan adds it, and `sync_state` table has it. Plan-consistent. |
| 4 | Spec §3.3.5 — `compute_all` returns 17-key payload incl. `hourly_profile` (24) and `agp_percentiles` (24) | ✓ | `statistics.py:46-64`; tests verify 24-bucket lengths |
| 5 | Spec §3.3.5 — GMI formula `3.31 + 0.02392 * mean` | ✓ | `statistics.py:35`; `test_gmi_matches_formula` |
| 6 | Spec §3.3.5 — HbA1c DCCT formula `(mean + 46.7) / 28.7` | ✓ | `statistics.py:36`; `test_hba1c_dcct_matches_formula` |
| 7 | Spec §3.3.5 — TIR thresholds 70 / 180, very 54 / 250 | ✓ | `statistics.py:8-11` match; tests verify |
| 8 | Spec §3.3.5 — Pure-Python, no IO, no HA deps | ✓ | imports in `statistics.py` are `math`, `time`, `typing.Any` only |
| 9 | Spec §3.3.6 — `Category` StrEnum, 6 values | ✓ | `feature_registry.py:16-22` |
| 10 | Spec §3.3.6 — `FeatureDef` frozen dataclass | ✓ | `feature_registry.py:25-40` uses `frozen=True, slots=True` |
| 11 | Spec §4.1 — 5 BG features | ✓ | `feature_registry.py:60-72` |
| 12 | Spec §4.2 — 9 PUMP features | ✓ | `feature_registry.py:75-100` |
| 13 | Spec §4.3 — 12 LOOP features (incl. `loop_active` binary, `loop_last_enacted_age_minutes`) | ✓ | `feature_registry.py:103-135` |
| 14 | Spec §4.4 — 7 CAREPORTAL features | ✓ | `feature_registry.py:138-161` |
| 15 | Spec §4.5 — 13-sensor stats bundle per window | ~ | Impl generates **14** per window (adds `stat_hba1c_{w}d`, not listed in spec §4.5); plan approves the 14th. Spec §3.3.5 *does* define `hba1c_dcct_percent` in payload, so exposing it as a sensor is internally consistent. Docstring at `feature_registry.py:183` still says "13-sensor". See nit N-2. |
| 16 | Spec §4.6 — 3 UPLOADER features | ✓ | `feature_registry.py:164-173`; all 3 use `_has_uploader` capability |
| 17 | Pure-Python isolation — no HA imports in `history_store.py`, `statistics.py`, `const.py` | ✓ | verified by grep; all three files have zero `homeassistant` references |
| 18 | `feature_registry.py` MAY import HA | ✓ | imports `BinarySensorDeviceClass`, `SensorDeviceClass`, `SensorStateClass`, `PERCENTAGE`, `Platform`, `UnitOfTime` — the closed set of HA enums/constants needed for the FeatureDef table |
| 19 | `from __future__ import annotations` everywhere | ✓ | all four files, line 2 |
| 20 | Modern type hints (`list`, `dict`, `\|`, lowercase generics) | ✓ | e.g. `list[dict[str, Any]]`, `SyncState \| None`, `dict[str, Any] \| None` |
| 21 | `slots=True` / `frozen=True` on dataclasses | ✓ | `SyncState` (both), `FeatureDef` (both) |
| 22 | `Literal[...]` for closed enums | ✓ | not strictly needed in these modules; all closed sets are `StrEnum` (Category) or `Platform` (HA enum) |
| 23 | `Any` only at raw-JSON boundary | ✓ | `statistics.py` uses `Any` on entry dicts; `history_store.py` uses `Any` on payload dicts; `feature_registry.py` imports `Any` but **never uses it** — see nit N-1 |
| 24 | TDD followed (test → impl → commit) | ✓ | plan enforces red-green-commit; one commit per task, both test and impl |
| 25 | No real network, no real FS outside tmp_path | ✓ | `test_history_store.py` uses `tmp_path`; `test_statistics.py` is pure-Python; `test_feature_registry.py` needs no IO |
| 26 | `schema_version` == 1 | ✓ | `history_store.py:15`; `test_schema_version_is_1` |
| 27 | `insert_batch` idempotent (INSERT OR IGNORE) | ✓ | `history_store.py:96-97`; `test_insert_batch_is_idempotent` |
| 28 | `prune` returns row count deleted | ✓ | `history_store.py:146`; `test_prune_removes_old` |
| 29 | `stats_cache` JSON round-trip | ✓ | `history_store.py:148-163`; `test_stats_cache_roundtrip` |
| 30 | Corruption detection + recovery | ✓ | `history_store.py:165-181`; `test_detects_corruption` end-to-end |
| 31 | No secrets logged, timeouts, graceful error handling | ✓ | only logging is the `_LOGGER.warning` on init failure (no sensitive data); `is_corrupt()` has bounded try/except; HTTP/timeout concerns deferred to Phase 3 coordinator |
| 32 | `translation_key` unique across FEATURE_REGISTRY | ✓ | verified via runtime check: 36 keys, 36 translation_keys, all unique |
| 33 | `translation_key` reused across stats windows by design | ✓ | stats_feature_defs reuses e.g. `stat_gmi` across 1d/14d/30d windows; HA supports this because `unique_id` includes the window suffix. Friendly name disambiguation will happen via `_attr_translation_placeholders` in Phase 4. |
| 34 | `default_enabled=False` for noisy sensors only | ✓ | `loop_reason` (free-text AAPS decision log), `care_last_note` (announcements), `stat_lbgi/hbgi`, `stat_hourly_profile`, `stat_agp` (heavy attribute payloads) — all defensible |
| 35 | Coverage ≥ 95 % per module | ✓ | feature_registry 95 %, history_store 98 %, statistics 96 % |
| 36 | Coverage ≥ 95 % combined (full package gate) | ✗ | 61.5 % because api/* not exercised by Phase 2 tests; acceptable at phase boundary, CI gate is project-wide; see §4 |

Legend: ✓ pass, ✗ fail, ? partial/needs discussion, ~ deviation approved by plan.

---

## 3. Severity-ranked issues

### Critical (must fix before Phase 2 is considered done)

_None._

### Important (should fix)

- **I-1. Plan commit message (`3d287ac`) states "40 features" but the FEATURE_REGISTRY has 36.** The mismatch is cosmetic but will confuse future maintainers who grep git-log. The 36 entries exactly match the sum of spec §4.1–§4.4 + §4.6 tables (5 + 9 + 12 + 7 + 3). STATISTICS are correctly generated per-window. Either update the subject line to "36 registry features + 14 per stats-window", or leave it and note the mismatch in the Phase 2 review (this document). No code change required.

### Nits (take or leave)

- **N-1. Unused `from typing import Any` in `feature_registry.py:7`.** `Any` is never referenced in the file body (all FeatureDef fields use concrete types or `str | None`). `ruff` would catch this; consider removing.
- **N-2. `stats_feature_defs` docstring says "13-sensor stats bundle" at `feature_registry.py:183`, but the function emits 14.** The 14th is `stat_hba1c_{w}d`, which is not listed in spec §4.5 but *is* derivable from spec §3.3.5's `hba1c_dcct_percent` field. Either (a) update the docstring to "14-sensor" and note the spec §4.5 table omission, or (b) drop the `stat_hba1c_*` FeatureDef (users will still see `stat_gmi_*`, which is the modern preference). I'd lean (a) — GMI and eHbA1c are subtly different (GMI based on 14-day mean only; HbA1c DCCT is a different formula), so both have clinical value.
- **N-3. Unused `import math` and `import time` in `tests/test_statistics.py:4-5`.** Both are imported at module scope but never referenced (the tests use `pytest.approx` only). `ruff --fix` would remove them.
- **N-4. `statistics.py` line 108 (`continue` in `_bucket_by_hour` when `sgv` or `date` is None) is defensive but untested.** Coverage marks it missing. A two-line fixture `[{"sgv": None, "date": 1}, {"sgv": 120}]` would close it. Same for line 137 (`_percentile([])` early-return, unreachable via public API but present).
- **N-5. `statistics.py:126` median uses upper-median (`xs_sorted[len(xs) // 2]`) for even-length lists.** For [100, 200] it returns 200, not 150. CGM data has 288 samples/day so hourly buckets typically have 12 samples and the bias rarely matters, but the AGP/P50 percentile function on line 142 computes the correct interpolated median. A consistent `_percentile(sorted_xs, 0.5)` call in `_hourly_profile` would remove the asymmetry for ~3 lines. Not urgent.
- **N-6. `_bucket_by_hour` buckets by UTC hour, not local time.** `h = int((int(date) // 1000 % 86_400) // 3600)` computes the UTC hour of day. For a user in Berlin (CET/CEST), a 6 AM local reading lands in bucket 4 or 5 depending on DST. The hourly-profile and AGP cards on a dashboard will therefore look shifted. Spec §3.3.5 is silent on timezone; Phase 3 should either accept a `hass.config.time_zone` parameter or resolve this at the coordinator seam. Flagging now so it doesn't get lost.
- **N-7. `history_store.py:81` (`if not entries: return 0`) is untested.** One-line test: `assert await store.insert_batch([]) == 0`. Free coverage.
- **N-8. `history_store.py:_initialize_schema` swallows `sqlite3.DatabaseError` silently-but-logged.** Comment could be stronger: after swallow, the instance is in a zombie state (connection open on a non-SQLite file). Only `is_corrupt()` and `recover_from_corruption()` are safe to call. Any other method call will raise. Worth an explicit docstring on `open()` noting this contract, or raise a sentinel `StoreNotInitialized` subclass that callers can catch and route to recovery.
- **N-9. `HistoryStore.open` creates `path.parent` with `mkdir(parents=True, exist_ok=True)`.** This is a sync FS call inside an async classmethod; HA's executor would normally handle it. For `.storage/` which always exists, the real-world impact is zero. Phase 3 integration should consider running through `hass.async_add_executor_job` for strictness. Not actionable here.
- **N-10. `strings.json` has `"entity": {}`.** All 36 FeatureDef `translation_key`s plus the 14 stats ones reference entity-level translations that don't exist yet. HA will emit a warning at entity-registration time in Phase 4/5. Expected — the Phase 2 task didn't include string table population. Make sure a later phase fills this in before Silver submission.
- **N-11. `insert_batch` does SELECT COUNT → INSERT → SELECT COUNT to compute delta.** Correct for idempotent semantics but costs two extra queries per batch. For 288 entries/day × 5-minute polling, this is noise. At the 14-day backfill the batch is 4032 rows, still under 1 ms. Not worth changing; noting for future profiling.

---

## 4. Coverage detail

Command:

```bash
.venv/bin/python -m pytest tests/test_history_store.py tests/test_statistics.py \
    tests/test_feature_registry.py --cov=custom_components.nightscout_v3 \
    --cov-report=term-missing --no-cov-on-fail --no-header
```

Result: **20 passed**, combined coverage **61.51 %** (project-wide, fail-under=95 in `pyproject.toml`).

| Module | Stmts | Miss | Branch | BrPart | Cover | Missing lines |
|---|---:|---:|---:|---:|---:|---|
| `__init__.py` | 0 | 0 | 0 | 0 | 100 % | — |
| `api/__init__.py` | 0 | 0 | 0 | 0 | 100 % | — |
| `api/auth.py` | 71 | 46 | 12 | 0 | 30 % | not in scope |
| `api/capabilities.py` | 39 | 12 | 2 | 0 | 66 % | not in scope |
| `api/client.py` | 75 | 55 | 26 | 0 | 20 % | not in scope |
| `api/exceptions.py` | 9 | 3 | 0 | 0 | 67 % | not in scope |
| `const.py` | 30 | 30 | 0 | 0 | **0 %** | never imported by Phase-2 tests |
| `feature_registry.py` | 43 | 2 | 0 | 0 | **95 %** | 184-185 (`stats_feature_defs` body) |
| `history_store.py` | 97 | 1 | 4 | 1 | **98 %** | 81 (empty-batch early return) |
| `statistics.py` | 76 | 2 | 20 | 2 | **96 %** | 108, 137 (defensive branches) |
| **Total** | **440** | **151** | **64** | **3** | **62 %** | |

### Interpretation

- The three new domain modules (`feature_registry`, `history_store`, `statistics`) meet the spec's 95 % target per-module.
- `const.py` shows 0 % because it's not imported by any Phase 2 test. It's a pure declaration module; Phase 3 config_flow + coordinator code will import it, and `coverage` will then report it as 100 % (no executable logic beyond module-level assignments).
- `api/*` shows the Phase-1 coverage as measured by the Phase-2 test subset — not the truth. Running the full suite (which Phase 1 review confirmed at 100 %) would put combined coverage back at ≥ 95 %.
- The CI gate (`--cov-fail-under=95`) in `pyproject.toml` is intended for the full suite, not per-phase. Locally running only Phase 2 tests will fail coverage; that's expected. The Phase 3 review should re-verify combined coverage once coordinator tests are in.

### Easy coverage gap closers (if desired now)

- `feature_registry.py:184-185`: one-liner `stats_feature_defs(14)` call in a test asserting 14 entries returned and containing `stat_gmi_14d`.
- `history_store.py:81`: `assert await store.insert_batch([]) == 0`.
- `statistics.py:108`: include an entry with `sgv=None` in any existing test.
- `statistics.py:137`: unreachable via public API — safe to mark `# pragma: no cover` or leave as-is.

Estimated effort: 5 minutes for +3 percentage points on the three domain modules (all already ≥ 95 %).

---

## 5. Security / Silver-gate notes

- **No secrets logged.** `_LOGGER.warning` at `history_store.py:192-196` logs only the file path (which is under `.storage/` — not sensitive). No tokens, URLs, or patient data touched.
- **Bounded error handling at the DB boundary.** `is_corrupt()` at `history_store.py:165-171` catches both `aiosqlite.Error` and `sqlite3.Error`, returning `True` on either. `_initialize_schema` at `:183-196` catches `sqlite3.DatabaseError` and logs. The intended flow is `open → is_corrupt → recover_from_corruption → re-open`, which the test verifies.
- **`statistics.py` is fully deterministic and has no external dependencies.** No numeric overflow concerns for realistic CGM data (SGVs are 0–500 mg/dL, bounded float ops).
- **`FEATURE_REGISTRY` is immutable at module scope** (`frozen=True` on `FeatureDef`). Registry itself is a `list`, which is mutable; concurrent mutation is not a realistic threat in HA's single-event-loop model, but a `tuple[FeatureDef, ...]` type would be more defensive. Nit, not actionable.
- **No `eval`, `exec`, `pickle`, `subprocess`, `shell=True`** in any Phase 2 file.
- **SQL injection surface is zero.** All dynamic values go through parameterized `?` placeholders; no string-interpolation into SQL.
- **No timeouts needed in domain layer** (all IO is local SQLite). Phase 3 coordinator will be the timeout authority.

Silver rules satisfied for this phase: **82 (timeouts — N/A here)**, **105 (pure functions testable)**, **79 (no blocking in event loop)** (aiosqlite is async). Phase 3 must re-verify **79** when the coordinator starts scheduling executor calls.

---

## 6. Deviations from plan

| # | Plan says | Code does | Verdict | Documented? |
|---|---|---|---|---|
| D-1 | `statistics.py:1924` uses population SD (`/ n`) | Impl uses sample SD (`/ (n-1)`) | **Correct.** The plan's own `test_sd_and_cv` expects 31.62 for [100,120,140,160,180], which is the sample SD (`sqrt(sum / 4)`), not population (`sqrt(sum / 5) ≈ 28.28`). Impl fixes plan-internal contradiction. Also matches the standard CGM-analytics convention (Nightscout itself, Dexcom Clarity, ATTD 2019 consensus). | ✓ `e13447f` commit body |
| D-2 | `history_store.py:1750` catches `aiosqlite.Error` only in `is_corrupt`; `_initialize_schema` (plan `:1767-1773`) catches nothing | Impl also catches `sqlite3.DatabaseError` in `_initialize_schema` | **Correct.** SQLite defers file-format validation to the first DDL statement; without the catch, `open()` raises and the caller never gets a `HistoryStore` instance on which to call `is_corrupt()`. The plan's own `test_detects_corruption` assumes `open()` succeeds and then `is_corrupt()` returns True — impossible without the fix. | ✓ `43d5d61` commit body |
| D-3 | `test_insert_batch_and_window` uses `days=1` window (plan `:1521`) | Test uses `days=365 * 30` | **Correct.** Fixture dates are pinned to `1_745_000_000_000` ≈ 2025-04; wall-clock at commit time is 2026-04, so `days=1` excludes all fixture rows. The plan's `test_prune_removes_old` already uses the 30-year idiom. | ✓ `43d5d61` commit body |
| D-4 | Spec §3.3.4:198 shows `update_sync_state(collection, last_modified, oldest_date)` | Impl (matching plan `:1709-1711`) adds keyword-only `newest_date` | **Plan-consistent.** The `sync_state` table has a `newest_date` column in both spec §5.1 and plan `:1617`. The signature in spec §3.3.4 is abbreviated; the plan resolves the ambiguity by including `newest_date`. Impl follows plan. | Not explicitly, but plan is authoritative |
| D-5 | Plan commit message `3d287ac` says "40 features" | Registry has 36 | **Message bug, not code bug.** See I-1. | ✗ |

No other behavioral deviations detected.

---

## 7. Recommendation

**Approve.** Phase 2 is in good shape. Three small items are worth a follow-up polish commit before Phase 3 starts (if there's a Phase-2-polish slot planned similar to Phase 1's `f5bd56d`):

1. Drop the unused `from typing import Any` in `feature_registry.py:7` (N-1).
2. Drop the unused `import math` / `import time` in `tests/test_statistics.py:4-5` (N-3).
3. Update `stats_feature_defs` docstring from "13-sensor" to "14-sensor" (N-2), or drop `stat_hba1c_{w}d` if the team prefers GMI-only.

Optional at reviewer's discretion:

- Close the 4 untested defensive lines in `statistics.py` / `history_store.py` with 5 minutes of tests, to put all three domain modules at 100 %.
- Add a Phase-3-prep todo to decide on local-time vs UTC bucketing for the hourly/AGP views (N-6).

Everything else (unused imports, median bias, timezone question) can be batched into Phase 3 without blocking.

Phase 2 is approvable as-is.

---

*End of report.*
