# Phase 4 Review — Scripts & Dev/Ops Tooling

**Reviewer:** code-reviewer subagent
**Date:** 2026-04-22
**Scope:** commit `2634b47` "feat(scripts): phase 4 dev/ops tooling + full de.json entity translations"
**Plan reference:** `docs/plans/2026-04-22-ha-nightscout-v3-plan.md` Phase 4 (lines 4273–4950)
**Silver reference:** `docs/references/ha-silver-quality-scale.md`

---

## Verdict

**Request changes (minor) — merge after addressing the two Important findings.**

Phase 4 delivers exactly what the plan scopes: four dev/ops scripts
(`anonymize_fixtures`, `capture_fixtures`, `smoke_test`, `verify_silver`),
25 new unit tests, `.gitignore` hygiene for `captures/`, and full German
entity translations for every sensor / binary_sensor key in `strings.json`.
All 125 tests pass, `verify_silver` runs green on the current integration
except for the four `docs-*` rules that the plan explicitly defers to
Phase 6. The deliberate deviations from the plan's code samples
(`api.auth.JwtManager`, `client.get_status()`, `probe_capabilities(client)`,
`caps.to_dict()`) are correct — they match the real Phase 1 API surface,
which is what a published plan-sample refresh should look like. The extra
fixes against the plan (dict-dispatch in `capture_fixtures`, exempt-without-
comment failure-mode in `verify_silver`, enum-coercion helper, `check_translations`
short-circuit when `strings.json`/`translations/` absent) are all net
improvements and I'd keep every one.

Two items keep this from being a clean Approve:

1. **I-1 (important) — Anonymizer does not scrub device / pump / identifier
   strings that appear in real v3 captures.** The docstring promises to strip
   anything identifying the "person, server, or medical event", but
   `SENSITIVE_STRING_KEYS` omits `device`, `pumpSerial`, `pumpType`, `pumpId`,
   `identifier`, `reason`, `consoleLog`, `consoleError`, `ActiveProfile`, and
   any free-form string inside `openaps.suggested.reason` — all of which
   appear verbatim in the API reference's verified live captures
   (`docs/references/nightscout-v3-api.md` lines 157, 213–215, 247, 286). A
   real DevInstance capture anonymized today would leak `"device": "xDrip-
   DexbridgeWixel"`, `"pumpSerial": "PUMP_10154415"`, the AAPS build string
   `"Version": "3.4.0.0-dev-e7de99043a-2026.01.10"`, and the human-readable
   reason blob that quotes basal/ISF numbers. Fix before any fixture is
   actually committed to `tests/fixtures/`.

2. **I-2 (important) — German translation `loop_eventual_bg` = "Loop Ziel-BG"
   collides semantically with `loop_target_bg` = "Loop Zielwert".** The
   English source distinguishes "eventual BG" (projected 30–60-min-out
   prediction from the loop's suggested/enacted) from "target BG" (the loop
   setpoint). The current German renders both as flavours of "Ziel…" which
   will confuse users on the dashboard where both entities live side by
   side. Suggested wording: `loop_eventual_bg` → `"Loop Prognose-BG"` or
   `"Loop erwarteter BG"`.

Everything else in this review is nit-level.

---

## Summary of work reviewed

- **`scripts/anonymize_fixtures.py`** — hoists DROP/SENSITIVE/TIMESTAMP into
  module-level sets, recursively scrubs dicts/lists, rebases ms-scale
  timestamps, buckets carbs to the nearest 10 g, and regenerates `_id`s
  from `secrets.choice`. CLI accepts files *or* directories (a plan-spec
  bonus — plan text only described files).
- **`scripts/capture_fixtures.py`** — dataclass-based config, env-var-driven,
  `FORBIDDEN_HOSTS = {"prod-nightscout.example.invalid"}` with a dedicated exit code 3,
  dispatch-dict over five v3 endpoints. Uses the real
  `api.auth.JwtManager` / `api.client.NightscoutV3Client` names.
- **`scripts/smoke_test.py`** — separate `refuse_forbidden_hosts` helper
  (the plan inlined it); `probe_capabilities(client)` + `caps.to_dict()`
  corrected to match Phase 1; defensive `.get("result", [])` extraction
  for both dict-envelope and bare-list responses.
- **`scripts/verify_silver.py`** — covers 18 of the 19 Silver-tier rule IDs
  from the plan's `SILVER_RULES_REQUIRED`, adds `check_has_entity_name`
  with the correct "base class wins, else every platform must declare it"
  logic, `check_manifest_declares_silver` behind an opt-in `--strict-manifest`
  flag, and an `_coerce` helper that maps unknown statuses to TODO rather
  than raising.
- **`tests/scripts/`** — 25 unit tests total, no network, `monkeypatch.setenv`
  based env-isolation, plan's buggy `assert RuleStatus.TODO in report.statuses`
  replaced with the correct `"test-before-configure" in report.failures`.
- **`translations/de.json`** — 47 new `entity.sensor.*` + 3 new
  `entity.binary_sensor.*` name keys, all 14 stats variants preserve the
  `{window}` placeholder required by `feature_registry.py`.
- **`.gitignore`** — adds `captures/` under a signposting comment.

Tests: `125 passed, 1 warning in 2.51s` (the warning is an upstream
`aioresponses`→`asyncio.iscoroutinefunction` deprecation, unrelated to this
phase).

---

## Plan alignment

| Plan section | Status | Notes |
|---|---|---|
| 4.1 `anonymize_fixtures.py` | delivered | incl. dir-recursion not in plan text |
| 4.2 `capture_fixtures.py` | delivered | dispatch-dict refactor — nice |
| 4.3 `smoke_test.py` | delivered | API-name refresh applied correctly |
| 4.4 `verify_silver.py` | delivered | coverage check (plan line 4727) intentionally not implemented — covered by pytest-cov `--cov-fail-under=95` in pyproject instead. Worth noting in the docstring so a future reader doesn't re-add it. |
| Task 4.5 — full de.json | delivered | 50 `entity.*` keys filled in |
| `captures/` in `.gitignore` | delivered | |

The API-name deviations flagged in the review brief (`api.jwt_manager` →
`api.auth.JwtManager`, `client.status()` → `client.get_status()`,
`ServerCapabilities.probe` → `probe_capabilities(client)`, `caps.as_dict()` →
`caps.to_dict()`) are **correct** — the plan's Phase 1 code samples aged
out; the implementation matches what's actually on disk in
`custom_components/nightscout_v3/api/`. Do not fold this back into the plan
unless you regenerate all Phase 1–4 code samples in one pass.

---

## Silver Quality Scale cross-check

Comparing `SILVER_RULES_REQUIRED` against the ledger in
`docs/references/ha-silver-quality-scale.md` §0:

| Silver rule | In verifier? | Notes |
|---|---|---|
| `action-exceptions` | yes | |
| `config-entry-unloading` | yes | |
| `docs-configuration-parameters` | yes | |
| `docs-installation-parameters` | **no** | **N-1 below** |
| `entity-unavailable` | yes | |
| `integration-owner` | yes | |
| `log-when-unavailable` | yes | |
| `parallel-updates` | yes | |
| `reauthentication-flow` | yes | |
| `test-coverage` | **no (by design)** | static gate can't measure runtime coverage; real check lives in pyproject `--cov-fail-under=95` |
| plus all 10 Bronze rules the plan listed | yes | |

`docs-installation-parameters` is an actual Silver rule present in
`quality_scale.yaml` as `todo`, so the verifier should fail on it and
currently doesn't. See N-1.

The translation-diff (`_flatten` + set-diff) is sound for the
strings.json/de.json shape: no arrays at leaf positions, all keys are dict-
or-string. The `PARALLEL_UPDATES` substring check and the
`_attr_has_entity_name = True` regex with the "base class wins, skip the
platform check" logic both match how HA actually resolves the attribute.

---

## Findings

### Critical
*(none)*

### Important

**I-1 — Anonymizer leaks device, pump, identifier, and free-form reason strings.**

`SENSITIVE_STRING_KEYS` covers human fields (`notes`, `enteredBy`, `email`,
`name` …) and server URLs, but real Nightscout v3 responses carry several
more identifying strings per
`docs/references/nightscout-v3-api.md`:

- `device` — e.g. `"xDrip-DexbridgeWixel"` (CGM bridge model → identifies hardware)
- `pumpSerial` — e.g. `"PUMP_10154415"` (literal device serial)
- `pumpType` — e.g. `"ACCU_CHEK_COMBO"` (pump model)
- `pumpId` — numeric pump-internal id
- `identifier` — v3's stable per-record UUID (analogue of `_id`, but
  `DROP_KEYS` only fakes `_id`)
- `reason`, `consoleLog`, `consoleError` — inside `openaps.suggested` /
  `.enacted`; `reason` is a human-readable blob that embeds ISF/CR/BG
  values
- `ActiveProfile` — e.g. `"200U Normal"` (user-named profile string, often
  contains insulin totals or the patient's first name)
- `Version` — AAPS build string, e.g. `"3.4.0.0-dev-e7de99043a-2026.01.10"`
  (git-hashes the uploader's build)

Recommended change to `scripts/anonymize_fixtures.py`:

```python
SENSITIVE_STRING_KEYS = {
    # existing
    "notes", "enteredBy", "profileJson", "created_at", "srvModified",
    "url", "baseURL", "instance", "hostname", "author", "email", "username",
    "name", "firstName", "lastName", "patient",
    # add — device / pump / AAPS
    "device", "pumpSerial", "pumpType", "Version", "ActiveProfile",
    "reason", "consoleLog", "consoleError", "LastBolus",
    "TempBasalStart",
}
DROP_KEYS = {"_id", "identifier", "pumpId"}  # random-replace both v1 and v3 ids
```

Also add a test exercising `devicestatus.pump.extended` / `openaps.suggested`
shapes; the current suite only covers entries + treatments.

Phone numbers and IP addresses embedded in the free-form `notes` field are
already handled — the entire `notes` string is replaced with `"redacted"`,
so any IP/phone content inside a user-typed note is scrubbed by key, not
by pattern. No regex pass needed for that.

---

**I-2 — `loop_eventual_bg` German wording collides with `loop_target_bg`.**

`custom_components/nightscout_v3/translations/de.json`:

```json
"loop_eventual_bg": { "name": "Loop Ziel-BG" },
"loop_target_bg":   { "name": "Loop Zielwert" },
```

"Eventual BG" in loop terminology is the predicted future BG the algorithm
expects 30–60 min out, not a target. Users will see two entities both named
around "Ziel-…" and have to guess which is which. Suggested fix:

```json
"loop_eventual_bg": { "name": "Loop Prognose-BG" },
```

or `"Loop erwarteter BG"`. Confirm with the user which reads more natural
before editing; either works for the Silver rule — this is a UX nit that
translation reviewers *do* catch.

---

**I-3 — `docs-installation-parameters` omitted from `SILVER_RULES_REQUIRED`.**

The rule is listed in `docs/references/ha-silver-quality-scale.md`
(table line 35 and §3.4), is present in `quality_scale.yaml` as `todo`,
and needs to flip to `done` for Silver. The current
`SILVER_RULES_REQUIRED` has only the four `docs-*` rules from the Bronze
tier plus `docs-configuration-parameters`. Add
`docs-installation-parameters` so the gate fails loud when docs Phase 6
lands.

---

### Nits

- **N-1 — `check_translations` re-flattens `strings.json` inside the
  per-locale loop.** Recompute outside the `for locale_file` loop; at two
  locales it's free, at twelve it adds up. Pure perf nit.

- **N-2 — `FORBIDDEN_HOSTS` duplicated across `smoke_test.py` and
  `capture_fixtures.py`.** DRY into a tiny `scripts/_safety.py` or add a
  test that asserts both modules pin the same set, so a future copy-paste
  can't silently diverge. Not urgent.

- **N-3 — Substring match for `prod-nightscout.example.invalid` would trigger on
  `not-prod-nightscout.example.invalid`.** This is fail-safe (refuses a valid host),
  so keep it. If you ever regret the false-positive, switch to
  `urllib.parse.urlparse(url).hostname` + suffix match.

- **N-4 — `capture_fixtures._capture` never catches/cleans up on mid-
  endpoint failure.** If endpoint 2 of 4 raises, endpoint-1's file is on
  disk and the JWT session never receives `jwt.close()` (if that exists).
  Dev script, low priority.

- **N-5 — `anonymize_fixtures` does not warn when it encounters a key
  that looks sensitive (e.g. contains `"token"` or `"secret"`) but isn't
  in `SENSITIVE_STRING_KEYS`.** A defensive warn-on-unknown-string-keys
  pass would future-proof against new Nightscout fields; optional.

- **N-6 — `verify_silver` docstring promises a coverage-threshold check
  (plan line 4727: "Coverage summary ≥ 90 % overall, ≥ 95 % for
  config_flow.py").** The script intentionally delegates this to
  pyproject (`--cov-fail-under=95`). Add one line to the module docstring
  so a future maintainer doesn't re-implement it under the wrong
  assumption that it's missing.

- **N-7 — `anonymize_fixtures._bucket_carbs` uses `isinstance(v, int |
  float)` but `bool` is a subclass of `int`.** Bolus records don't carry
  boolean carbs, so this is theoretical; adding `and not isinstance(v,
  bool)` is belt-and-braces.

- **N-8 — `scripts/__init__.py` and `tests/scripts/__init__.py` are both
  empty.** Add the standard one-line docstring so that `pytest --collect-
  only` output is self-documenting. Pure polish.

---

## Safety audit (public exposure)

Only `prod-nightscout.example.invalid` and `dev-nightscout.example.invalid` hostnames appear in
committed code or tests — no tokens, no account identifiers, no names.
Every occurrence is either a `FORBIDDEN_HOSTS` constant, a test URL that
triggers the guard-rail, or a plan-doc reference. Consistent with the
project's stated operational boundary.

`captures/` is `.gitignore`d. Anonymizer is the only path by which real
data can move into `tests/fixtures/`, which makes I-1 load-bearing.

---

## Test quality

- Script tests are unit-only, offline, `monkeypatch.setenv`-driven.
  That's the correct call for CI hygiene and the plan's own "no network
  in pytest" rule.
- Coverage of script *logic* (as opposed to `_capture`'s aiohttp loop,
  which is intentionally not covered) is good:
  - `anonymize_payload` — URL/token/note/timestamp/carbs rebasing covered
    (but see I-1 for additional shape gaps).
  - `build_client_config` — all four branches (missing url, missing
    token, refused host, trailing-slash strip).
  - `refuse_forbidden_hosts` + `parse_args` — both branches, plus a
    custom-limit assertion.
  - `check_quality_scale_yaml` — short-form DONE, short-form TODO, dict
    EXEMPT-with-comment, dict EXEMPT-without-comment.
  - `check_translations` — missing-key branch and the no-strings.json
    short-circuit.
  - `check_parallel_updates` — present vs missing.
  - `check_has_entity_name` — base-class-wins vs per-platform-required.
  - `check_manifest_declares_silver` — both branches.
  - `main` happy path + error path.
- Integration tests against a live DevInstance would be valuable but require
  credentials, which is out of scope for the Phase 4 gate.

---

## Architecture notes (no change requested)

- The `scripts/` namespace is a regular package (`__init__.py` present)
  rather than a PEP 420 namespace — correct, because
  `python -m scripts.foo` needs the metadata for relative imports.
- `verify_silver` takes `--root` so it's pytest-tmp-path testable without
  mocking the filesystem — excellent. Keep this pattern.
- The dispatch-dict in `capture_fixtures._capture` is strictly nicer than
  the plan's if/elif chain — easier to extend when Phase 7 adds
  `profile` variants.

---

## Commit message

`feat(scripts): phase 4 dev/ops tooling + full de.json entity translations`

Accurate and scoped. No mid-commit scope creep.

---

## Follow-ups for the implementer

1. Expand `SENSITIVE_STRING_KEYS` / `DROP_KEYS` per I-1 and add a
   `devicestatus`-shaped fixture to the anonymizer tests.
2. Retranslate `loop_eventual_bg` per I-2.
3. Add `docs-installation-parameters` to `SILVER_RULES_REQUIRED` per
   I-3.
4. Optionally land N-1 / N-2 / N-6 in the same cleanup commit; the rest
   can wait.

Phase 4 is otherwise good work — small, focused, tested, doesn't touch
the HA integration surface. The de.json update is exactly the kind of
low-risk translation fill that belongs in the same commit as dev tooling.
