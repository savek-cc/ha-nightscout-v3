# Final Release Review — Pass 2

Date: 2026-04-22
Reviewer: code-reviewer agent (pass 2)
Target: v0.1.0 Silver-Gate release

## Verdict

APPROVED FOR TAG

All pass-1 criticals are closed with regression coverage. Remaining ruff
findings are cosmetic style rules outside the F/RUF/ASYNC/D families that
were in scope for pass 1 and do not affect Silver compliance. Tests are
green (170 passed, 95.50 % coverage). `verify_silver --strict-manifest`
exits 0.

## Pass-1 finding status

| ID  | Title                                  | Status     | Evidence                                                                                                                                                                                                                                  |
| --- | -------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C-1 | JWT / token URL leak in `ApiError`     | closed     | `custom_components/nightscout_v3/api/auth.py:82-110`: `_exchange_once` never interpolates `url` or response body into `ApiError`; the `ClientError/TimeoutError` branch uses `type(exc).__name__` only and explicitly documents why; malformed-body branch reports only field names. Regression test at `tests/test_auth.py:207-232` pins the invariant with a realistic JWT-shaped leaked value and also checks `__cause__`. |
| C-2 | Diagnostics redaction mismatch         | closed     | `custom_components/nightscout_v3/diagnostics.py:12-24` redacts `url`, `access_token`, `api_secret`, `identifier`, `sub`, `token`, `reason`, `notes`, `note`, `last_note`, `enteredBy`. Regression test at `tests/test_diagnostics.py:52-89` asserts `loop.reason`, `care.last_note`, `uploader.enteredBy` are all scrubbed. `docs/architecture.md:21` and `README.md:122-124` promises line up with code. |
| I-1 | Missing docstrings on public surface   | closed     | `ruff --select=D` clean; spot-checked `api/auth.py`, `api/capabilities.py`, `api/client.py`, `coordinator.py`, `history_store.py`, `models.py` — docstrings are accurate, not boilerplate. |
| I-2 | Ruff F/RUF/ASYNC findings              | closed     | `ruff --select=F,RUF,ASYNC` clean (commit a0cff28).                                                                                                                                                                                       |
| I-3 | Stale `# noqa: BLE001` directives      | closed     | `grep -rn "BLE001"` returns nothing (commit 503afb0).                                                                                                                                                                                     |
| I-4 | Dead `NotReady` exception class        | closed     | `grep -n "NotReady" custom_components/nightscout_v3/api/exceptions.py` returns 0 matches. `exceptions.py` exports only `ApiError`, `AuthError` (commit dc646a5).                                                                           |
| I-5 | Long lines in config_flow.py           | closed     | No E501 findings in `config_flow.py` (commit 503afb0).                                                                                                                                                                                    |

## New findings (pass 2)

### Critical

None.

I scanned for new leak shapes across the whole package:

- **No `ApiError` interpolates `url`, `self._base_url`, `access_token`, or any
  response object.** The one remaining `f"{self._base_url}…"` site is
  `api/auth.py:63` and the one in `api/client.py:113`; both are local `url`
  variables that never reach an exception message. `api/client.py` error
  branches only surface `path` and `resp.status`.
- **No `_LOGGER.error/warning/debug(..., extra={...})` includes the token.**
  The `__init__.py:80` debug log emits `"JWT refresh failed transiently: %s", exc`
  — and `exc` is now guaranteed URL/token-free by C-1.
- **No `str(resp)` / `repr(exc)` that could contain the token.**
  `coordinator.py:138-142` and `__init__.py:45-54` use `str(exc)` on
  `AuthError` / `ApiError`, which are our own types with controlled messages.
- **No real-looking tokens or URLs committed to `tests/fixtures/`.** Tests
  use obvious sentinels (`"SECRET"`, `"LEAK_REASON_…"`, `"tok"`,
  `"access-test"`, `"accesstoken-testuser"`). No private hostnames found.

### Important

- `config_flow.py:105, 134` use bare `_LOGGER.exception("Unhandled error…")`.
  The catch is `except Exception:`, so a truly unexpected exception type
  could produce a traceback that references the local `url`/`token` vars
  in frame locals. Home Assistant does not dump frame locals by default,
  only formatted tracebacks, so in practice this is safe — but the pattern
  is brittle. **Post-release**: consider narrowing the catch or scrubbing
  the logged exception. Not a v0.1.0 blocker.

### Pre-existing ruff findings

`ruff check --output-format=concise` reports 42 findings across rule
families that were **not** called out in pass 1. My judgment, rule by rule:

| Rule family        | Count  | Ship at 0.1.0? | Rationale                                                                                                                                                                                                             |
| ------------------ | ------ | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E501 (long lines)  | ~15    | Yes            | Legacy long lines in `feature_registry.py`, `history_store.py`, `coordinator.py`. Cosmetic. Not a Silver rule.                                                                                                        |
| I001 (import sort) | ~8     | Yes            | `ruff --fix` can close these in one commit post-release. Not functional.                                                                                                                                              |
| UP017/UP037/UP042/UP043 | ~5 | Yes            | Python 3.12+ modernization hints (`datetime.UTC` alias, unnecessary string annotations, `str, Enum` inheritance on `RuleStatus`). Not a correctness or Silver issue.                                                  |
| SIM108/SIM105/SIM300 | 3    | Yes            | Style preference (ternary, `contextlib.suppress`, yoda conditions). No behavioral impact.                                                                                                                             |
| S105               | 1      | Yes — **false positive** | `CONF_ACCESS_TOKEN: Final = "access_token"` is a form-field key, not a secret. Safe to add `# noqa: S105` or configure an ignore; can wait for post-release.                                                |

None of these are Silver-gate blockers. They should all be tracked as
post-release tech debt and closed in a follow-up "style sweep" PR.

## Verification evidence

- **Test suite**: 170 passed, 1 warning (a third-party
  `asyncio.iscoroutinefunction` DeprecationWarning from `aioresponses`, not
  our code). Coverage 95.50 %, over the 95 % Silver floor. `diagnostics.py`
  is at 100 %, `api/auth.py` 100 %, `api/client.py` 100 %.
- **`ruff check --select=F,RUF,ASYNC,D`**: "All checks passed!" (two
  compatibility warnings about D203/D211 and D212/D213 pairs are config
  quirks, not findings).
- **`verify_silver --strict-manifest`**: `silver: ok`, exit 0.

## Recommendation

**Tag v0.1.0 now.** Both pass-1 criticals are closed with regression tests
that pin the invariants. All pass-1 importants are closed. The 42
remaining ruff findings belong in a follow-up "style sweep" issue
(`chore(style): close remaining ruff findings`) and are not release
blockers for a HACS-only integration shipping at Silver.

Follow-up items to open as issues before or immediately after the tag:

1. `chore(style): close remaining ruff findings (E501, I001, UP, SIM, S105)`.
2. `refactor(config_flow): narrow or scrub _LOGGER.exception catch-all`
   (hardening, not a known leak).
