# Contributing

Thanks for contributing to Nightscout v3.

This file is intentionally practical: how to report a useful issue, how to run
the project locally, and what we expect from pull requests.

## Before you open an issue or PR

- Read [README.md](README.md) first. It is the user-facing reference for setup,
  supported functionality, limitations, and troubleshooting.
- For bug reports, include your Home Assistant version, integration version,
  Nightscout version, and the exact symptom you are seeing.
- For behavior changes, include tests and any related README updates in the
  same pull request.

## Development setup

```bash
git clone <repo>
cd ha-nightscout-v3
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
pre-commit install
```

Python `3.13+` is required. CI currently targets Python `3.14`.
The test suite runs directly from the checked-out source tree; an editable
install is not required.

## Run checks locally

Before opening a PR, run:

```bash
ruff check .
ruff format --check .
mypy custom_components/nightscout_v3
pytest
python -m scripts.verify_silver --strict-manifest
```

If you have a local Home Assistant Core checkout available, run `hassfest`
there as well, especially after `manifest.json`, translations, or integration
metadata changes.

The test environment is provided by
`pytest-homeassistant-custom-component`.

## Tests and fixtures

- Add or update tests with every behavior change.
- Unit tests must not make live network calls.
- Never commit raw Nightscout captures.
- If you refresh fixtures, capture from a dedicated non-production Nightscout
  test instance only.
- Run `scripts/anonymize_fixtures.py` before committing fixture updates and
  verify the anonymized output still looks safe to publish.
- If Nightscout starts returning a new identifying field, extend the anonymizer
  and add a regression test for it.

## Code expectations

- Keep the integration UI-configurable. New user-facing configuration should go
  through config flows or options flows when appropriate.
- Use `ConfigEntry.runtime_data` for runtime state.
- Prefer targeted exception handling over blanket catches.
- Production code should pass `mypy --strict`.
- Update docs, dashboard examples, or diagnostics-related notes when user
  behavior changes.

## Pull requests

- Keep PRs focused and explain the user-visible impact.
- Include tests for new behavior and regressions.
- Prefer conventional commits such as `feat:`, `fix:`, `docs:`, `test:`, or
  `chore:`.
- Do not commit secrets, raw captures, or personally identifying Nightscout
  data.

## Getting help

Open an issue or draft PR if you want feedback before finishing a change.

For bug reports, include:

- Home Assistant version
- integration version
- Nightscout version
- relevant log excerpt
- diagnostics export when possible
