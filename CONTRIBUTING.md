# Contributing

Thanks for looking. This integration is developed under a few hard rules;
please skim all of them before sending a patch.

## Dev setup

```bash
git clone <repo>
cd ha-nightscout-v3
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pre-commit install
```

Python ≥ 3.13 (we target 3.14 in CI). Home Assistant dev dependencies are
installed transitively via `pytest-homeassistant-custom-component`.

## Test-only-against-DevInstance rule

We have two real Nightscout instances:

- **DevInstance** (`dev-nightscout.example.invalid`) — the dev / test target. Live smoke tests
  and fixture captures run here.
- **ProdInstance** (`prod-nightscout.example.invalid`) — **production**. Never run any capture,
  smoke test, or experimental request against it. The scripts in
  `scripts/capture_fixtures.py` and `scripts/smoke_test.py` enforce this with
  a `FORBIDDEN_HOSTS` guard that exits non-zero if the URL resolves to a
  ProdInstance host. **Do not weaken or remove this guard** — treat any PR that
  bypasses it as a bug.

## Fixture workflow

Raw captures never land in git. The flow is:

1. `python -m scripts.capture_fixtures` with `NS_URL` / `NS_TOKEN` pointing
   at DevInstance → writes raw JSON under `captures/` (gitignored).
2. `python -m scripts.anonymize_fixtures captures/ tests/fixtures/` →
   scrubs URLs, tokens, patient notes, device serials, pump firmware,
   openaps reason blobs; buckets carbs to the nearest 10 g; rebases
   timestamps; regenerates opaque IDs.
3. Commit only the anonymized files. `captures/` is gitignored.

If you add a new sensitive key upstream (e.g. Nightscout starts shipping a
new device identifier), extend `SENSITIVE_STRING_KEYS` / `DROP_KEYS` in
`scripts/anonymize_fixtures.py` and add a regression test in
`tests/scripts/test_anonymize_fixtures.py`.

## Code style

- **ruff** (`ruff check .` + `ruff format .`). See `ruff.toml`.
- **pyright / basedpyright** — we target `strict`. No `# type: ignore`
  without a one-line justification comment.
- **No blanket `except:`** and no `except Exception:` without a targeted
  log + re-raise.
- **No backward-compat shims** — when a signature changes, change all
  callers in the same commit. There is no external user of internal APIs.
- **runtime_data everywhere** — never store entry state in
  `hass.data[DOMAIN][entry.entry_id]`.

## Test expectations

- Overall coverage floor: **90 %**. `config_flow.py` floor: **95 %**.
- New behavior begins with a failing test (TDD). Both the plan and the
  review gates enforce this.
- **No network in unit tests.** Integration-layer tests use
  `aioresponses`; domain-layer tests are pure.
- pytest markers: no slow tests at the moment; if you add one, mark it
  `@pytest.mark.slow` and exclude from default run.

## Commit style

[conventional commits](https://www.conventionalcommits.org/): `feat(api): …`,
`fix(coordinator): …`, `docs: …`, `test(statistics): …`, `chore: …`, etc.
One logical change per commit. Squash fixups locally before pushing.

Co-authorship trailer for AI-assisted work is fine, but make it truthful.

## Silver Quality Scale gate

Before opening a PR, run:

```bash
python -m scripts.verify_silver --strict-manifest
pytest --cov
ruff check .
python -m script.hassfest --integration-path custom_components/nightscout_v3   # if HA dev repo is accessible
```

All four must pass. `verify_silver` checks `quality_scale.yaml`, translation
completeness, `PARALLEL_UPDATES` presence on platforms, `_attr_has_entity_name`
on the base entity, and that `manifest.json` declares `quality_scale: silver`.

## Code review flow

Every phase closes with a code-reviewer subagent pass whose report lands
under `docs/reviews/`. If your change spans a phase boundary, include a
fresh review commit in the same PR. Review verdicts of "request changes"
get addressed in the same PR — don't merge with known findings.

## Dashboards

Dashboards live under `dashboards/` and are **not** shipped inside the
integration. A smoke test (`tests/dashboards/test_yaml_shape.py`) ensures
every `sensor.nightscout_v3_*` / `binary_sensor.nightscout_v3_*` reference
resolves to a real feature key in `FEATURE_REGISTRY` or
`stats_feature_defs(14)`. If you rename a feature key, the dashboard test
will catch the divergence immediately.

## Getting help

Open an issue. Include `diagnostics` output (redacted by the integration),
a ruff/pytest failure log if applicable, and your HA + integration
versions.
