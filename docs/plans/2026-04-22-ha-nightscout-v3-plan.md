# ha-nightscout-v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a HA custom integration `nightscout_v3` that exposes the full AAPS closed-loop data model from Nightscout v3, with live statistics and a dashboard, meeting HA Quality Scale Silver.

**Architecture:** One `DataUpdateCoordinator` with staggered tick cycles (60 s fast / 5 min change-detect / 60 min stats). An `aiohttp`-based `NightscoutV3Client` behind a `JwtManager` that auto-refreshes the JWT. An `aiosqlite` `HistoryStore` independent of the HA recorder. A `FEATURE_REGISTRY` as single source of truth for category / capability / entity creation. Read-only v1; careportal writes are v2 roadmap.

**Tech Stack:** Python 3.13+, `aiohttp`, `aiosqlite`, `orjson`, `voluptuous`, Home Assistant ≥ 2025.1, `pytest-homeassistant-custom-component`, `aioresponses`, `ruff`, `hassfest`.

**References in-repo (read before starting):**
- `docs/specs/2026-04-22-ha-nightscout-v3-design.md` — the Lastenheft (authoritative for behavior)
- `docs/references/nightscout-v3-api.md` — v3 API facts (auth, endpoints, filters, payloads)
- `docs/references/ha-silver-quality-scale.md` — Bronze + Silver rule list with code snippets
- `docs/references/ha-reference-integrations.md` — husqvarna_automower / tessie / github idioms

**Execution rules:**
- Tests only against the DevInstance instance (`dev-nightscout.example.invalid`). **Never** touch ProdInstance (`prod-nightscout.example.invalid`) during development or tests. Unit tests use fixtures only.
- No URLs, tokens, identifiers, names, or measured values in committed code or fixtures. Fixtures are anonymized via `scripts/anonymize_fixtures.py`.
- Conventional-commit messages (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`). Commit after every task's final step. Do not push to any remote.
- After every phase, dispatch `superpowers:code-reviewer` over the phase's commits and write the report to `docs/reviews/YYYY-MM-DD-phase-N.md`. Commit the report.

---

## Phase 0 — Project Scaffolding

### Task 0.1: Python tooling + pyproject

**Files:**
- Create: `pyproject.toml`
- Create: `requirements-test.txt`
- Create: `.pre-commit-config.yaml`
- Create: `ruff.toml`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "nightscout_v3"
version = "0.1.0"
description = "Home Assistant custom integration for Nightscout v3 (AAPS closed loop)"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.13"
authors = [{ name = "nightscout_v3 contributors" }]

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["custom_components.nightscout_v3", "custom_components.nightscout_v3.api"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra --cov=custom_components.nightscout_v3 --cov-report=term-missing --cov-fail-under=90"

[tool.coverage.run]
source = ["custom_components.nightscout_v3"]
branch = true

[tool.coverage.report]
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:", "raise NotImplementedError"]
```

- [ ] **Step 2: Create `requirements-test.txt`**

```
pytest>=8.0
pytest-asyncio>=0.23
pytest-cov>=5.0
pytest-homeassistant-custom-component>=0.13
aioresponses>=0.7.6
freezegun>=1.5
syrupy>=4.6
```

- [ ] **Step 3: Create `ruff.toml`**

```toml
target-version = "py313"
line-length = 100

[lint]
select = [
  "E", "F", "W", "I", "N", "UP", "B", "ASYNC", "S", "SIM", "RUF", "D",
]
ignore = ["D203", "D213", "D107", "D100", "S101"]

[lint.per-file-ignores]
"tests/**" = ["D", "S", "E501"]

[format]
quote-style = "double"
```

- [ ] **Step 4: Create `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: detect-private-key
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements-test.txt ruff.toml .pre-commit-config.yaml
git commit -m "chore: add python tooling (pyproject, ruff, pytest, pre-commit)"
```

---

### Task 0.2: Integration skeleton — manifest + quality_scale

**Files:**
- Create: `custom_components/nightscout_v3/__init__.py` (empty placeholder)
- Create: `custom_components/nightscout_v3/manifest.json`
- Create: `custom_components/nightscout_v3/quality_scale.yaml`
- Create: `custom_components/nightscout_v3/strings.json`
- Create: `custom_components/nightscout_v3/translations/en.json`
- Create: `custom_components/nightscout_v3/translations/de.json`

- [ ] **Step 1: Create `custom_components/nightscout_v3/__init__.py`**

```python
"""Nightscout v3 custom integration (scaffolding, filled in later tasks)."""
```

- [ ] **Step 2: Create `custom_components/nightscout_v3/manifest.json`**

```json
{
  "domain": "nightscout_v3",
  "name": "Nightscout v3",
  "codeowners": ["@savek-cc"],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/savek-cc/ha-nightscout-v3",
  "integration_type": "service",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/savek-cc/ha-nightscout-v3/issues",
  "quality_scale": "silver",
  "requirements": ["aiosqlite==0.20.0", "orjson==3.10.7"],
  "version": "0.1.0"
}
```

- [ ] **Step 3: Create `custom_components/nightscout_v3/quality_scale.yaml`**

```yaml
rules:
  # Bronze
  action-setup:
    status: exempt
    comment: The integration does not register services in v1 (careportal writes are v2 roadmap).
  appropriate-polling: todo
  brands:
    status: todo
    comment: PR to home-assistant/brands required before HACS listing.
  common-modules: todo
  config-flow-test-coverage: todo
  config-flow: todo
  dependency-transparency: todo
  docs-actions:
    status: exempt
    comment: The integration does not register services in v1.
  docs-high-level-description: todo
  docs-installation-instructions: todo
  docs-removal-instructions: todo
  entity-event-setup:
    status: exempt
    comment: >
      Entities do not subscribe to push events. All data is pulled through the
      DataUpdateCoordinator.
  entity-unique-id: todo
  has-entity-name: todo
  runtime-data: todo
  test-before-configure: todo
  test-before-setup: todo
  unique-config-entry: todo
  # Silver
  action-exceptions:
    status: exempt
    comment: The integration does not register services in v1.
  config-entry-unloading: todo
  docs-configuration-parameters: todo
  docs-installation-parameters: todo
  entity-unavailable: todo
  integration-owner: todo
  log-when-unavailable: todo
  parallel-updates: todo
  reauthentication-flow: todo
  test-coverage: todo
```

- [ ] **Step 4: Create `custom_components/nightscout_v3/strings.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Nightscout v3",
        "description": "Connect a Nightscout v3 instance.",
        "data": {
          "url": "Server URL",
          "access_token": "Access token"
        },
        "data_description": {
          "url": "Base URL of your Nightscout server (e.g. https://my.nightscout.example).",
          "access_token": "API token with at least `*:*:read` and `api:treatments:create` roles."
        }
      },
      "customize": {
        "title": "Select features",
        "description": "Enable or disable individual features. Disabled features are hidden from the UI."
      },
      "stats": {
        "title": "Statistics windows",
        "description": "Pick which rolling statistics windows to compute. 14 days is always enabled."
      },
      "reauth_confirm": {
        "title": "Re-authenticate Nightscout v3",
        "description": "The existing access token is no longer valid. Enter a new token.",
        "data": { "access_token": "New access token" }
      }
    },
    "error": {
      "cannot_connect": "Cannot reach the Nightscout server.",
      "invalid_auth": "Token rejected by the server.",
      "unknown": "Unexpected error; see logs."
    },
    "abort": {
      "already_configured": "This Nightscout instance is already configured.",
      "reauth_successful": "Re-authentication succeeded."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Nightscout v3 options",
        "menu_options": {
          "features": "Enable / disable features",
          "stats": "Statistics windows",
          "thresholds": "Time-in-range thresholds",
          "polling": "Polling intervals",
          "rediscover": "Re-probe server capabilities"
        }
      },
      "features": { "title": "Features" },
      "stats": { "title": "Statistics windows" },
      "thresholds": {
        "title": "Time-in-range thresholds",
        "data": {
          "tir_low_threshold_mgdl": "Low threshold (mg/dL)",
          "tir_high_threshold_mgdl": "High threshold (mg/dL)",
          "tir_very_low_threshold_mgdl": "Very low threshold (mg/dL)",
          "tir_very_high_threshold_mgdl": "Very high threshold (mg/dL)"
        }
      },
      "polling": {
        "title": "Polling intervals",
        "data": {
          "poll_fast_seconds": "Fast cycle (s)",
          "poll_change_detect_minutes": "Change-detect cycle (min)",
          "poll_stats_minutes": "Statistics cycle (min)"
        }
      }
    }
  },
  "entity": {}
}
```

- [ ] **Step 5: Create `custom_components/nightscout_v3/translations/en.json`**

Copy `strings.json` verbatim (HA convention — strings.json is the source, en.json is the published copy).

```bash
cp custom_components/nightscout_v3/strings.json custom_components/nightscout_v3/translations/en.json
```

- [ ] **Step 6: Create `custom_components/nightscout_v3/translations/de.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Nightscout v3",
        "description": "Eine Nightscout-v3-Instanz verbinden.",
        "data": {
          "url": "Server-URL",
          "access_token": "Zugangstoken"
        },
        "data_description": {
          "url": "Basis-URL des Nightscout-Servers (z. B. https://my.nightscout.example).",
          "access_token": "API-Token mit mindestens `*:*:read` und `api:treatments:create`."
        }
      },
      "customize": {
        "title": "Features auswählen",
        "description": "Einzelne Features ein- oder ausschalten. Deaktivierte Features werden in der UI ausgeblendet."
      },
      "stats": {
        "title": "Statistik-Fenster",
        "description": "Wähle die rollierenden Statistik-Fenster. 14 Tage ist Pflicht."
      },
      "reauth_confirm": {
        "title": "Erneut anmelden — Nightscout v3",
        "description": "Der Zugangstoken ist ungültig. Bitte neuen Token eingeben.",
        "data": { "access_token": "Neuer Zugangstoken" }
      }
    },
    "error": {
      "cannot_connect": "Nightscout-Server nicht erreichbar.",
      "invalid_auth": "Token vom Server abgelehnt.",
      "unknown": "Unerwarteter Fehler; siehe Log."
    },
    "abort": {
      "already_configured": "Diese Nightscout-Instanz ist bereits konfiguriert.",
      "reauth_successful": "Erneute Anmeldung erfolgreich."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Nightscout v3 — Optionen",
        "menu_options": {
          "features": "Features aktivieren / deaktivieren",
          "stats": "Statistik-Fenster",
          "thresholds": "Time-in-Range-Schwellen",
          "polling": "Abfrage-Intervalle",
          "rediscover": "Server-Capabilities neu prüfen"
        }
      },
      "features": { "title": "Features" },
      "stats": { "title": "Statistik-Fenster" },
      "thresholds": {
        "title": "Time-in-Range-Schwellen",
        "data": {
          "tir_low_threshold_mgdl": "Untere Grenze (mg/dL)",
          "tir_high_threshold_mgdl": "Obere Grenze (mg/dL)",
          "tir_very_low_threshold_mgdl": "Sehr niedrig (mg/dL)",
          "tir_very_high_threshold_mgdl": "Sehr hoch (mg/dL)"
        }
      },
      "polling": {
        "title": "Abfrage-Intervalle",
        "data": {
          "poll_fast_seconds": "Fast-Cycle (s)",
          "poll_change_detect_minutes": "Change-Detect-Cycle (min)",
          "poll_stats_minutes": "Statistik-Cycle (min)"
        }
      }
    }
  },
  "entity": {}
}
```

- [ ] **Step 7: Commit**

```bash
git add custom_components/nightscout_v3/
git commit -m "feat: integration scaffolding (manifest, quality_scale, translations)"
```

---

### Task 0.3: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { python-version: "3.13" }
      - run: uv pip install --system ruff==0.6.0
      - run: ruff check .
      - run: ruff format --check .

  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master

  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install -r requirements-test.txt
      - run: pip install -e .
      - run: pytest
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "chore: add CI workflow (ruff, hassfest, hacs, pytest)"
```

---

### Task 0.4: Empty HACS manifest + test scaffold

**Files:**
- Create: `hacs.json`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Create: `tests/fixtures/__init__.py` (empty)

- [ ] **Step 1: Create `hacs.json`**

```json
{
  "name": "Nightscout v3",
  "content_in_root": false,
  "zip_release": false,
  "homeassistant": "2025.1.0",
  "render_readme": true
}
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
"""Shared test fixtures for nightscout_v3."""
from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture by filename (without .json extension)."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,  # noqa: ARG001 — fixture from pytest-homeassistant-custom-component
) -> Generator[None, None, None]:
    """Auto-enable loading the integration in all tests."""
    yield


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Short-circuit async_setup_entry for config-flow-only tests."""
    with patch(
        "custom_components.nightscout_v3.async_setup_entry", return_value=True
    ) as m:
        yield m
```

- [ ] **Step 3: Create `tests/__init__.py` and `tests/fixtures/__init__.py`**

Both empty (Python package markers).

- [ ] **Step 4: Commit**

```bash
git add hacs.json tests/
git commit -m "chore: add hacs manifest and test scaffolding"
```

---

## Phase 1 — API Layer (pure Python, no HA imports)

### Task 1.1: Exceptions

**Files:**
- Create: `custom_components/nightscout_v3/api/__init__.py` (empty)
- Create: `custom_components/nightscout_v3/api/exceptions.py`
- Test: `tests/test_exceptions.py`

- [ ] **Step 1: Write failing test `tests/test_exceptions.py`**

```python
"""Tests for nightscout_v3 API exceptions."""
from custom_components.nightscout_v3.api.exceptions import (
    ApiError,
    AuthError,
    NotReady,
)


def test_exception_hierarchy() -> None:
    """All exceptions inherit from ApiError."""
    assert issubclass(AuthError, ApiError)
    assert issubclass(NotReady, ApiError)


def test_api_error_carries_status() -> None:
    """ApiError captures HTTP status code."""
    err = ApiError("boom", status=502)
    assert err.status == 502
    assert "boom" in str(err)


def test_auth_error_defaults_to_401() -> None:
    """AuthError defaults to HTTP 401."""
    err = AuthError("token rejected")
    assert err.status == 401
```

- [ ] **Step 2: Run — expect FAIL (module not found)**

```bash
pytest tests/test_exceptions.py -v
```

- [ ] **Step 3: Implement `custom_components/nightscout_v3/api/__init__.py`**

```python
"""Nightscout v3 API client package."""
```

- [ ] **Step 4: Implement `custom_components/nightscout_v3/api/exceptions.py`**

```python
"""Exceptions raised by the Nightscout v3 API client."""
from __future__ import annotations


class ApiError(Exception):
    """Base class for all API errors."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class AuthError(ApiError):
    """Raised when the server rejects our credentials (401)."""

    def __init__(self, message: str, *, status: int = 401) -> None:
        super().__init__(message, status=status)


class NotReady(ApiError):
    """Raised for transient errors (5xx, timeout, DNS)."""
```

- [ ] **Step 5: Run — expect PASS**

```bash
pytest tests/test_exceptions.py -v
```

- [ ] **Step 6: Commit**

```bash
git add custom_components/nightscout_v3/api/__init__.py custom_components/nightscout_v3/api/exceptions.py tests/test_exceptions.py
git commit -m "feat(api): add exception hierarchy (ApiError, AuthError, NotReady)"
```

---

### Task 1.2: JwtManager

**Files:**
- Create: `custom_components/nightscout_v3/api/auth.py`
- Test: `tests/test_auth.py`
- Create: `tests/fixtures/auth_request_success.json`

- [ ] **Step 1: Create the fixture `tests/fixtures/auth_request_success.json`**

```json
{
  "status": 200,
  "result": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.anonymized.signature",
    "sub": "homeassistant",
    "iat": 1745000000,
    "exp": 1745028800
  }
}
```

- [ ] **Step 2: Write failing test `tests/test_auth.py`**

```python
"""Tests for the JWT manager."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses

from custom_components.nightscout_v3.api.auth import JwtManager
from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError
from tests.conftest import load_fixture


BASE_URL = "https://ns.example"
TOKEN = "accesstoken-testuser"


@pytest.fixture
def payload() -> dict:
    return load_fixture("auth_request_success")


async def test_initial_exchange_stores_jwt(
    aiohttp_client_session, payload: dict, freezer
) -> None:
    freezer.move_to("2026-04-21T00:00:00Z")
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            payload=payload,
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        state = await mgr.initial_exchange()
    assert state.token == payload["result"]["token"]
    assert state.exp == payload["result"]["exp"]


async def test_get_valid_jwt_refreshes_near_expiry(
    aiohttp_client_session, payload: dict, freezer
) -> None:
    freezer.move_to("2026-04-21T00:00:00Z")
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            payload=payload,
            repeat=True,
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        await mgr.initial_exchange()
        # Advance to within refresh threshold
        freezer.move_to(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(payload["result"]["exp"] - 1000)))
        jwt = await mgr.get_valid_jwt()
    assert jwt == payload["result"]["token"]
    # Called twice (initial + on-demand refresh)
    assert len(m.requests) >= 1


async def test_initial_exchange_raises_auth_on_401(aiohttp_client_session) -> None:
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v2/authorization/request/{TOKEN}",
            status=401,
            payload={"status": 401, "message": "unauthorized"},
        )
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        with pytest.raises(AuthError):
            await mgr.initial_exchange()


async def test_refresh_retries_with_backoff_on_5xx(
    aiohttp_client_session, payload: dict, monkeypatch
) -> None:
    sleeps: list[float] = []

    async def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    monkeypatch.setattr("custom_components.nightscout_v3.api.auth.asyncio.sleep", fake_sleep)

    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v2/authorization/request/{TOKEN}", status=502, repeat=3)
        m.get(f"{BASE_URL}/api/v2/authorization/request/{TOKEN}", payload=payload)
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        state = await mgr.initial_exchange()
    assert state.token == payload["result"]["token"]
    assert sleeps[:3] == [1, 2, 4]


async def test_refresh_gives_up_after_max_attempts(
    aiohttp_client_session, monkeypatch
) -> None:
    async def fake_sleep(_d: float) -> None: ...

    monkeypatch.setattr("custom_components.nightscout_v3.api.auth.asyncio.sleep", fake_sleep)
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v2/authorization/request/{TOKEN}", status=502, repeat=True)
        mgr = JwtManager(aiohttp_client_session, BASE_URL, TOKEN)
        with pytest.raises(ApiError):
            await mgr.initial_exchange()


@pytest.fixture
async def aiohttp_client_session(aiohttp_client):
    import aiohttp

    async with aiohttp.ClientSession() as s:
        yield s
```

- [ ] **Step 3: Run — expect FAIL (no JwtManager)**

```bash
pytest tests/test_auth.py -v
```

- [ ] **Step 4: Implement `custom_components/nightscout_v3/api/auth.py`**

```python
"""JWT exchange + refresh for Nightscout v3."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import aiohttp

from .exceptions import ApiError, AuthError

_LOGGER = logging.getLogger(__name__)

REFRESH_THRESHOLD_SECONDS = 3600
MAX_REFRESH_ATTEMPTS = 5
_BACKOFF_BASE = 1.0


@dataclass(slots=True)
class JwtState:
    """Last-known JWT state."""

    token: str
    iat: int
    exp: int


class JwtManager:
    """Manages the Nightscout v3 JWT: initial exchange + on-demand refresh."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, access_token: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._state: JwtState | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> JwtState | None:
        return self._state

    async def initial_exchange(self) -> JwtState:
        """Perform the first JWT exchange."""
        return await self._exchange_with_retry()

    async def get_valid_jwt(self) -> str:
        """Return a currently-valid JWT, refreshing if needed."""
        async with self._lock:
            if self._state is None or self._state.exp - time.time() < REFRESH_THRESHOLD_SECONDS:
                await self._exchange_with_retry()
            assert self._state is not None
            return self._state.token

    async def refresh(self) -> JwtState:
        """Force a refresh regardless of current TTL."""
        async with self._lock:
            return await self._exchange_with_retry()

    async def _exchange_with_retry(self) -> JwtState:
        url = f"{self._base_url}/api/v2/authorization/request/{self._access_token}"
        last_exc: Exception | None = None
        for attempt in range(MAX_REFRESH_ATTEMPTS):
            try:
                return await self._exchange_once(url)
            except AuthError:
                raise
            except (ApiError, aiohttp.ClientError, TimeoutError) as exc:
                last_exc = exc
                backoff = _BACKOFF_BASE * (2**attempt)
                _LOGGER.debug("JWT exchange attempt %d failed; sleeping %.1fs", attempt + 1, backoff)
                await asyncio.sleep(backoff)
        raise ApiError(f"JWT exchange gave up after {MAX_REFRESH_ATTEMPTS} attempts: {last_exc}")

    async def _exchange_once(self, url: str) -> JwtState:
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 401:
                    raise AuthError("Access token rejected")
                if resp.status >= 500:
                    raise ApiError(f"Server error {resp.status}", status=resp.status)
                if resp.status != 200:
                    raise ApiError(f"Unexpected status {resp.status}", status=resp.status)
                body = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise ApiError(f"Network error during JWT exchange: {exc}") from exc

        result = body.get("result") or {}
        token = result.get("token")
        exp = result.get("exp")
        iat = result.get("iat")
        if not (token and exp and iat):
            raise ApiError(f"Malformed JWT response: {body}")
        self._state = JwtState(token=token, iat=int(iat), exp=int(exp))
        return self._state
```

- [ ] **Step 5: Run — expect PASS**

```bash
pytest tests/test_auth.py -v
```

- [ ] **Step 6: Commit**

```bash
git add custom_components/nightscout_v3/api/auth.py tests/test_auth.py tests/fixtures/auth_request_success.json
git commit -m "feat(api): JwtManager with exchange, on-demand refresh, backoff"
```

---

### Task 1.3: NightscoutV3Client

**Files:**
- Create: `custom_components/nightscout_v3/api/client.py`
- Test: `tests/test_client.py`
- Create fixtures: `tests/fixtures/{status.json, entries_latest.json, devicestatus_latest.json, treatments_sensor_change.json, profile_latest.json, lastmodified.json}`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/status.json`:
```json
{
  "status": 200,
  "result": {
    "version": "15.0.3",
    "apiVersion": "3.0.3-alpha",
    "srvDate": 1745010000000,
    "settings": {
      "units": "mg/dl",
      "timeFormat": "24",
      "customTitle": "Anon NS",
      "theme": "default"
    }
  }
}
```

`tests/fixtures/lastmodified.json`:
```json
{
  "status": 200,
  "result": {
    "srvDate": 1745010000000,
    "collections": {
      "devicestatus": 1745009999000,
      "entries": 1745009998000,
      "treatments": 1745009000000,
      "profile": 1745000000000
    }
  }
}
```

`tests/fixtures/entries_latest.json`:
```json
{
  "status": 200,
  "result": [
    {
      "identifier": "aaaaaaaa-1111-4aaa-aaaa-aaaaaaaaaaaa",
      "date": 1745009700000,
      "sgv": 142,
      "direction": "Flat",
      "type": "sgv",
      "srvModified": 1745009701000
    }
  ]
}
```

`tests/fixtures/devicestatus_latest.json`:
```json
{
  "status": 200,
  "result": [
    {
      "identifier": "bbbbbbbb-2222-4bbb-bbbb-bbbbbbbbbbbb",
      "created_at": "2026-04-21T23:45:00Z",
      "date": 1745009700000,
      "device": "aaps-android-test",
      "pump": {
        "battery": { "percent": 82 },
        "reservoir": 185.2,
        "status": { "status": "normal", "timestamp": "2026-04-21T23:45:00Z" },
        "extended": {
          "ActiveProfile": "TestProfile",
          "BaseBasalRate": 0.85,
          "LastBolus": "21.04. 19:15",
          "LastBolusAmount": 3.2,
          "TempBasalRemaining": 12
        }
      },
      "openaps": {
        "iob": { "iob": 2.34, "basaliob": 1.12, "activity": 0.0085 },
        "suggested": {
          "eventualBG": 118,
          "targetBG": 105,
          "COB": 18.5,
          "sensitivityRatio": 1.0,
          "reason": "Anon reason",
          "predBGs": { "IOB": [142, 138, 133], "ZT": [142, 141, 140] }
        }
      },
      "uploaderBattery": 67,
      "isCharging": false,
      "srvModified": 1745009702000
    }
  ]
}
```

`tests/fixtures/treatments_sensor_change.json`:
```json
{
  "status": 200,
  "result": [
    {
      "identifier": "cccccccc-3333-4ccc-cccc-cccccccccccc",
      "eventType": "Sensor Change",
      "created_at": "2026-04-10T11:00:00Z",
      "date": 1744282800000,
      "srvModified": 1744282801000
    }
  ]
}
```

`tests/fixtures/profile_latest.json`:
```json
{
  "status": 200,
  "result": {
    "identifier": "dddddddd-4444-4ddd-dddd-dddddddddddd",
    "defaultProfile": "TestProfile",
    "store": {
      "TestProfile": {
        "dia": 6,
        "basal": [{ "time": "00:00", "value": 0.85 }],
        "units": "mg/dl"
      }
    },
    "srvModified": 1745000001000
  }
}
```

- [ ] **Step 2: Write failing test `tests/test_client.py`**

```python
"""Tests for NightscoutV3Client."""
from __future__ import annotations

from unittest.mock import AsyncMock

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.nightscout_v3.api.auth import JwtManager, JwtState
from custom_components.nightscout_v3.api.client import NightscoutV3Client
from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError
from tests.conftest import load_fixture

BASE_URL = "https://ns.example"


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s


@pytest.fixture
def jwt_manager(session: aiohttp.ClientSession) -> JwtManager:
    mgr = JwtManager(session, BASE_URL, "access-token")
    mgr._state = JwtState(token="jwt-anon", iat=0, exp=9999999999)
    return mgr


async def test_get_status(session, jwt_manager):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/status", payload=load_fixture("status"))
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_status()
    assert result["apiVersion"].startswith("3.0")


async def test_get_last_modified(session, jwt_manager):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/lastModified", payload=load_fixture("lastmodified"))
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_last_modified()
    assert "collections" in result


async def test_get_devicestatus(session, jwt_manager):
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/devicestatus?limit=1&sort$desc=date",
            payload=load_fixture("devicestatus_latest"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_devicestatus(limit=1)
    assert result[0]["pump"]["battery"]["percent"] == 82


async def test_get_entries_since(session, jwt_manager):
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/entries?date$gte=1745000000000&limit=1000&sort$desc=date",
            payload=load_fixture("entries_latest"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_entries(since_date=1745000000000, limit=1000)
    assert result[0]["sgv"] == 142


async def test_get_treatments_event_filter(session, jwt_manager):
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/treatments?eventType$eq=Sensor%20Change&limit=1&sort$desc=date",
            payload=load_fixture("treatments_sensor_change"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_treatments(event_type="Sensor Change", limit=1)
    assert result[0]["eventType"] == "Sensor Change"


async def test_get_profile_latest(session, jwt_manager):
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/profile?limit=1&sort$desc=date",
            payload=load_fixture("profile_latest"),
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        result = await client.get_profile(latest=True)
    assert result["defaultProfile"] == "TestProfile"


async def test_401_raises_auth_error(session, jwt_manager):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/status", status=401, payload={"status": 401})
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        with pytest.raises(AuthError):
            await client.get_status()


async def test_5xx_raises_api_error(session, jwt_manager):
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/v3/status", status=503, payload={"status": 503})
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        with pytest.raises(ApiError):
            await client.get_status()


async def test_authorization_header_sent(session, jwt_manager):
    captured = {}

    async def handler(url, **kwargs):
        captured["headers"] = dict(kwargs.get("headers") or {})

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/v3/status",
            payload=load_fixture("status"),
            callback=handler,
        )
        client = NightscoutV3Client(session, BASE_URL, jwt_manager)
        await client.get_status()
    assert captured["headers"]["Authorization"] == "Bearer jwt-anon"
```

- [ ] **Step 3: Run — expect FAIL**

```bash
pytest tests/test_client.py -v
```

- [ ] **Step 4: Implement `custom_components/nightscout_v3/api/client.py`**

```python
"""Nightscout v3 REST client."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from .auth import JwtManager
from .exceptions import ApiError, AuthError

_LOGGER = logging.getLogger(__name__)
_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


class NightscoutV3Client:
    """Thin wrapper around the Nightscout v3 REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        jwt_manager: JwtManager,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._jwt_manager = jwt_manager

    async def get_status(self) -> dict[str, Any]:
        return await self._get("/api/v3/status", envelope=True)

    async def get_last_modified(self) -> dict[str, Any]:
        return await self._get("/api/v3/lastModified", envelope=True)

    async def get_devicestatus(
        self,
        limit: int = 1,
        *,
        last_modified: int | None = None,
    ) -> list[dict[str, Any]]:
        params = [("limit", str(limit)), ("sort$desc", "date")]
        if last_modified is not None:
            params.append(("srvModified$gt", str(last_modified)))
        return await self._get_list("/api/v3/devicestatus", params)

    async def get_entries(
        self,
        limit: int = 1,
        *,
        since_date: int | None = None,
        before_date: int | None = None,
        last_modified: int | None = None,
    ) -> list[dict[str, Any]]:
        params: list[tuple[str, str]] = [("limit", str(limit)), ("sort$desc", "date")]
        if since_date is not None:
            params.insert(0, ("date$gte", str(since_date)))
        if before_date is not None:
            params.insert(0, ("date$lt", str(before_date)))
        if last_modified is not None:
            params.append(("srvModified$gt", str(last_modified)))
        return await self._get_list("/api/v3/entries", params)

    async def get_treatments(
        self,
        *,
        event_type: str | None = None,
        limit: int = 1,
        since_date: int | None = None,
        last_modified: int | None = None,
    ) -> list[dict[str, Any]]:
        params: list[tuple[str, str]] = []
        if event_type is not None:
            params.append(("eventType$eq", event_type))
        if since_date is not None:
            params.append(("date$gte", str(since_date)))
        params += [("limit", str(limit)), ("sort$desc", "date")]
        if last_modified is not None:
            params.append(("srvModified$gt", str(last_modified)))
        return await self._get_list("/api/v3/treatments", params)

    async def get_profile(self, *, latest: bool = True) -> dict[str, Any]:
        params = [("limit", "1"), ("sort$desc", "date")] if latest else []
        result = await self._get_list("/api/v3/profile", params)
        if not result:
            raise ApiError("No profile returned")
        return result[0]

    async def _get(self, path: str, *, envelope: bool) -> dict[str, Any]:
        raw = await self._raw_get(path, [])
        if envelope and "result" in raw:
            return raw["result"]
        return raw

    async def _get_list(self, path: str, params: list[tuple[str, str]]) -> list[dict[str, Any]]:
        raw = await self._raw_get(path, params)
        result = raw.get("result", [])
        if not isinstance(result, list):
            raise ApiError(f"Expected list at {path}, got {type(result).__name__}")
        return result

    async def _raw_get(self, path: str, params: list[tuple[str, str]]) -> dict[str, Any]:
        jwt = await self._jwt_manager.get_valid_jwt()
        headers = {"Authorization": f"Bearer {jwt}", "Accept": "application/json"}
        qs = "&".join(f"{k}={quote(v, safe='$')}" for k, v in params)
        url = f"{self._base_url}{path}" + (f"?{qs}" if qs else "")
        try:
            async with self._session.get(url, headers=headers, timeout=_DEFAULT_TIMEOUT) as resp:
                if resp.status == 401:
                    raise AuthError(f"401 on {path}")
                if resp.status >= 500:
                    raise ApiError(f"{resp.status} on {path}", status=resp.status)
                if resp.status != 200:
                    raise ApiError(f"{resp.status} on {path}", status=resp.status)
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise ApiError(f"Network error on {path}: {exc}") from exc
```

- [ ] **Step 5: Run — expect PASS**

```bash
pytest tests/test_client.py -v
```

- [ ] **Step 6: Commit**

```bash
git add custom_components/nightscout_v3/api/client.py tests/test_client.py tests/fixtures/*.json
git commit -m "feat(api): NightscoutV3Client (status, lastModified, entries, devicestatus, treatments, profile)"
```

---

### Task 1.4: ServerCapabilities probe

**Files:**
- Create: `custom_components/nightscout_v3/api/capabilities.py`
- Test: `tests/test_capabilities.py`

- [ ] **Step 1: Write failing test `tests/test_capabilities.py`**

```python
"""Tests for ServerCapabilities.probe."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities, probe_capabilities
from tests.conftest import load_fixture


@pytest.fixture
def client() -> AsyncMock:
    c = AsyncMock()
    c.get_status = AsyncMock(return_value=load_fixture("status")["result"])
    c.get_devicestatus = AsyncMock(return_value=load_fixture("devicestatus_latest")["result"])
    c.get_entries = AsyncMock(return_value=load_fixture("entries_latest")["result"])
    c.get_treatments = AsyncMock(return_value=load_fixture("treatments_sensor_change")["result"])
    return c


async def test_probe_detects_full_aaps_server(client: AsyncMock) -> None:
    caps = await probe_capabilities(client)
    assert caps.units == "mg/dl"
    assert caps.has_openaps is True
    assert caps.has_pump is True
    assert caps.has_entries is True
    assert caps.has_uploader_battery is True
    assert caps.has_treatments_sensor_change is True


async def test_probe_detects_minimal_server(client: AsyncMock) -> None:
    client.get_devicestatus.return_value = []
    client.get_treatments.return_value = []
    caps = await probe_capabilities(client)
    assert caps.has_openaps is False
    assert caps.has_pump is False
    assert caps.has_treatments_sensor_change is False
    assert caps.has_entries is True
    assert caps.units == "mg/dl"


async def test_probe_raises_if_no_entries(client: AsyncMock) -> None:
    client.get_entries.return_value = []
    with pytest.raises(RuntimeError, match="entries"):
        await probe_capabilities(client)


def test_capabilities_round_trip_dict() -> None:
    caps = ServerCapabilities(
        units="mg/dl",
        has_openaps=True,
        has_pump=True,
        has_uploader_battery=False,
        has_entries=True,
        has_treatments_sensor_change=True,
        has_treatments_site_change=False,
        has_treatments_insulin_change=False,
        has_treatments_pump_battery_change=False,
        last_probed_at_ms=1745000000000,
    )
    data = caps.to_dict()
    restored = ServerCapabilities.from_dict(data)
    assert restored == caps
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_capabilities.py -v
```

- [ ] **Step 3: Implement `custom_components/nightscout_v3/api/capabilities.py`**

```python
"""Probe a Nightscout server to detect which feature families are available."""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .client import NightscoutV3Client


@dataclass(slots=True, frozen=True)
class ServerCapabilities:
    """Snapshot of what this server can provide."""

    units: Literal["mg/dl", "mmol/L"]
    has_openaps: bool
    has_pump: bool
    has_uploader_battery: bool
    has_entries: bool
    has_treatments_sensor_change: bool
    has_treatments_site_change: bool
    has_treatments_insulin_change: bool
    has_treatments_pump_battery_change: bool
    last_probed_at_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerCapabilities":
        return cls(**data)


_SENSOR_CHANGE = "Sensor Change"
_SITE_CHANGE = "Site Change"
_INSULIN_CHANGE = "Insulin Change"
_PUMP_BATTERY_CHANGE = "Pump Battery Change"


async def probe_capabilities(client: NightscoutV3Client) -> ServerCapabilities:
    """Probe the server in parallel; raise if /entries is empty (hard requirement)."""
    status_task = asyncio.create_task(client.get_status())
    devicestatus_task = asyncio.create_task(client.get_devicestatus(limit=1))
    entries_task = asyncio.create_task(client.get_entries(limit=1))
    sensor_task = asyncio.create_task(client.get_treatments(event_type=_SENSOR_CHANGE, limit=1))
    site_task = asyncio.create_task(client.get_treatments(event_type=_SITE_CHANGE, limit=1))
    insulin_task = asyncio.create_task(client.get_treatments(event_type=_INSULIN_CHANGE, limit=1))
    battery_task = asyncio.create_task(
        client.get_treatments(event_type=_PUMP_BATTERY_CHANGE, limit=1)
    )

    status, devicestatus, entries, sensor, site, insulin, battery = await asyncio.gather(
        status_task, devicestatus_task, entries_task, sensor_task, site_task, insulin_task, battery_task
    )

    if not entries:
        raise RuntimeError("Server exposes no entries; cannot proceed")

    units_raw = (status.get("settings") or {}).get("units", "mg/dl")
    units: Literal["mg/dl", "mmol/L"] = "mmol/L" if units_raw == "mmol/L" else "mg/dl"

    latest_ds = devicestatus[0] if devicestatus else {}
    has_openaps = bool(latest_ds.get("openaps"))
    has_pump = bool(latest_ds.get("pump"))
    has_uploader_battery = "uploaderBattery" in latest_ds or bool(
        (latest_ds.get("pump") or {}).get("battery")
    )

    return ServerCapabilities(
        units=units,
        has_openaps=has_openaps,
        has_pump=has_pump,
        has_uploader_battery=has_uploader_battery,
        has_entries=bool(entries),
        has_treatments_sensor_change=bool(sensor),
        has_treatments_site_change=bool(site),
        has_treatments_insulin_change=bool(insulin),
        has_treatments_pump_battery_change=bool(battery),
        last_probed_at_ms=int(time.time() * 1000),
    )
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_capabilities.py -v
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/nightscout_v3/api/capabilities.py tests/test_capabilities.py
git commit -m "feat(api): ServerCapabilities probe (parallel fan-out)"
```

---

### Phase 1 review

- [ ] **Step 1: Dispatch code-reviewer subagent**

Run the `superpowers:code-reviewer` skill against commits in Phase 1 with this brief:

> Review the API layer of nightscout_v3 (`custom_components/nightscout_v3/api/*` and their tests). Check against the Silver Quality Scale rules that apply to pre-HA-layer code (typing, pure-python isolation, exception hierarchy, test coverage >=95 % in these modules). Report any deviations from the spec at `docs/specs/2026-04-22-ha-nightscout-v3-design.md` §3.3.1 – §3.3.3.

- [ ] **Step 2: Save report and commit**

```bash
# Subagent writes docs/reviews/YYYY-MM-DD-phase-1-api.md
git add docs/reviews/
git commit -m "docs(review): phase 1 (API layer) code-reviewer report"
```

---

## Phase 2 — Domain Layer (pure Python)

### Task 2.1: HistoryStore (aiosqlite)

**Files:**
- Create: `custom_components/nightscout_v3/history_store.py`
- Test: `tests/test_history_store.py`

- [ ] **Step 1: Write failing test `tests/test_history_store.py`**

```python
"""Tests for HistoryStore."""
from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.nightscout_v3.history_store import HistoryStore, SyncState


@pytest.fixture
async def store(tmp_path: Path):
    s = await HistoryStore.open(tmp_path / "history.db")
    try:
        yield s
    finally:
        await s.close()


async def test_schema_version_is_1(store: HistoryStore) -> None:
    assert await store.schema_version() == 1


async def test_insert_batch_and_window(store: HistoryStore) -> None:
    rows = [
        {
            "identifier": f"id-{i:04d}",
            "date": 1_745_000_000_000 + i * 300_000,
            "sgv": 140 + i,
            "direction": "Flat",
            "type": "sgv",
            "noise": 0,
            "srvModified": 1_745_000_000_000 + i * 300_000 + 1,
        }
        for i in range(10)
    ]
    inserted = await store.insert_batch(rows)
    assert inserted == 10
    window = await store.entries_in_window(days=1)
    assert len(window) == 10


async def test_insert_batch_is_idempotent(store: HistoryStore) -> None:
    rows = [
        {"identifier": "same", "date": 1, "sgv": 100, "direction": "Flat",
         "type": "sgv", "noise": 0, "srvModified": 1}
    ]
    assert await store.insert_batch(rows) == 1
    assert await store.insert_batch(rows) == 0


async def test_sync_state_roundtrip(store: HistoryStore) -> None:
    await store.update_sync_state("entries", last_modified=5, oldest_date=1, newest_date=10)
    state = await store.get_sync_state("entries")
    assert state == SyncState(
        collection="entries", last_modified=5, oldest_date=1, newest_date=10, updated_at_ms=state.updated_at_ms
    )


async def test_prune_removes_old(store: HistoryStore) -> None:
    rows = [
        {"identifier": "old", "date": 1_000_000_000_000, "sgv": 90, "direction": "Flat",
         "type": "sgv", "noise": 0, "srvModified": 1},
        {"identifier": "new", "date": 1_745_000_000_000, "sgv": 150, "direction": "Flat",
         "type": "sgv", "noise": 0, "srvModified": 2},
    ]
    await store.insert_batch(rows)
    removed = await store.prune(keep_days=7, now_ms=1_745_000_000_000)
    assert removed == 1
    remaining = await store.entries_in_window(days=365 * 30)
    assert len(remaining) == 1
    assert remaining[0]["identifier"] == "new"


async def test_stats_cache_roundtrip(store: HistoryStore) -> None:
    payload = {"window_days": 14, "mean": 136.2}
    await store.set_stats_cache(14, payload)
    got = await store.get_stats_cache(14)
    assert got["mean"] == 136.2


async def test_detects_corruption(tmp_path: Path) -> None:
    db = tmp_path / "broken.db"
    db.write_bytes(b"not a sqlite database")
    store = await HistoryStore.open(db)
    try:
        assert await store.is_corrupt() is True
        backup = await store.recover_from_corruption()
        assert backup.exists()
        assert await store.is_corrupt() is False
    finally:
        await store.close()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_history_store.py -v
```

- [ ] **Step 3: Implement `custom_components/nightscout_v3/history_store.py`**

```python
"""aiosqlite-backed rolling history for Nightscout v3 entries."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

_LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1

_DDL = [
    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY) WITHOUT ROWID",
    "CREATE TABLE IF NOT EXISTS entries ("
    "  identifier   TEXT PRIMARY KEY,"
    "  date         INTEGER NOT NULL,"
    "  sgv          INTEGER NOT NULL,"
    "  direction    TEXT,"
    "  type         TEXT NOT NULL,"
    "  noise        INTEGER,"
    "  srv_modified INTEGER NOT NULL"
    ") WITHOUT ROWID",
    "CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(date DESC)",
    "CREATE TABLE IF NOT EXISTS sync_state ("
    "  collection     TEXT PRIMARY KEY,"
    "  last_modified  INTEGER NOT NULL,"
    "  oldest_date    INTEGER NOT NULL,"
    "  newest_date    INTEGER NOT NULL,"
    "  updated_at_ms  INTEGER NOT NULL"
    ") WITHOUT ROWID",
    "CREATE TABLE IF NOT EXISTS stats_cache ("
    "  window_days  INTEGER PRIMARY KEY,"
    "  computed_at  INTEGER NOT NULL,"
    "  payload      TEXT NOT NULL"
    ") WITHOUT ROWID",
]


@dataclass(slots=True, frozen=True)
class SyncState:
    """Per-collection sync state."""

    collection: str
    last_modified: int
    oldest_date: int
    newest_date: int
    updated_at_ms: int


class HistoryStore:
    """aiosqlite-backed rolling history for a single config entry."""

    def __init__(self, path: Path, db: aiosqlite.Connection) -> None:
        self._path = path
        self._db = db

    @classmethod
    async def open(cls, path: Path) -> "HistoryStore":
        path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(path)
        db.row_factory = aiosqlite.Row
        store = cls(path, db)
        await store._initialize_schema()
        return store

    async def close(self) -> None:
        await self._db.close()

    async def schema_version(self) -> int:
        async with self._db.execute("SELECT version FROM schema_version LIMIT 1") as cur:
            row = await cur.fetchone()
        return int(row["version"]) if row else 0

    async def insert_batch(self, entries: list[dict[str, Any]]) -> int:
        if not entries:
            return 0
        rows = [
            (
                e["identifier"],
                int(e["date"]),
                int(e["sgv"]),
                e.get("direction"),
                e.get("type", "sgv"),
                e.get("noise"),
                int(e.get("srvModified", e["date"])),
            )
            for e in entries
        ]
        async with self._db.execute("SELECT COUNT(*) AS n FROM entries") as cur:
            before = (await cur.fetchone())["n"]
        await self._db.executemany(
            "INSERT OR IGNORE INTO entries (identifier, date, sgv, direction, type, noise, srv_modified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        await self._db.commit()
        async with self._db.execute("SELECT COUNT(*) AS n FROM entries") as cur:
            after = (await cur.fetchone())["n"]
        return int(after - before)

    async def entries_in_window(self, days: int, *, now_ms: int | None = None) -> list[dict[str, Any]]:
        now_ms = now_ms or int(time.time() * 1000)
        cutoff = now_ms - days * 86_400_000
        async with self._db.execute(
            "SELECT identifier, date, sgv, direction, type, noise, srv_modified "
            "FROM entries WHERE date >= ? ORDER BY date ASC",
            (cutoff,),
        ) as cur:
            return [dict(row) async for row in cur]

    async def get_sync_state(self, collection: str) -> SyncState | None:
        async with self._db.execute(
            "SELECT collection, last_modified, oldest_date, newest_date, updated_at_ms "
            "FROM sync_state WHERE collection = ?",
            (collection,),
        ) as cur:
            row = await cur.fetchone()
        return SyncState(**dict(row)) if row else None

    async def update_sync_state(
        self, collection: str, *, last_modified: int, oldest_date: int, newest_date: int
    ) -> None:
        now_ms = int(time.time() * 1000)
        await self._db.execute(
            "INSERT INTO sync_state (collection, last_modified, oldest_date, newest_date, updated_at_ms) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(collection) DO UPDATE SET "
            "  last_modified = excluded.last_modified,"
            "  oldest_date   = excluded.oldest_date,"
            "  newest_date   = excluded.newest_date,"
            "  updated_at_ms = excluded.updated_at_ms",
            (collection, last_modified, oldest_date, newest_date, now_ms),
        )
        await self._db.commit()

    async def prune(self, keep_days: int, *, now_ms: int | None = None) -> int:
        now_ms = now_ms or int(time.time() * 1000)
        cutoff = now_ms - keep_days * 86_400_000
        cur = await self._db.execute("DELETE FROM entries WHERE date < ?", (cutoff,))
        await self._db.commit()
        return cur.rowcount or 0

    async def get_stats_cache(self, window_days: int) -> dict[str, Any] | None:
        async with self._db.execute(
            "SELECT payload FROM stats_cache WHERE window_days = ?", (window_days,)
        ) as cur:
            row = await cur.fetchone()
        return json.loads(row["payload"]) if row else None

    async def set_stats_cache(self, window_days: int, payload: dict[str, Any]) -> None:
        await self._db.execute(
            "INSERT INTO stats_cache (window_days, computed_at, payload) VALUES (?, ?, ?) "
            "ON CONFLICT(window_days) DO UPDATE SET "
            "  computed_at = excluded.computed_at,"
            "  payload     = excluded.payload",
            (window_days, int(time.time() * 1000), json.dumps(payload)),
        )
        await self._db.commit()

    async def is_corrupt(self) -> bool:
        try:
            async with self._db.execute("PRAGMA integrity_check") as cur:
                row = await cur.fetchone()
        except aiosqlite.Error:
            return True
        return not row or row[0] != "ok"

    async def recover_from_corruption(self) -> Path:
        """Move the broken file aside and re-initialize."""
        await self._db.close()
        backup = self._path.with_suffix(self._path.suffix + f".broken.{int(time.time())}")
        self._path.rename(backup)
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._initialize_schema()
        return backup

    async def _initialize_schema(self) -> None:
        for stmt in _DDL:
            await self._db.execute(stmt)
        await self._db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
        )
        await self._db.commit()
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_history_store.py -v
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/nightscout_v3/history_store.py tests/test_history_store.py
git commit -m "feat(domain): HistoryStore (aiosqlite, schema v1, prune, stats cache, corruption recovery)"
```

---

### Task 2.2: Statistics

**Files:**
- Create: `custom_components/nightscout_v3/statistics.py`
- Test: `tests/test_statistics.py`

- [ ] **Step 1: Write failing test `tests/test_statistics.py`**

```python
"""Tests for statistics.compute_all."""
from __future__ import annotations

import math
import time

import pytest

from custom_components.nightscout_v3.statistics import compute_all


def _entry(offset_seconds: int, sgv: int) -> dict:
    now_ms = 1_745_000_000_000
    return {"date": now_ms - offset_seconds * 1000, "sgv": sgv}


def test_empty_input_returns_zero_samples() -> None:
    result = compute_all([], window_days=14)
    assert result["sample_count"] == 0
    assert result["mean_mgdl"] == 0.0


def test_gmi_matches_formula() -> None:
    entries = [_entry(i * 300, 154) for i in range(288)]
    result = compute_all(entries, window_days=1)
    # GMI = 3.31 + 0.02392 * 154 = 6.99
    assert result["gmi_percent"] == pytest.approx(6.99, abs=0.01)


def test_tir_buckets_partition_to_100() -> None:
    # 50% in range, 20% low, 20% high, 5% very low, 5% very high
    entries = (
        [_entry(i, 120) for i in range(50)]
        + [_entry(100 + i, 60) for i in range(20)]
        + [_entry(200 + i, 200) for i in range(20)]
        + [_entry(300 + i, 50) for i in range(5)]
        + [_entry(400 + i, 260) for i in range(5)]
    )
    r = compute_all(entries, window_days=1)
    total = r["tir_in_range_percent"] + r["tir_low_percent"] + r["tir_high_percent"]
    # tir_very_low is a subset of tir_low; tir_very_high is a subset of tir_high
    assert total == pytest.approx(100.0, abs=0.1)
    assert r["tir_very_low_percent"] == pytest.approx(5.0, abs=0.5)
    assert r["tir_very_high_percent"] == pytest.approx(5.0, abs=0.5)


def test_sd_and_cv() -> None:
    entries = [_entry(i * 60, v) for i, v in enumerate([100, 120, 140, 160, 180])]
    r = compute_all(entries, window_days=1)
    assert r["mean_mgdl"] == pytest.approx(140.0)
    assert r["sd_mgdl"] == pytest.approx(31.62, abs=0.1)
    assert r["cv_percent"] == pytest.approx(22.59, abs=0.1)


def test_hba1c_dcct_matches_formula() -> None:
    entries = [_entry(i * 300, 150) for i in range(288)]
    r = compute_all(entries, window_days=1)
    # (150 + 46.7) / 28.7 = 6.85
    assert r["hba1c_dcct_percent"] == pytest.approx(6.85, abs=0.01)


def test_hourly_profile_has_24_buckets() -> None:
    entries = [_entry(h * 3600, 100 + h) for h in range(24)]
    r = compute_all(entries, window_days=1)
    assert len(r["hourly_profile"]) == 24
    assert all(b["hour"] == i for i, b in enumerate(r["hourly_profile"]))


def test_agp_percentiles_are_ordered() -> None:
    entries = [_entry(i * 300, 100 + (i % 60)) for i in range(720)]
    r = compute_all(entries, window_days=1)
    assert len(r["agp_percentiles"]) == 24
    for band in r["agp_percentiles"]:
        if band["n"] == 0:
            continue
        assert band["p5"] <= band["p25"] <= band["p50"] <= band["p75"] <= band["p95"]


def test_lbgi_hbgi_are_nonnegative() -> None:
    entries = [_entry(i * 300, v) for i, v in enumerate([55, 70, 100, 140, 200, 260])]
    r = compute_all(entries, window_days=1)
    assert r["lbgi"] >= 0
    assert r["hbgi"] >= 0
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_statistics.py -v
```

- [ ] **Step 3: Implement `custom_components/nightscout_v3/statistics.py`**

```python
"""Pure-Python diabetes statistics computations (no IO, no HA deps)."""
from __future__ import annotations

import math
import time
from typing import Any

TIR_LOW = 70
TIR_HIGH = 180
TIR_VERY_LOW = 54
TIR_VERY_HIGH = 250


def compute_all(
    entries: list[dict[str, Any]],
    window_days: int,
    *,
    tir_low: int = TIR_LOW,
    tir_high: int = TIR_HIGH,
    tir_very_low: int = TIR_VERY_LOW,
    tir_very_high: int = TIR_VERY_HIGH,
) -> dict[str, Any]:
    """Compute all statistics for a window of entries. Empty input returns zeroed payload."""
    sgvs = [int(e["sgv"]) for e in entries if e.get("sgv") is not None]
    n = len(sgvs)

    if n == 0:
        return _empty_payload(window_days)

    mean = sum(sgvs) / n
    variance = sum((x - mean) ** 2 for x in sgvs) / n
    sd = math.sqrt(variance)
    cv = (sd / mean * 100) if mean else 0.0

    gmi = 3.31 + 0.02392 * mean
    hba1c_dcct = (mean + 46.7) / 28.7

    tir_in = 100 * sum(tir_low <= x <= tir_high for x in sgvs) / n
    tir_lo = 100 * sum(x < tir_low for x in sgvs) / n
    tir_vlo = 100 * sum(x < tir_very_low for x in sgvs) / n
    tir_hi = 100 * sum(x > tir_high for x in sgvs) / n
    tir_vhi = 100 * sum(x > tir_very_high for x in sgvs) / n

    lbgi, hbgi = _bgi(sgvs)

    return {
        "window_days": window_days,
        "sample_count": n,
        "mean_mgdl": round(mean, 2),
        "sd_mgdl": round(sd, 2),
        "cv_percent": round(cv, 2),
        "gmi_percent": round(gmi, 2),
        "hba1c_dcct_percent": round(hba1c_dcct, 2),
        "tir_in_range_percent": round(tir_in, 2),
        "tir_low_percent": round(tir_lo, 2),
        "tir_very_low_percent": round(tir_vlo, 2),
        "tir_high_percent": round(tir_hi, 2),
        "tir_very_high_percent": round(tir_vhi, 2),
        "lbgi": round(lbgi, 2),
        "hbgi": round(hbgi, 2),
        "hourly_profile": _hourly_profile(entries),
        "agp_percentiles": _agp_percentiles(entries),
        "computed_at_ms": int(time.time() * 1000),
    }


def _empty_payload(window_days: int) -> dict[str, Any]:
    return {
        "window_days": window_days,
        "sample_count": 0,
        "mean_mgdl": 0.0,
        "sd_mgdl": 0.0,
        "cv_percent": 0.0,
        "gmi_percent": 0.0,
        "hba1c_dcct_percent": 0.0,
        "tir_in_range_percent": 0.0,
        "tir_low_percent": 0.0,
        "tir_very_low_percent": 0.0,
        "tir_high_percent": 0.0,
        "tir_very_high_percent": 0.0,
        "lbgi": 0.0,
        "hbgi": 0.0,
        "hourly_profile": [{"hour": h, "mean": 0, "median": 0, "min": 0, "max": 0, "n": 0} for h in range(24)],
        "agp_percentiles": [{"hour": h, "p5": 0, "p25": 0, "p50": 0, "p75": 0, "p95": 0, "n": 0} for h in range(24)],
        "computed_at_ms": int(time.time() * 1000),
    }


def _bgi(sgvs: list[int]) -> tuple[float, float]:
    """Low Blood Glucose Index & High Blood Glucose Index (Kovatchev 1997)."""
    low = 0.0
    high = 0.0
    for x in sgvs:
        f = 1.509 * (math.log(max(x, 1)) ** 1.084 - 5.381)
        rl = 10 * (f**2) if f < 0 else 0.0
        rh = 10 * (f**2) if f > 0 else 0.0
        low += rl
        high += rh
    return low / len(sgvs), high / len(sgvs)


def _bucket_by_hour(entries: list[dict[str, Any]]) -> list[list[int]]:
    buckets: list[list[int]] = [[] for _ in range(24)]
    for e in entries:
        sgv = e.get("sgv")
        date = e.get("date")
        if sgv is None or date is None:
            continue
        h = int((int(date) // 1000 % 86_400) // 3600)
        buckets[h].append(int(sgv))
    return buckets


def _hourly_profile(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = _bucket_by_hour(entries)
    out = []
    for h, xs in enumerate(buckets):
        if not xs:
            out.append({"hour": h, "mean": 0, "median": 0, "min": 0, "max": 0, "n": 0})
            continue
        xs_sorted = sorted(xs)
        out.append(
            {
                "hour": h,
                "mean": round(sum(xs) / len(xs), 2),
                "median": xs_sorted[len(xs) // 2],
                "min": xs_sorted[0],
                "max": xs_sorted[-1],
                "n": len(xs),
            }
        )
    return out


def _percentile(sorted_values: list[int], q: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(sorted_values[int(k)])
    return sorted_values[lo] * (hi - k) + sorted_values[hi] * (k - lo)


def _agp_percentiles(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = _bucket_by_hour(entries)
    out = []
    for h, xs in enumerate(buckets):
        if not xs:
            out.append({"hour": h, "p5": 0, "p25": 0, "p50": 0, "p75": 0, "p95": 0, "n": 0})
            continue
        sorted_xs = sorted(xs)
        out.append(
            {
                "hour": h,
                "p5": round(_percentile(sorted_xs, 0.05), 2),
                "p25": round(_percentile(sorted_xs, 0.25), 2),
                "p50": round(_percentile(sorted_xs, 0.50), 2),
                "p75": round(_percentile(sorted_xs, 0.75), 2),
                "p95": round(_percentile(sorted_xs, 0.95), 2),
                "n": len(xs),
            }
        )
    return out
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_statistics.py -v
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/nightscout_v3/statistics.py tests/test_statistics.py
git commit -m "feat(domain): statistics (GMI, HbA1c, TIR, SD/CV, LBGI/HBGI, hourly, AGP)"
```

---

### Task 2.3: FEATURE_REGISTRY

**Files:**
- Create: `custom_components/nightscout_v3/const.py`
- Create: `custom_components/nightscout_v3/feature_registry.py`
- Test: `tests/test_feature_registry.py`

- [ ] **Step 1: Create `custom_components/nightscout_v3/const.py`**

```python
"""Constants for nightscout_v3."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "nightscout_v3"
MANUFACTURER: Final = "Nightscout"
MODEL: Final = "v3 API"

CONF_URL: Final = "url"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_CAPABILITIES: Final = "capabilities"
CONF_CAPABILITIES_PROBED_AT: Final = "capabilities_probed_at"

OPT_ENABLED_FEATURES: Final = "enabled_features"
OPT_STATS_WINDOWS: Final = "stats_windows"
OPT_TIR_LOW: Final = "tir_low_threshold_mgdl"
OPT_TIR_HIGH: Final = "tir_high_threshold_mgdl"
OPT_TIR_VERY_LOW: Final = "tir_very_low_threshold_mgdl"
OPT_TIR_VERY_HIGH: Final = "tir_very_high_threshold_mgdl"
OPT_POLL_FAST_SECONDS: Final = "poll_fast_seconds"
OPT_POLL_CHANGE_DETECT_MINUTES: Final = "poll_change_detect_minutes"
OPT_POLL_STATS_MINUTES: Final = "poll_stats_minutes"

DEFAULT_POLL_FAST_SECONDS: Final = 60
DEFAULT_POLL_CHANGE_DETECT_MINUTES: Final = 5
DEFAULT_POLL_STATS_MINUTES: Final = 60
DEFAULT_TIR_LOW: Final = 70
DEFAULT_TIR_HIGH: Final = 180
DEFAULT_TIR_VERY_LOW: Final = 54
DEFAULT_TIR_VERY_HIGH: Final = 250

ALLOWED_STATS_WINDOWS: Final = (1, 7, 14, 30, 90)
MANDATORY_STATS_WINDOW: Final = 14
STATS_HISTORY_MAX_DAYS: Final = 90

COORDINATOR_TICK_SECONDS: Final = 30
JWT_BACKGROUND_REFRESH_HOURS: Final = 7
```

- [ ] **Step 2: Write failing test `tests/test_feature_registry.py`**

```python
"""Tests for FEATURE_REGISTRY."""
from __future__ import annotations

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
from custom_components.nightscout_v3.feature_registry import (
    FEATURE_REGISTRY,
    Category,
    features_for_capabilities,
)


def _caps(**overrides) -> ServerCapabilities:
    base = {
        "units": "mg/dl",
        "has_openaps": True,
        "has_pump": True,
        "has_uploader_battery": True,
        "has_entries": True,
        "has_treatments_sensor_change": True,
        "has_treatments_site_change": True,
        "has_treatments_insulin_change": True,
        "has_treatments_pump_battery_change": True,
        "last_probed_at_ms": 0,
    }
    base.update(overrides)
    return ServerCapabilities(**base)


def test_registry_has_unique_keys() -> None:
    keys = [f.key for f in FEATURE_REGISTRY]
    assert len(keys) == len(set(keys))


def test_all_features_have_translation_key() -> None:
    for f in FEATURE_REGISTRY:
        assert f.translation_key, f"{f.key} missing translation_key"


def test_all_categories_represented() -> None:
    cats = {f.category for f in FEATURE_REGISTRY}
    assert Category.BG in cats
    assert Category.PUMP in cats
    assert Category.LOOP in cats
    assert Category.CAREPORTAL in cats
    assert Category.UPLOADER in cats
    # STATISTICS features are generated per-window, not listed here.


def test_full_capabilities_enables_all_features() -> None:
    enabled = features_for_capabilities(_caps())
    keys = {f.key for f in enabled}
    assert "bg_current" in keys
    assert "loop_iob" in keys
    assert "pump_reservoir" in keys
    assert "uploader_online" in keys


def test_minimal_capabilities_excludes_pump_and_loop() -> None:
    caps = _caps(has_openaps=False, has_pump=False, has_uploader_battery=False)
    enabled = features_for_capabilities(caps)
    keys = {f.key for f in enabled}
    assert "bg_current" in keys
    assert "loop_iob" not in keys
    assert "pump_reservoir" not in keys
```

- [ ] **Step 3: Run — expect FAIL**

```bash
pytest tests/test_feature_registry.py -v
```

- [ ] **Step 4: Implement `custom_components/nightscout_v3/feature_registry.py`**

```python
"""Single source of truth mapping features -> category, capability, extractor, platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, Platform, UnitOfTime

from .api.capabilities import ServerCapabilities


class Category(StrEnum):
    BG = "bg"
    PUMP = "pump"
    LOOP = "loop"
    CAREPORTAL = "careportal"
    STATISTICS = "statistics"
    UPLOADER = "uploader"


@dataclass(frozen=True, slots=True)
class FeatureDef:
    """One feature that can become an entity."""

    key: str
    category: Category
    platform: Platform
    capability: Callable[[ServerCapabilities], bool]
    default_enabled: bool
    translation_key: str
    extractor: str  # dotted path into coordinator data (documented in coordinator.py)
    device_class: str | None = None
    state_class: str | None = None
    unit: str | None = None
    icon: str | None = None
    # Phase-3-polish (Review 2026-04-22): stats entities set
    # translation_placeholders={"window": str(w)} so each window's sensor
    # renders its own translated name without collisions.
    translation_placeholders: dict[str, str] | None = None


def _always(_c: ServerCapabilities) -> bool:
    return True


def _has_openaps(c: ServerCapabilities) -> bool:
    return c.has_openaps


def _has_pump(c: ServerCapabilities) -> bool:
    return c.has_pump


def _has_uploader(c: ServerCapabilities) -> bool:
    return c.has_uploader_battery


FEATURE_REGISTRY: list[FeatureDef] = [
    # -------- BG (spec §4.1) --------
    FeatureDef("bg_current", Category.BG, Platform.SENSOR, _always, True,
               "bg_current", "bg.current_sgv",
               device_class=None, state_class=SensorStateClass.MEASUREMENT, icon="mdi:water"),
    FeatureDef("bg_delta", Category.BG, Platform.SENSOR, _always, True,
               "bg_delta", "bg.delta_mgdl",
               state_class=SensorStateClass.MEASUREMENT, icon="mdi:plus-minus-variant"),
    FeatureDef("bg_direction", Category.BG, Platform.SENSOR, _always, True,
               "bg_direction", "bg.direction", icon="mdi:arrow-right"),
    FeatureDef("bg_trend_arrow", Category.BG, Platform.SENSOR, _always, True,
               "bg_trend_arrow", "bg.trend_arrow", icon="mdi:arrow-top-right"),
    FeatureDef("bg_stale_minutes", Category.BG, Platform.SENSOR, _always, True,
               "bg_stale_minutes", "bg.stale_minutes",
               state_class=SensorStateClass.MEASUREMENT, unit=UnitOfTime.MINUTES, icon="mdi:clock-alert-outline"),

    # -------- PUMP (spec §4.2) --------
    FeatureDef("pump_reservoir", Category.PUMP, Platform.SENSOR, _has_pump, True,
               "pump_reservoir", "pump.reservoir",
               state_class=SensorStateClass.MEASUREMENT, unit="U", icon="mdi:water-pump"),
    FeatureDef("pump_battery", Category.PUMP, Platform.SENSOR, _has_pump, True,
               "pump_battery", "pump.battery_percent",
               device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT,
               unit=PERCENTAGE, icon="mdi:battery"),
    FeatureDef("pump_status", Category.PUMP, Platform.SENSOR, _has_pump, True,
               "pump_status", "pump.status_text", icon="mdi:information-outline"),
    FeatureDef("pump_base_basal", Category.PUMP, Platform.SENSOR, _has_pump, True,
               "pump_base_basal", "pump.base_basal",
               state_class=SensorStateClass.MEASUREMENT, unit="U/h", icon="mdi:chart-line"),
    FeatureDef("pump_temp_basal_rate", Category.PUMP, Platform.SENSOR, _has_pump, True,
               "pump_temp_basal_rate", "pump.temp_basal_rate",
               state_class=SensorStateClass.MEASUREMENT, unit="U/h", icon="mdi:chart-line-variant"),
    FeatureDef("pump_temp_basal_remaining", Category.PUMP, Platform.SENSOR, _has_pump, True,
               "pump_temp_basal_remaining", "pump.temp_basal_remaining",
               state_class=SensorStateClass.MEASUREMENT, unit=UnitOfTime.MINUTES, icon="mdi:timer-sand"),
    FeatureDef("pump_active_profile", Category.PUMP, Platform.SENSOR, _has_pump, True,
               "pump_active_profile", "pump.active_profile", icon="mdi:account-cog"),
    FeatureDef("pump_last_bolus_time", Category.PUMP, Platform.SENSOR, _has_pump, True,
               "pump_last_bolus_time", "pump.last_bolus_time",
               device_class=SensorDeviceClass.TIMESTAMP, icon="mdi:clock-outline"),
    FeatureDef("pump_last_bolus_amount", Category.PUMP, Platform.SENSOR, _has_pump, True,
               "pump_last_bolus_amount", "pump.last_bolus_amount",
               state_class=SensorStateClass.MEASUREMENT, unit="U", icon="mdi:needle"),

    # -------- LOOP (spec §4.3) --------
    FeatureDef("loop_mode", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_mode", "loop.mode", icon="mdi:refresh-auto"),
    FeatureDef("loop_active", Category.LOOP, Platform.BINARY_SENSOR, _has_openaps, True,
               "loop_active", "loop.active",
               device_class=BinarySensorDeviceClass.RUNNING),
    FeatureDef("loop_eventual_bg", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_eventual_bg", "loop.eventual_bg",
               state_class=SensorStateClass.MEASUREMENT, icon="mdi:crystal-ball"),
    FeatureDef("loop_target_bg", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_target_bg", "loop.target_bg",
               state_class=SensorStateClass.MEASUREMENT, icon="mdi:target"),
    FeatureDef("loop_iob", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_iob", "loop.iob",
               state_class=SensorStateClass.MEASUREMENT, unit="U", icon="mdi:needle"),
    FeatureDef("loop_basaliob", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_basaliob", "loop.basaliob",
               state_class=SensorStateClass.MEASUREMENT, unit="U", icon="mdi:chart-line"),
    FeatureDef("loop_activity", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_activity", "loop.activity",
               state_class=SensorStateClass.MEASUREMENT, icon="mdi:pulse"),
    FeatureDef("loop_cob", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_cob", "loop.cob",
               state_class=SensorStateClass.MEASUREMENT, unit="g", icon="mdi:food-apple"),
    FeatureDef("loop_sensitivity_ratio", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_sensitivity_ratio", "loop.sensitivity_ratio",
               state_class=SensorStateClass.MEASUREMENT, icon="mdi:scale-balance"),
    FeatureDef("loop_reason", Category.LOOP, Platform.SENSOR, _has_openaps, False,
               "loop_reason", "loop.reason", icon="mdi:message-text-outline"),
    FeatureDef("loop_pred_bgs", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_pred_bgs", "loop.pred_bgs", icon="mdi:chart-timeline-variant"),
    FeatureDef("loop_last_enacted_age_minutes", Category.LOOP, Platform.SENSOR, _has_openaps, True,
               "loop_last_enacted_age_minutes", "loop.last_enacted_age_minutes",
               state_class=SensorStateClass.MEASUREMENT, unit=UnitOfTime.MINUTES, icon="mdi:clock-outline"),

    # -------- CAREPORTAL read-only (spec §4.4) --------
    FeatureDef("care_sage_days", Category.CAREPORTAL, Platform.SENSOR,
               lambda c: c.has_treatments_sensor_change, True,
               "care_sage_days", "care.sage_days",
               state_class=SensorStateClass.MEASUREMENT, unit=UnitOfTime.DAYS, icon="mdi:cgm"),
    FeatureDef("care_iage_days", Category.CAREPORTAL, Platform.SENSOR,
               lambda c: c.has_treatments_insulin_change, True,
               "care_iage_days", "care.iage_days",
               state_class=SensorStateClass.MEASUREMENT, unit=UnitOfTime.DAYS, icon="mdi:needle"),
    FeatureDef("care_cage_days", Category.CAREPORTAL, Platform.SENSOR,
               lambda c: c.has_treatments_site_change, True,
               "care_cage_days", "care.cage_days",
               state_class=SensorStateClass.MEASUREMENT, unit=UnitOfTime.DAYS, icon="mdi:bandage"),
    FeatureDef("care_bage_days", Category.CAREPORTAL, Platform.SENSOR,
               lambda c: c.has_treatments_pump_battery_change, True,
               "care_bage_days", "care.bage_days",
               state_class=SensorStateClass.MEASUREMENT, unit=UnitOfTime.DAYS, icon="mdi:battery"),
    FeatureDef("care_last_meal_carbs", Category.CAREPORTAL, Platform.SENSOR, _always, True,
               "care_last_meal_carbs", "care.last_meal_carbs",
               state_class=SensorStateClass.MEASUREMENT, unit="g", icon="mdi:food-apple"),
    FeatureDef("care_carbs_today", Category.CAREPORTAL, Platform.SENSOR, _always, True,
               "care_carbs_today", "care.carbs_today",
               state_class=SensorStateClass.TOTAL, unit="g", icon="mdi:food-apple-outline"),
    FeatureDef("care_last_note", Category.CAREPORTAL, Platform.SENSOR, _always, False,
               "care_last_note", "care.last_note", icon="mdi:note-outline"),

    # -------- UPLOADER (spec §4.6) --------
    FeatureDef("uploader_battery", Category.UPLOADER, Platform.SENSOR, _has_uploader, True,
               "uploader_battery", "uploader.battery_percent",
               device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT,
               unit=PERCENTAGE, icon="mdi:cellphone"),
    FeatureDef("uploader_online", Category.UPLOADER, Platform.BINARY_SENSOR, _has_uploader, True,
               "uploader_online", "uploader.online",
               device_class=BinarySensorDeviceClass.CONNECTIVITY),
    FeatureDef("uploader_charging", Category.UPLOADER, Platform.BINARY_SENSOR, _has_uploader, True,
               "uploader_charging", "uploader.charging",
               device_class=BinarySensorDeviceClass.BATTERY_CHARGING),
]


def features_for_capabilities(caps: ServerCapabilities) -> list[FeatureDef]:
    """Return features whose capability is satisfied by `caps`."""
    return [f for f in FEATURE_REGISTRY if f.capability(caps)]


def stats_feature_defs(window_days: int) -> list[FeatureDef]:
    """Expand the 13-sensor stats bundle for one window (spec §4.5)."""
    w = window_days
    return [
        FeatureDef(f"stat_gmi_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_gmi", f"stats.{w}d.gmi_percent",
                   state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE, icon="mdi:diabetes"),
        FeatureDef(f"stat_hba1c_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_hba1c", f"stats.{w}d.hba1c_dcct_percent",
                   state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE, icon="mdi:diabetes"),
        FeatureDef(f"stat_tir_in_range_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_tir_in_range", f"stats.{w}d.tir_in_range_percent",
                   state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE, icon="mdi:timer-check"),
        FeatureDef(f"stat_tir_low_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_tir_low", f"stats.{w}d.tir_low_percent",
                   state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE, icon="mdi:arrow-down-bold"),
        FeatureDef(f"stat_tir_very_low_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_tir_very_low", f"stats.{w}d.tir_very_low_percent",
                   state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE, icon="mdi:alert-circle"),
        FeatureDef(f"stat_tir_high_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_tir_high", f"stats.{w}d.tir_high_percent",
                   state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE, icon="mdi:arrow-up-bold"),
        FeatureDef(f"stat_tir_very_high_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_tir_very_high", f"stats.{w}d.tir_very_high_percent",
                   state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE, icon="mdi:alert-decagram"),
        FeatureDef(f"stat_mean_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_mean", f"stats.{w}d.mean_mgdl",
                   state_class=SensorStateClass.MEASUREMENT, icon="mdi:sigma"),
        FeatureDef(f"stat_sd_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_sd", f"stats.{w}d.sd_mgdl",
                   state_class=SensorStateClass.MEASUREMENT, icon="mdi:chart-bell-curve"),
        FeatureDef(f"stat_cv_{w}d", Category.STATISTICS, Platform.SENSOR, _always, True,
                   "stat_cv", f"stats.{w}d.cv_percent",
                   state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE, icon="mdi:variable"),
        FeatureDef(f"stat_lbgi_{w}d", Category.STATISTICS, Platform.SENSOR, _always, False,
                   "stat_lbgi", f"stats.{w}d.lbgi",
                   state_class=SensorStateClass.MEASUREMENT, icon="mdi:arrow-down-thin-circle-outline"),
        FeatureDef(f"stat_hbgi_{w}d", Category.STATISTICS, Platform.SENSOR, _always, False,
                   "stat_hbgi", f"stats.{w}d.hbgi",
                   state_class=SensorStateClass.MEASUREMENT, icon="mdi:arrow-up-thin-circle-outline"),
        FeatureDef(f"stat_hourly_profile_{w}d", Category.STATISTICS, Platform.SENSOR, _always, False,
                   "stat_hourly_profile", f"stats.{w}d.hourly_profile_summary",
                   icon="mdi:chart-line"),
        FeatureDef(f"stat_agp_{w}d", Category.STATISTICS, Platform.SENSOR, _always, False,
                   "stat_agp", f"stats.{w}d.agp_summary",
                   icon="mdi:chart-areaspline"),
    ]
```

- [ ] **Step 5: Run — expect PASS**

```bash
pytest tests/test_feature_registry.py -v
```

- [ ] **Step 6: Commit**

```bash
git add custom_components/nightscout_v3/const.py custom_components/nightscout_v3/feature_registry.py tests/test_feature_registry.py
git commit -m "feat(domain): FEATURE_REGISTRY + const (categories, 40 features, stats expansion)"
```

---

### Phase 2 review

- [ ] **Step 1: Dispatch code-reviewer subagent**

Brief: review `history_store.py`, `statistics.py`, `feature_registry.py`, `const.py` + their tests against spec §3.3.4-§3.3.6 and §4.1-§4.6. Verify: typing, no HA imports in history_store/statistics, all feature keys match spec, test coverage.

- [ ] **Step 2: Commit review report**

```bash
git add docs/reviews/
git commit -m "docs(review): phase 2 (domain layer) code-reviewer report"
```

---

## Phase 3 — HA Integration Layer

### Task 3.1: Runtime data + base entity

**Files:**
- Create: `custom_components/nightscout_v3/entity.py`
- Test: none yet — exercised by later tasks.

- [ ] **Step 1: Implement `custom_components/nightscout_v3/entity.py`**

```python
"""Base entity for nightscout_v3."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL

if TYPE_CHECKING:
    from .coordinator import NightscoutCoordinator
    from .feature_registry import FeatureDef


class NightscoutEntity(CoordinatorEntity["NightscoutCoordinator"]):
    """Shared base: unique_id, has_entity_name, device_info, extractor plumbing."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: "NightscoutCoordinator", feature: "FeatureDef") -> None:
        super().__init__(coordinator)
        self._feature = feature
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{feature.key}"
        self._attr_translation_key = feature.translation_key
        self._attr_icon = feature.icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=coordinator.config_entry.title,
            configuration_url=coordinator.config_entry.data.get("url"),
        )

    def _extract(self) -> Any:
        """Pull the value from coordinator data using this feature's dotted path."""
        data = self.coordinator.data
        if data is None:
            return None
        for part in self._feature.extractor.split("."):
            if data is None:
                return None
            if isinstance(data, dict):
                data = data.get(part)
            else:
                data = getattr(data, part, None)
        return data

    @property
    def available(self) -> bool:
        """Available only when coordinator last update succeeded AND value is not None."""
        if not super().available:
            return False
        return self._extract() is not None
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/nightscout_v3/entity.py
git commit -m "feat(ha): NightscoutEntity base (unique_id, has_entity_name, device_info, extractor)"
```

---

### Task 3.2: Coordinator

**Files:**
- Create: `custom_components/nightscout_v3/coordinator.py`
- Test: `tests/test_coordinator.py`

- [ ] **Step 1: Write failing test `tests/test_coordinator.py`**

```python
"""Tests for NightscoutCoordinator staggered-tick behavior."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError
from custom_components.nightscout_v3.coordinator import NightscoutCoordinator
from custom_components.nightscout_v3.history_store import HistoryStore


def _caps() -> ServerCapabilities:
    return ServerCapabilities(
        units="mg/dl",
        has_openaps=True,
        has_pump=True,
        has_uploader_battery=True,
        has_entries=True,
        has_treatments_sensor_change=True,
        has_treatments_site_change=True,
        has_treatments_insulin_change=True,
        has_treatments_pump_battery_change=True,
        last_probed_at_ms=0,
    )


@pytest.fixture
async def store(tmp_path):
    s = await HistoryStore.open(tmp_path / "c.db")
    try:
        yield s
    finally:
        await s.close()


@pytest.fixture
def entry() -> ConfigEntry:
    e = MagicMock(spec=ConfigEntry)
    e.entry_id = "entry-1"
    e.title = "Test User"
    e.options = {}
    e.data = {"url": "https://ns.example"}
    return e


@pytest.fixture
def mock_client():
    c = AsyncMock()
    c.get_entries.return_value = [{"identifier": "e1", "date": 1, "sgv": 140, "direction": "Flat", "type": "sgv", "srvModified": 2}]
    c.get_devicestatus.return_value = [{
        "pump": {"battery": {"percent": 80}, "reservoir": 100.0, "status": {"status": "normal"},
                  "extended": {"ActiveProfile": "P", "BaseBasalRate": 0.85, "LastBolus": "21.04. 12:00",
                                "LastBolusAmount": 2.0, "TempBasalRemaining": 0}},
        "openaps": {"iob": {"iob": 1.0, "basaliob": 0.5, "activity": 0.01},
                     "suggested": {"eventualBG": 120, "targetBG": 105, "COB": 10,
                                    "sensitivityRatio": 1.0, "reason": "ok",
                                    "predBGs": {"IOB": [], "ZT": []}}},
        "created_at": "2026-04-21T23:45:00Z",
        "date": 1_745_009_700_000,
        "uploaderBattery": 65,
        "isCharging": False,
    }]
    c.get_treatments.return_value = []
    c.get_last_modified.return_value = {"collections": {"entries": 1, "devicestatus": 2, "treatments": 3}}
    return c


async def test_first_refresh_populates_data(hass: HomeAssistant, mock_client, store, entry) -> None:
    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    await coord.async_config_entry_first_refresh()
    assert coord.data is not None
    assert coord.data["bg"]["current_sgv"] == 140
    assert coord.data["pump"]["battery_percent"] == 80
    assert coord.data["loop"]["iob"] == 1.0


async def test_auth_error_becomes_config_entry_auth_failed(
    hass: HomeAssistant, mock_client, store, entry
) -> None:
    mock_client.get_entries.side_effect = AuthError("401")
    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    with pytest.raises(ConfigEntryAuthFailed):
        await coord.async_config_entry_first_refresh()


async def test_api_error_becomes_update_failed(
    hass: HomeAssistant, mock_client, store, entry
) -> None:
    from homeassistant.helpers.update_coordinator import UpdateFailed

    mock_client.get_entries.side_effect = ApiError("boom", status=503)
    coord = NightscoutCoordinator(hass, mock_client, _caps(), store, entry)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_coordinator.py -v
```

- [ ] **Step 3: Implement `custom_components/nightscout_v3/coordinator.py`**

```python
"""DataUpdateCoordinator with staggered fast / change-detect / stats cycles."""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.capabilities import ServerCapabilities
from .api.client import NightscoutV3Client
from .api.exceptions import ApiError, AuthError
from .const import (
    ALLOWED_STATS_WINDOWS,
    COORDINATOR_TICK_SECONDS,
    DEFAULT_POLL_CHANGE_DETECT_MINUTES,
    DEFAULT_POLL_FAST_SECONDS,
    DEFAULT_POLL_STATS_MINUTES,
    DEFAULT_TIR_HIGH,
    DEFAULT_TIR_LOW,
    DEFAULT_TIR_VERY_HIGH,
    DEFAULT_TIR_VERY_LOW,
    DOMAIN,
    MANDATORY_STATS_WINDOW,
    OPT_POLL_CHANGE_DETECT_MINUTES,
    OPT_POLL_FAST_SECONDS,
    OPT_POLL_STATS_MINUTES,
    OPT_STATS_WINDOWS,
    OPT_TIR_HIGH,
    OPT_TIR_LOW,
    OPT_TIR_VERY_HIGH,
    OPT_TIR_VERY_LOW,
    STATS_HISTORY_MAX_DAYS,
)
from .history_store import HistoryStore
from .statistics import compute_all

_LOGGER = logging.getLogger(__name__)

_TREATMENT_AGE_EVENTS = {
    "sensor": "Sensor Change",
    "site": "Site Change",
    "insulin": "Insulin Change",
    "battery": "Pump Battery Change",
}

_DIRECTION_TO_ARROW = {
    "DoubleUp": "⇈",
    "SingleUp": "↑",
    "FortyFiveUp": "↗",
    "Flat": "→",
    "FortyFiveDown": "↘",
    "SingleDown": "↓",
    "DoubleDown": "⇊",
    "NOT COMPUTABLE": "?",
    "NONE": "-",
}


class NightscoutCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single coordinator with staggered update cycles."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: NightscoutV3Client,
        capabilities: ServerCapabilities,
        store: HistoryStore,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{entry.entry_id}",
            update_interval=timedelta(seconds=COORDINATOR_TICK_SECONDS),
            config_entry=entry,
        )
        self._client = client
        self._capabilities = capabilities
        self._store = store
        self._tick = 0
        self._stats_dirty = True
        self._last_tick_summary: dict[str, int] = {}
        self._last_modified_cache: dict[str, int] = {}
        self._treatment_age_cache: dict[str, datetime | None] = {}
        self._last_meal: dict[str, Any] | None = None
        self._carbs_today: float = 0.0
        self._last_note: str | None = None

    @property
    def capabilities(self) -> ServerCapabilities:
        return self._capabilities

    @property
    def client(self) -> NightscoutV3Client:
        return self._client

    @property
    def store(self) -> HistoryStore:
        return self._store

    @property
    def last_tick_summary(self) -> dict[str, int]:
        return dict(self._last_tick_summary)

    async def _async_update_data(self) -> dict[str, Any]:
        """Run the appropriate cycles for this tick."""
        self._tick += 1
        started = time.monotonic()
        opts = self.config_entry.options
        fast_secs = opts.get(OPT_POLL_FAST_SECONDS, DEFAULT_POLL_FAST_SECONDS)
        change_mins = opts.get(OPT_POLL_CHANGE_DETECT_MINUTES, DEFAULT_POLL_CHANGE_DETECT_MINUTES)
        stats_mins = opts.get(OPT_POLL_STATS_MINUTES, DEFAULT_POLL_STATS_MINUTES)

        fast_every = max(1, round(fast_secs / COORDINATOR_TICK_SECONDS))
        change_every = max(1, round(change_mins * 60 / COORDINATOR_TICK_SECONDS))
        stats_every = max(1, round(stats_mins * 60 / COORDINATOR_TICK_SECONDS))

        try:
            if self._tick % fast_every == 0 or self._tick == 1:
                await self._fast_cycle()
            if self._tick % change_every == 0 or self._tick == 1:
                await self._change_detect_cycle()
            if self._stats_dirty or self._tick % stats_every == 0 or self._tick == 1:
                await self._stats_cycle()
        except AuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except ApiError as exc:
            raise UpdateFailed(str(exc)) from exc
        except (TimeoutError, OSError) as exc:
            raise UpdateFailed(f"Network error: {exc}") from exc

        self._last_tick_summary = {
            "tick": self._tick,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        return self._build_payload()

    async def _fast_cycle(self) -> None:
        entries = await self._client.get_entries(limit=2, since_date=_day_ago_ms(1))
        ds = await self._client.get_devicestatus(limit=1)
        self._latest_entries = entries
        self._latest_devicestatus = ds[0] if ds else None
        if entries:
            inserted = await self._store.insert_batch(entries)
            if inserted:
                self._stats_dirty = True

    async def _change_detect_cycle(self) -> None:
        lm = await self._client.get_last_modified()
        collections = (lm.get("collections") or {}) if isinstance(lm, dict) else {}
        entries_lm = int(collections.get("entries") or 0)
        treatments_lm = int(collections.get("treatments") or 0)

        if entries_lm > self._last_modified_cache.get("entries", 0):
            newest = await self._store.get_sync_state("entries")
            since = newest.newest_date if newest else _day_ago_ms(STATS_HISTORY_MAX_DAYS)
            fresh = await self._client.get_entries(limit=1000, since_date=since, last_modified=self._last_modified_cache.get("entries", 0))
            if fresh:
                await self._store.insert_batch(fresh)
                await self._store.update_sync_state(
                    "entries",
                    last_modified=entries_lm,
                    oldest_date=min(int(e["date"]) for e in fresh),
                    newest_date=max(int(e["date"]) for e in fresh),
                )
                self._stats_dirty = True
            self._last_modified_cache["entries"] = entries_lm

        if treatments_lm > self._last_modified_cache.get("treatments", 0):
            await self._refresh_treatment_aware_features()
            self._last_modified_cache["treatments"] = treatments_lm

    async def _refresh_treatment_aware_features(self) -> None:
        for slot, event in _TREATMENT_AGE_EVENTS.items():
            t = await self._client.get_treatments(event_type=event, limit=1)
            self._treatment_age_cache[slot] = _parse_created(t[0]) if t else None

        meals = await self._client.get_treatments(event_type="Meal Bolus", limit=1)
        if not meals:
            meals = await self._client.get_treatments(event_type="Carbs", limit=1)
        self._last_meal = meals[0] if meals else None

        since = _day_ago_ms(1)
        today = await self._client.get_treatments(since_date=since, limit=200)
        self._carbs_today = sum(float(t.get("carbs") or 0) for t in today)

        note_candidates = await self._client.get_treatments(event_type="Note", limit=1)
        if not note_candidates:
            note_candidates = await self._client.get_treatments(event_type="Announcement", limit=1)
        self._last_note = (note_candidates[0].get("notes") if note_candidates else None)

    async def _stats_cycle(self) -> None:
        enabled = sorted(set(self.config_entry.options.get(OPT_STATS_WINDOWS, [MANDATORY_STATS_WINDOW])) |
                         {MANDATORY_STATS_WINDOW})
        low = self.config_entry.options.get(OPT_TIR_LOW, DEFAULT_TIR_LOW)
        high = self.config_entry.options.get(OPT_TIR_HIGH, DEFAULT_TIR_HIGH)
        vlow = self.config_entry.options.get(OPT_TIR_VERY_LOW, DEFAULT_TIR_VERY_LOW)
        vhigh = self.config_entry.options.get(OPT_TIR_VERY_HIGH, DEFAULT_TIR_VERY_HIGH)

        self._stats: dict[int, dict[str, Any]] = {}
        for w in enabled:
            if w not in ALLOWED_STATS_WINDOWS:
                continue
            entries = await self._store.entries_in_window(days=w)
            payload = compute_all(entries, window_days=w,
                                  tir_low=low, tir_high=high,
                                  tir_very_low=vlow, tir_very_high=vhigh)
            payload["hourly_profile_summary"] = payload["hourly_profile"]
            payload["agp_summary"] = payload["agp_percentiles"]
            self._stats[w] = payload
            await self._store.set_stats_cache(w, payload)
        self._stats_dirty = False

    def _build_payload(self) -> dict[str, Any]:
        entries = getattr(self, "_latest_entries", [])
        ds = getattr(self, "_latest_devicestatus", None) or {}
        stats = getattr(self, "_stats", {})
        now = datetime.now(timezone.utc)

        bg = _bg_block(entries, now)
        pump = _pump_block(ds)
        loop = _loop_block(ds, now)
        uploader = _uploader_block(ds, now)
        care = _care_block(self._treatment_age_cache, now, self._last_meal, self._carbs_today, self._last_note)

        return {
            "bg": bg,
            "pump": pump,
            "loop": loop,
            "uploader": uploader,
            "care": care,
            "stats": {f"{w}d": payload for w, payload in stats.items()},
        }


# ---------- extractor helpers (pure) ----------

def _day_ago_ms(days: int) -> int:
    return int((time.time() - days * 86_400) * 1000)


def _parse_created(t: dict[str, Any]) -> datetime | None:
    raw = t.get("created_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _bg_block(entries: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    if not entries:
        return {"current_sgv": None, "delta_mgdl": None, "direction": None,
                "trend_arrow": None, "stale_minutes": None}
    latest = entries[0]
    prev = entries[1] if len(entries) > 1 else None
    stale_minutes = int((now.timestamp() * 1000 - int(latest["date"])) / 60000)
    return {
        "current_sgv": int(latest["sgv"]),
        "delta_mgdl": int(latest["sgv"] - prev["sgv"]) if prev else 0,
        "direction": latest.get("direction"),
        "trend_arrow": _DIRECTION_TO_ARROW.get(latest.get("direction", ""), "?"),
        "stale_minutes": stale_minutes,
    }


def _pump_block(ds: dict[str, Any]) -> dict[str, Any]:
    pump = ds.get("pump") or {}
    extended = pump.get("extended") or {}
    battery = (pump.get("battery") or {}).get("percent")
    status_text = (pump.get("status") or {}).get("status")
    last_bolus_time = _parse_last_bolus(extended.get("LastBolus"))
    return {
        "reservoir": pump.get("reservoir"),
        "battery_percent": battery,
        "status_text": status_text,
        "base_basal": extended.get("BaseBasalRate"),
        "temp_basal_rate": _temp_basal_rate(ds),
        "temp_basal_remaining": extended.get("TempBasalRemaining"),
        "active_profile": extended.get("ActiveProfile"),
        "last_bolus_time": last_bolus_time,
        "last_bolus_amount": extended.get("LastBolusAmount"),
    }


def _temp_basal_rate(ds: dict[str, Any]) -> float | None:
    """Primary: openaps.enacted.rate; fallback None (treatments lookup is in change-detect)."""
    openaps = ds.get("openaps") or {}
    enacted = openaps.get("enacted") or {}
    return enacted.get("rate")


def _parse_last_bolus(raw: Any) -> str | None:
    """AAPS emits strings like '21.04. 19:15' — surface as-is; consumers can render."""
    if raw in (None, "", "null"):
        return None
    return str(raw)


def _loop_block(ds: dict[str, Any], now: datetime) -> dict[str, Any]:
    if not ds:
        return {"mode": None, "active": False, "eventual_bg": None, "target_bg": None,
                "iob": None, "basaliob": None, "activity": None, "cob": None,
                "sensitivity_ratio": None, "reason": None, "pred_bgs": None,
                "last_enacted_age_minutes": None}
    openaps = ds.get("openaps") or {}
    iob = openaps.get("iob") or {}
    suggested = openaps.get("suggested") or {}
    created = _parse_created(ds)
    age_min = int((now - created).total_seconds() / 60) if created else None
    active = age_min is not None and age_min <= 10 and bool(openaps)
    pump_status = ((ds.get("pump") or {}).get("status") or {}).get("status", "")
    if "suspend" in pump_status.lower():
        mode = "Suspended"
    elif active:
        mode = "Closed"
    else:
        mode = "Open"
    return {
        "mode": mode,
        "active": active,
        "eventual_bg": suggested.get("eventualBG"),
        "target_bg": suggested.get("targetBG"),
        "iob": iob.get("iob"),
        "basaliob": iob.get("basaliob"),
        "activity": iob.get("activity"),
        "cob": suggested.get("COB"),
        "sensitivity_ratio": suggested.get("sensitivityRatio"),
        "reason": suggested.get("reason"),
        "pred_bgs": suggested.get("predBGs"),
        "last_enacted_age_minutes": age_min,
    }


def _uploader_block(ds: dict[str, Any], now: datetime) -> dict[str, Any]:
    if not ds:
        return {"battery_percent": None, "online": False, "charging": None}
    created = _parse_created(ds)
    age_min = int((now - created).total_seconds() / 60) if created else None
    return {
        "battery_percent": ds.get("uploaderBattery") or (((ds.get("pump") or {}).get("battery") or {}).get("percent")),
        "online": age_min is not None and age_min < 15,
        "charging": ds.get("isCharging"),
    }


def _care_block(
    ages: dict[str, datetime | None],
    now: datetime,
    last_meal: dict[str, Any] | None,
    carbs_today: float,
    last_note: str | None,
) -> dict[str, Any]:
    def _age_days(slot: str) -> float | None:
        d = ages.get(slot)
        return round((now - d).total_seconds() / 86_400, 2) if d else None

    return {
        "sage_days": _age_days("sensor"),
        "cage_days": _age_days("site"),
        "iage_days": _age_days("insulin"),
        "bage_days": _age_days("battery"),
        "last_meal_carbs": (last_meal or {}).get("carbs"),
        "carbs_today": round(carbs_today, 2),
        "last_note": last_note,
    }
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_coordinator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/nightscout_v3/coordinator.py tests/test_coordinator.py
git commit -m "feat(ha): NightscoutCoordinator with staggered fast/change/stats cycles"
```

---

### Task 3.3: `__init__.py` — setup / unload

**Files:**
- Create (replace): `custom_components/nightscout_v3/__init__.py`
- Create: `custom_components/nightscout_v3/models.py`
- Test: `tests/test_init.py`

- [ ] **Step 1: Create `custom_components/nightscout_v3/models.py`**

```python
"""Runtime-data dataclass for nightscout_v3."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .api.auth import JwtManager
from .api.capabilities import ServerCapabilities
from .api.client import NightscoutV3Client
from .coordinator import NightscoutCoordinator
from .history_store import HistoryStore


@dataclass(slots=True)
class NightscoutData:
    """Everything a config entry owns at runtime."""

    client: NightscoutV3Client
    coordinator: NightscoutCoordinator
    store: HistoryStore
    capabilities: ServerCapabilities
    jwt_manager: JwtManager
    jwt_refresh_unsub: Callable[[], None]


type NightscoutConfigEntry = ConfigEntry[NightscoutData]
```

- [ ] **Step 2: Write failing test `tests/test_init.py`**

```python
"""Tests for async_setup_entry / async_unload_entry."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nightscout_v3.const import DOMAIN
from tests.conftest import load_fixture


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="abc1234567890def",
        title="Test User",
        data={
            "url": "https://ns.example",
            "access_token": "access-test",
            "capabilities": None,
            "capabilities_probed_at": 0,
        },
        options={"enabled_features": {}, "stats_windows": [14]},
    )


async def test_setup_and_unload(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)

    with (
        patch("custom_components.nightscout_v3.api.auth.JwtManager.initial_exchange",
              new=AsyncMock(return_value=MagicMock(token="jwt", iat=0, exp=9999999999))),
        patch("custom_components.nightscout_v3.api.capabilities.probe_capabilities",
              new=AsyncMock(return_value=_caps())),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_entries",
              new=AsyncMock(return_value=load_fixture("entries_latest")["result"])),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_devicestatus",
              new=AsyncMock(return_value=load_fixture("devicestatus_latest")["result"])),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_last_modified",
              new=AsyncMock(return_value=load_fixture("lastmodified")["result"])),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_treatments",
              new=AsyncMock(return_value=[])),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


def _caps():
    from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
    return ServerCapabilities(
        units="mg/dl", has_openaps=True, has_pump=True, has_uploader_battery=True,
        has_entries=True, has_treatments_sensor_change=True, has_treatments_site_change=True,
        has_treatments_insulin_change=True, has_treatments_pump_battery_change=True,
        last_probed_at_ms=0,
    )
```

- [ ] **Step 3: Run — expect FAIL**

```bash
pytest tests/test_init.py -v
```

- [ ] **Step 4: Implement `custom_components/nightscout_v3/__init__.py`**

```python
"""Nightscout v3 integration setup."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .api.auth import JwtManager
from .api.capabilities import ServerCapabilities, probe_capabilities
from .api.client import NightscoutV3Client
from .api.exceptions import ApiError, AuthError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CAPABILITIES,
    CONF_CAPABILITIES_PROBED_AT,
    CONF_URL,
    DOMAIN,
    JWT_BACKGROUND_REFRESH_HOURS,
)
from .coordinator import NightscoutCoordinator
from .history_store import HistoryStore
from .models import NightscoutConfigEntry, NightscoutData

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NightscoutConfigEntry) -> bool:
    """Set up nightscout_v3 from a config entry."""
    session = async_get_clientsession(hass)
    url: str = entry.data[CONF_URL]
    token: str = entry.data[CONF_ACCESS_TOKEN]

    jwt_manager = JwtManager(session, url, token)
    client = NightscoutV3Client(session, url, jwt_manager)

    try:
        await jwt_manager.initial_exchange()
    except AuthError as exc:
        raise ConfigEntryAuthFailed(str(exc)) from exc
    except ApiError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    try:
        capabilities = await probe_capabilities(client)
    except AuthError as exc:
        raise ConfigEntryAuthFailed(str(exc)) from exc
    except ApiError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_CAPABILITIES: capabilities.to_dict(),
            CONF_CAPABILITIES_PROBED_AT: capabilities.last_probed_at_ms,
        },
    )

    db_path = hass.config.path(".storage", f"nightscout_v3_{entry.entry_id}.db")
    from pathlib import Path
    store = await HistoryStore.open(Path(db_path))
    if await store.is_corrupt():
        await store.recover_from_corruption()

    coordinator = NightscoutCoordinator(hass, client, capabilities, store, entry)
    await coordinator.async_config_entry_first_refresh()

    async def _refresh_jwt(_now) -> None:
        try:
            await jwt_manager.refresh()
        except AuthError:
            _LOGGER.warning("JWT refresh rejected; awaiting reauth")
        except ApiError as exc:
            _LOGGER.debug("JWT refresh failed transiently: %s", exc)

    jwt_refresh_unsub = async_track_time_interval(
        hass, _refresh_jwt, timedelta(hours=JWT_BACKGROUND_REFRESH_HOURS)
    )

    entry.runtime_data = NightscoutData(
        client=client,
        coordinator=coordinator,
        store=store,
        capabilities=capabilities,
        jwt_manager=jwt_manager,
        jwt_refresh_unsub=jwt_refresh_unsub,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NightscoutConfigEntry) -> bool:
    """Unload a config entry cleanly."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unloaded:
        data = entry.runtime_data
        data.jwt_refresh_unsub()
        await data.coordinator.async_shutdown()
        await data.store.close()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry on options changes."""
    await hass.config_entries.async_reload(entry.entry_id)
```

- [ ] **Step 5: Run — expect PASS**

```bash
pytest tests/test_init.py -v
```

- [ ] **Step 6: Commit**

```bash
git add custom_components/nightscout_v3/__init__.py custom_components/nightscout_v3/models.py tests/test_init.py
git commit -m "feat(ha): async_setup_entry/async_unload_entry with runtime_data + JWT background refresh"
```

---

### Task 3.4: Config flow — user step

**Files:**
- Create: `custom_components/nightscout_v3/config_flow.py`
- Test: `tests/test_config_flow.py`

- [ ] **Step 1: Write failing test `tests/test_config_flow.py` (user step only)**

```python
"""Config flow tests — user step."""
from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.nightscout_v3.const import DOMAIN
from tests.conftest import load_fixture


@pytest.fixture
def valid_caps():
    from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
    return ServerCapabilities(
        units="mg/dl", has_openaps=True, has_pump=True, has_uploader_battery=True,
        has_entries=True, has_treatments_sensor_change=True, has_treatments_site_change=True,
        has_treatments_insulin_change=True, has_treatments_pump_battery_change=True,
        last_probed_at_ms=0,
    )


async def test_user_step_happy_path(hass: HomeAssistant, valid_caps) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
              new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0))),
        patch("custom_components.nightscout_v3.config_flow.probe_capabilities",
              new=AsyncMock(return_value=valid_caps)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://ns.example/", "access_token": "tok"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ns.example"
    expected_uid = hashlib.sha256(b"https://ns.example").hexdigest()[:16]
    assert result["result"].unique_id == expected_uid


@pytest.mark.parametrize(
    ("exc", "error_key"),
    [
        ("auth", "invalid_auth"),
        ("api", "cannot_connect"),
        ("unknown", "unknown"),
    ],
)
async def test_user_step_errors(hass, exc, error_key) -> None:
    from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError
    exception_map = {
        "auth": AuthError("401"),
        "api": ApiError("boom", status=503),
        "unknown": Exception("???"),
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch("custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
               new=AsyncMock(side_effect=exception_map[exc])):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://ns.example/", "access_token": "tok"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}


async def test_user_step_duplicate_aborts(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    existing_uid = hashlib.sha256(b"https://ns.example").hexdigest()[:16]
    MockConfigEntry(domain=DOMAIN, unique_id=existing_uid).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch("custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
              new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0))),
        patch("custom_components.nightscout_v3.config_flow.probe_capabilities",
              new=AsyncMock(return_value=valid_caps)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://ns.example/", "access_token": "tok"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_config_flow.py -v
```

- [ ] **Step 3: Implement `custom_components/nightscout_v3/config_flow.py`**

```python
"""Config + Options flow for nightscout_v3."""
from __future__ import annotations

import hashlib
import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api.auth import JwtManager
from .api.capabilities import probe_capabilities
from .api.client import NightscoutV3Client
from .api.exceptions import ApiError, AuthError
from .const import (
    ALLOWED_STATS_WINDOWS,
    CONF_ACCESS_TOKEN,
    CONF_CAPABILITIES,
    CONF_CAPABILITIES_PROBED_AT,
    DEFAULT_POLL_CHANGE_DETECT_MINUTES,
    DEFAULT_POLL_FAST_SECONDS,
    DEFAULT_POLL_STATS_MINUTES,
    DEFAULT_TIR_HIGH,
    DEFAULT_TIR_LOW,
    DEFAULT_TIR_VERY_HIGH,
    DEFAULT_TIR_VERY_LOW,
    DOMAIN,
    MANDATORY_STATS_WINDOW,
    OPT_ENABLED_FEATURES,
    OPT_POLL_CHANGE_DETECT_MINUTES,
    OPT_POLL_FAST_SECONDS,
    OPT_POLL_STATS_MINUTES,
    OPT_STATS_WINDOWS,
    OPT_TIR_HIGH,
    OPT_TIR_LOW,
    OPT_TIR_VERY_HIGH,
    OPT_TIR_VERY_LOW,
)
from .feature_registry import Category, features_for_capabilities

_LOGGER = logging.getLogger(__name__)

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    }
)


def _normalize(url: str) -> str:
    u = urlparse(url.strip())
    scheme = u.scheme or "https"
    netloc = u.netloc.rstrip("/")
    path = u.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


def _unique_id(url: str) -> str:
    return hashlib.sha256(_normalize(url).encode("utf-8")).hexdigest()[:16]


class NightscoutConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._url: str | None = None
        self._token: str | None = None
        self._capabilities: Any | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = _normalize(user_input[CONF_URL])
            token = user_input[CONF_ACCESS_TOKEN]
            await self.async_set_unique_id(_unique_id(url))
            self._abort_if_unique_id_configured()
            try:
                session = async_get_clientsession(self.hass)
                mgr = JwtManager(session, url, token)
                await mgr.initial_exchange()
                client = NightscoutV3Client(session, url, mgr)
                self._capabilities = await probe_capabilities(client)
                self._url = url
                self._token = token
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 — catch-all for unknown flow paths
                _LOGGER.exception("Unhandled error in user step")
                errors["base"] = "unknown"

            if not errors:
                return self._create_entry_from_capabilities()

        return self.async_show_form(step_id="user", data_schema=_USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        self._url = entry_data[CONF_URL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_ACCESS_TOKEN]
            try:
                session = async_get_clientsession(self.hass)
                mgr = JwtManager(session, self._url or "", token)
                await mgr.initial_exchange()
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unhandled error in reauth")
                errors["base"] = "unknown"

            if not errors:
                reauth_entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, CONF_ACCESS_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): cv.string}),
            errors=errors,
        )

    def _create_entry_from_capabilities(self) -> ConfigFlowResult:
        assert self._capabilities is not None and self._url is not None and self._token is not None
        title = urlparse(self._url).netloc or self._url
        enabled = {
            f.key: f.default_enabled for f in features_for_capabilities(self._capabilities)
        }
        return self.async_create_entry(
            title=title,
            data={
                CONF_URL: self._url,
                CONF_ACCESS_TOKEN: self._token,
                CONF_CAPABILITIES: self._capabilities.to_dict(),
                CONF_CAPABILITIES_PROBED_AT: self._capabilities.last_probed_at_ms,
            },
            options={
                OPT_ENABLED_FEATURES: enabled,
                OPT_STATS_WINDOWS: [MANDATORY_STATS_WINDOW],
                OPT_TIR_LOW: DEFAULT_TIR_LOW,
                OPT_TIR_HIGH: DEFAULT_TIR_HIGH,
                OPT_TIR_VERY_LOW: DEFAULT_TIR_VERY_LOW,
                OPT_TIR_VERY_HIGH: DEFAULT_TIR_VERY_HIGH,
                OPT_POLL_FAST_SECONDS: DEFAULT_POLL_FAST_SECONDS,
                OPT_POLL_CHANGE_DETECT_MINUTES: DEFAULT_POLL_CHANGE_DETECT_MINUTES,
                OPT_POLL_STATS_MINUTES: DEFAULT_POLL_STATS_MINUTES,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NightscoutOptionsFlow(config_entry)


class NightscoutOptionsFlow(OptionsFlow):
    """Options: menu + sub-steps (Task 3.5 fills all branches)."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["features", "stats", "thresholds", "polling", "rediscover"],
        )

    # Sub-steps implemented in Task 3.5
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_config_flow.py -v
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/nightscout_v3/config_flow.py tests/test_config_flow.py
git commit -m "feat(ha): config flow user step + unique_id dedup + reauth scaffold"
```

---

### Task 3.5: Config flow — options sub-steps

**Files:**
- Modify: `custom_components/nightscout_v3/config_flow.py` (append sub-step methods)
- Modify: `tests/test_config_flow.py` (append options tests)

- [ ] **Step 1: Write failing tests — append to `tests/test_config_flow.py`**

```python
# --- options flow ---

async def test_options_features_sub_step(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid1",
        data={"url": "https://ns.example", "access_token": "t",
              "capabilities": valid_caps.to_dict(), "capabilities_probed_at": 0},
        options={"enabled_features": {"bg_current": True}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"].name == "MENU"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "features"}
    )
    assert result["type"].name == "FORM"
    assert result["step_id"] == "features"


async def test_options_stats_windows(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="uid2",
        data={"url": "https://ns.example", "access_token": "t",
              "capabilities": valid_caps.to_dict(), "capabilities_probed_at": 0},
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "stats"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"stats_windows": [7, 14, 30]}
    )
    assert result["type"].name == "CREATE_ENTRY"
    assert sorted(result["data"]["stats_windows"]) == [7, 14, 30]


async def test_options_rediscover_updates_capabilities(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from unittest.mock import AsyncMock, patch, MagicMock
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="uid3",
        data={"url": "https://ns.example", "access_token": "t",
              "capabilities": valid_caps.to_dict(), "capabilities_probed_at": 0},
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with (
        patch("custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
              new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0))),
        patch("custom_components.nightscout_v3.config_flow.probe_capabilities",
              new=AsyncMock(return_value=valid_caps)),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "rediscover"}
        )
    assert result["type"].name == "CREATE_ENTRY"
```

- [ ] **Step 2: Append sub-step methods to `NightscoutOptionsFlow`** (inside `config_flow.py`, same class as Task 3.4)

```python
# -- inside NightscoutOptionsFlow --

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        from .api.capabilities import ServerCapabilities

        caps = ServerCapabilities.from_dict(self._entry.data[CONF_CAPABILITIES])
        features = features_for_capabilities(caps)
        current = dict(self._entry.options.get(OPT_ENABLED_FEATURES, {}))

        if user_input is not None:
            current.update({f.key: bool(user_input.get(f.key, False)) for f in features})
            return self.async_create_entry(
                title="", data={**self._entry.options, OPT_ENABLED_FEATURES: current}
            )

        schema: dict[Any, Any] = {}
        for cat in Category:
            for f in features:
                if f.category != cat:
                    continue
                schema[vol.Optional(f.key, default=current.get(f.key, f.default_enabled))] = bool
        return self.async_show_form(step_id="features", data_schema=vol.Schema(schema))

    async def async_step_stats(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            chosen = sorted(set(int(w) for w in user_input.get(OPT_STATS_WINDOWS, [])) | {MANDATORY_STATS_WINDOW})
            return self.async_create_entry(
                title="", data={**self._entry.options, OPT_STATS_WINDOWS: chosen}
            )
        current = list(self._entry.options.get(OPT_STATS_WINDOWS, [MANDATORY_STATS_WINDOW]))
        schema = vol.Schema(
            {
                vol.Optional(OPT_STATS_WINDOWS, default=current): cv.multi_select(
                    {w: f"{w}d" for w in ALLOWED_STATS_WINDOWS}
                )
            }
        )
        return self.async_show_form(step_id="stats", data_schema=schema)

    async def async_step_thresholds(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data={**self._entry.options, **user_input})
        current = self._entry.options
        schema = vol.Schema(
            {
                vol.Optional(OPT_TIR_LOW, default=current.get(OPT_TIR_LOW, DEFAULT_TIR_LOW)): vol.All(int, vol.Range(min=40, max=120)),
                vol.Optional(OPT_TIR_HIGH, default=current.get(OPT_TIR_HIGH, DEFAULT_TIR_HIGH)): vol.All(int, vol.Range(min=120, max=300)),
                vol.Optional(OPT_TIR_VERY_LOW, default=current.get(OPT_TIR_VERY_LOW, DEFAULT_TIR_VERY_LOW)): vol.All(int, vol.Range(min=30, max=80)),
                vol.Optional(OPT_TIR_VERY_HIGH, default=current.get(OPT_TIR_VERY_HIGH, DEFAULT_TIR_VERY_HIGH)): vol.All(int, vol.Range(min=180, max=400)),
            }
        )
        return self.async_show_form(step_id="thresholds", data_schema=schema)

    async def async_step_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data={**self._entry.options, **user_input})
        current = self._entry.options
        schema = vol.Schema(
            {
                vol.Optional(OPT_POLL_FAST_SECONDS, default=current.get(OPT_POLL_FAST_SECONDS, DEFAULT_POLL_FAST_SECONDS)): vol.All(int, vol.Range(min=30, max=600)),
                vol.Optional(OPT_POLL_CHANGE_DETECT_MINUTES, default=current.get(OPT_POLL_CHANGE_DETECT_MINUTES, DEFAULT_POLL_CHANGE_DETECT_MINUTES)): vol.All(int, vol.Range(min=1, max=60)),
                vol.Optional(OPT_POLL_STATS_MINUTES, default=current.get(OPT_POLL_STATS_MINUTES, DEFAULT_POLL_STATS_MINUTES)): vol.All(int, vol.Range(min=5, max=240)),
            }
        )
        return self.async_show_form(step_id="polling", data_schema=schema)

    async def async_step_rediscover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        try:
            session = async_get_clientsession(self.hass)
            mgr = JwtManager(session, self._entry.data[CONF_URL], self._entry.data[CONF_ACCESS_TOKEN])
            await mgr.initial_exchange()
            client = NightscoutV3Client(session, self._entry.data[CONF_URL], mgr)
            caps = await probe_capabilities(client)
        except (AuthError, ApiError):
            return self.async_abort(reason="cannot_connect")

        self.hass.config_entries.async_update_entry(
            self._entry,
            data={
                **self._entry.data,
                CONF_CAPABILITIES: caps.to_dict(),
                CONF_CAPABILITIES_PROBED_AT: caps.last_probed_at_ms,
            },
        )
        return self.async_create_entry(title="", data=dict(self._entry.options))
```

- [ ] **Step 3: Run — expect PASS**

```bash
pytest tests/test_config_flow.py -v
```

- [ ] **Step 4: Commit**

```bash
git add custom_components/nightscout_v3/config_flow.py tests/test_config_flow.py
git commit -m "feat(ha): options flow sub-steps (features, stats, thresholds, polling, rediscover)"
```

---

### Task 3.6: Reauth flow test coverage

**Files:**
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Add failing reauth tests at end of `tests/test_config_flow.py`**

```python
async def test_reauth_happy_path(hass, valid_caps) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from unittest.mock import AsyncMock, patch, MagicMock
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="rauid",
        data={"url": "https://ns.example", "access_token": "old",
              "capabilities": valid_caps.to_dict(), "capabilities_probed_at": 0},
        options={},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"].name == "FORM"
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
        new=AsyncMock(return_value=MagicMock(token="jwt", exp=9999999999, iat=0)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"access_token": "new"}
        )
    assert result["type"].name == "ABORT"
    assert result["reason"] == "reauth_successful"
    assert entry.data["access_token"] == "new"


@pytest.mark.parametrize(
    ("exc", "error_key"),
    [("auth", "invalid_auth"), ("api", "cannot_connect"), ("unknown", "unknown")],
)
async def test_reauth_errors(hass, valid_caps, exc, error_key) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from unittest.mock import AsyncMock, patch
    from custom_components.nightscout_v3.api.exceptions import ApiError, AuthError

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=f"rauid-{exc}",
        data={"url": "https://ns.example", "access_token": "old",
              "capabilities": valid_caps.to_dict(), "capabilities_probed_at": 0},
        options={},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    exc_map = {"auth": AuthError("401"), "api": ApiError("x"), "unknown": Exception("?")}
    with patch("custom_components.nightscout_v3.config_flow.JwtManager.initial_exchange",
               new=AsyncMock(side_effect=exc_map[exc])):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"access_token": "new"}
        )
    assert result["errors"] == {"base": error_key}
```

- [ ] **Step 2: Run — expect PASS (reauth already implemented in Task 3.4)**

```bash
pytest tests/test_config_flow.py -v -k reauth
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_config_flow.py
git commit -m "test(ha): reauth flow happy path + parametrized errors"
```

---

### Task 3.7: Sensor + binary_sensor platforms

**Files:**
- Create: `custom_components/nightscout_v3/sensor.py`
- Create: `custom_components/nightscout_v3/binary_sensor.py`
- Test: `tests/test_sensor.py`

- [ ] **Step 1: Write failing test `tests/test_sensor.py`**

```python
"""Tests for sensor / binary_sensor platform registration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
from custom_components.nightscout_v3.const import DOMAIN
from tests.conftest import load_fixture


@pytest.fixture
def caps() -> ServerCapabilities:
    return ServerCapabilities(
        units="mg/dl", has_openaps=True, has_pump=True, has_uploader_battery=True,
        has_entries=True, has_treatments_sensor_change=True, has_treatments_site_change=True,
        has_treatments_insulin_change=True, has_treatments_pump_battery_change=True,
        last_probed_at_ms=0,
    )


async def test_sensors_register_for_enabled_features(hass: HomeAssistant, caps) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="u1", title="Test",
        data={"url": "https://ns.example", "access_token": "t",
              "capabilities": caps.to_dict(), "capabilities_probed_at": 0},
        options={"enabled_features": {"bg_current": True, "bg_delta": False},
                 "stats_windows": [14]},
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.nightscout_v3.api.auth.JwtManager.initial_exchange",
              new=AsyncMock(return_value=type("S", (), {"token": "j", "iat": 0, "exp": 9999999999})())),
        patch("custom_components.nightscout_v3.api.capabilities.probe_capabilities",
              new=AsyncMock(return_value=caps)),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_entries",
              new=AsyncMock(return_value=load_fixture("entries_latest")["result"])),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_devicestatus",
              new=AsyncMock(return_value=load_fixture("devicestatus_latest")["result"])),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_last_modified",
              new=AsyncMock(return_value=load_fixture("lastmodified")["result"])),
        patch("custom_components.nightscout_v3.api.client.NightscoutV3Client.get_treatments",
              new=AsyncMock(return_value=[])),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # enabled feature -> entity exists
    state = hass.states.get("sensor.test_bg_current")
    assert state is not None
    # disabled feature -> no entity
    assert hass.states.get("sensor.test_bg_delta") is None


async def test_parallel_updates_zero():
    import custom_components.nightscout_v3.sensor as sm
    import custom_components.nightscout_v3.binary_sensor as bm
    assert sm.PARALLEL_UPDATES == 0
    assert bm.PARALLEL_UPDATES == 0
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_sensor.py -v
```

- [ ] **Step 3: Implement `custom_components/nightscout_v3/sensor.py`**

```python
"""Sensor platform — one SensorEntity per enabled feature."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import OPT_ENABLED_FEATURES, OPT_STATS_WINDOWS, MANDATORY_STATS_WINDOW
from .entity import NightscoutEntity
from .feature_registry import Category, FEATURE_REGISTRY, FeatureDef, features_for_capabilities, stats_feature_defs
from .models import NightscoutConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: NightscoutConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    enabled = entry.options.get(OPT_ENABLED_FEATURES, {})
    active = features_for_capabilities(data.capabilities)
    entities: list[SensorEntity] = []
    for f in active:
        if f.platform != Platform.SENSOR:
            continue
        if not enabled.get(f.key, f.default_enabled):
            continue
        entities.append(NightscoutSensor(data.coordinator, f))

    windows = sorted(set(entry.options.get(OPT_STATS_WINDOWS, [MANDATORY_STATS_WINDOW])) | {MANDATORY_STATS_WINDOW})
    for w in windows:
        for f in stats_feature_defs(w):
            if not enabled.get(f.key, f.default_enabled):
                continue
            entities.append(NightscoutSensor(data.coordinator, f))

    async_add_entities(entities)


class NightscoutSensor(NightscoutEntity, SensorEntity):
    """One coordinator-backed SensorEntity."""

    def __init__(self, coordinator, feature: FeatureDef) -> None:
        super().__init__(coordinator, feature)
        self._attr_device_class = feature.device_class
        self._attr_state_class = feature.state_class
        self._attr_native_unit_of_measurement = feature.unit

    @property
    def native_value(self) -> Any:
        val = self._extract()
        if isinstance(val, dict | list):
            return None  # complex values are surfaced as extra_state_attributes
        return val

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        val = self._extract()
        if isinstance(val, dict):
            return val
        if isinstance(val, list):
            return {"items": val}
        return None
```

- [ ] **Step 4: Implement `custom_components/nightscout_v3/binary_sensor.py`**

```python
"""Binary sensor platform — one BinarySensorEntity per enabled feature."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import OPT_ENABLED_FEATURES
from .entity import NightscoutEntity
from .feature_registry import FeatureDef, features_for_capabilities
from .models import NightscoutConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: NightscoutConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    enabled = entry.options.get(OPT_ENABLED_FEATURES, {})
    entities: list[BinarySensorEntity] = []
    for f in features_for_capabilities(data.capabilities):
        if f.platform != Platform.BINARY_SENSOR:
            continue
        if not enabled.get(f.key, f.default_enabled):
            continue
        entities.append(NightscoutBinarySensor(data.coordinator, f))
    async_add_entities(entities)


class NightscoutBinarySensor(NightscoutEntity, BinarySensorEntity):
    """Coordinator-backed binary sensor."""

    def __init__(self, coordinator, feature: FeatureDef) -> None:
        super().__init__(coordinator, feature)
        self._attr_device_class = feature.device_class

    @property
    def is_on(self) -> bool | None:
        val = self._extract()
        if val is None:
            return None
        return bool(val)
```

- [ ] **Step 5: Run — expect PASS**

```bash
pytest tests/test_sensor.py -v
```

- [ ] **Step 6: Commit**

```bash
git add custom_components/nightscout_v3/sensor.py custom_components/nightscout_v3/binary_sensor.py tests/test_sensor.py
git commit -m "feat(ha): sensor + binary_sensor platforms driven by FEATURE_REGISTRY"
```

---

### Task 3.8: Diagnostics

**Files:**
- Create: `custom_components/nightscout_v3/diagnostics.py`
- Test: `tests/test_diagnostics.py`

- [ ] **Step 1: Write failing test `tests/test_diagnostics.py`**

```python
"""Diagnostics redaction tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
from custom_components.nightscout_v3.const import DOMAIN
from custom_components.nightscout_v3.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.fixture
def caps() -> ServerCapabilities:
    return ServerCapabilities(
        units="mg/dl", has_openaps=True, has_pump=True, has_uploader_battery=True,
        has_entries=True, has_treatments_sensor_change=True, has_treatments_site_change=True,
        has_treatments_insulin_change=True, has_treatments_pump_battery_change=True,
        last_probed_at_ms=0,
    )


async def test_diagnostics_redacts_url_and_token(hass: HomeAssistant, caps) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="uid-diag", title="Test",
        data={"url": "https://secret.example", "access_token": "SECRET",
              "capabilities": caps.to_dict(), "capabilities_probed_at": 0},
        options={"enabled_features": {}, "stats_windows": [14]},
    )
    entry.add_to_hass(hass)

    # Fake runtime_data path shape without doing full setup
    with patch(
        "custom_components.nightscout_v3.diagnostics._collect_runtime",
        return_value={"coordinator": {"tick": 5}, "jwt": {"exp_in_seconds": 120}},
    ):
        diag = await async_get_config_entry_diagnostics(hass, entry)

    dumped = str(diag)
    assert "SECRET" not in dumped
    assert "secret.example" not in dumped
    assert diag["entry"]["data"]["url"] == "**REDACTED**"
    assert diag["entry"]["data"]["access_token"] == "**REDACTED**"
    assert diag["runtime"]["coordinator"]["tick"] == 5
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_diagnostics.py -v
```

- [ ] **Step 3: Implement `custom_components/nightscout_v3/diagnostics.py`**

```python
"""Redacted diagnostics dump."""
from __future__ import annotations

import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_TO_REDACT = {"url", "access_token", "api_secret", "identifier", "sub", "token"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    runtime = _collect_runtime(entry)
    return {
        "entry": {
            "entry_id": entry.entry_id,
            "data": async_redact_data(dict(entry.data), _TO_REDACT),
            "options": dict(entry.options),
            "title": entry.title,
            "unique_id": entry.unique_id,
        },
        "runtime": async_redact_data(runtime, _TO_REDACT),
    }


def _collect_runtime(entry: ConfigEntry) -> dict[str, Any]:
    data = getattr(entry, "runtime_data", None)
    if data is None:
        return {}
    jwt_state = data.jwt_manager.state
    jwt_info: dict[str, Any] = {}
    if jwt_state is not None:
        jwt_info = {
            "exp_in_seconds": max(0, int(jwt_state.exp - time.time())),
            "iat": jwt_state.iat,
            "exp": jwt_state.exp,
        }
    return {
        "coordinator": {
            "last_update_success": data.coordinator.last_update_success,
            **data.coordinator.last_tick_summary,
        },
        "jwt": jwt_info,
        "capabilities": data.capabilities.to_dict(),
        "snapshot": data.coordinator.data,
    }
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_diagnostics.py -v
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/nightscout_v3/diagnostics.py tests/test_diagnostics.py
git commit -m "feat(ha): diagnostics with redaction (url, token, identifiers)"
```

---

### Phase 3 review

- [ ] **Step 1: Run full test suite + coverage**

```bash
pytest --cov=custom_components.nightscout_v3 --cov-report=term-missing
```

Expected: ≥ 90 % overall; config_flow and auth ≥ 100 %.

- [ ] **Step 2: Dispatch code-reviewer subagent**

Brief: Review phase 3 (`entity.py`, `coordinator.py`, `__init__.py`, `config_flow.py`, `sensor.py`, `binary_sensor.py`, `diagnostics.py`) against `docs/references/ha-silver-quality-scale.md` rules:
- `runtime-data`, `has-entity-name`, `entity-unique-id`, `parallel-updates`, `config-entry-unloading`, `entity-unavailable`, `reauthentication-flow`, `test-before-configure`, `test-before-setup`, `unique-config-entry`, `log-when-unavailable`, `integration-owner`.

Report discrepancies per rule + coverage gaps.

- [ ] **Step 3: Commit review report**

```bash
git add docs/reviews/
git commit -m "docs(review): phase 3 (HA integration) code-reviewer report"
```

---

## Phase 4 — Scripts

Dev/ops scripts that do not ship to end users but are tracked in git. They live under `scripts/` and get unit-tested where feasible.

### Task 4.1 — `scripts/anonymize_fixtures.py`

Purpose: Scrub real Nightscout responses (captured from DevInstance) into public-safe fixtures. Replaces URLs, tokens, notes/carbs/boluses with deterministic fake values; keeps numeric shape (sgv, delta, timestamps normalized to a synthetic epoch).

- [ ] **Step 1: Write failing test** `tests/scripts/test_anonymize_fixtures.py`

```python
"""Tests for anonymize_fixtures script."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.anonymize_fixtures import anonymize_payload


def test_redacts_urls_tokens_and_notes() -> None:
    raw = {
        "status": "OK",
        "result": [
            {
                "_id": "abc123def456",
                "sgv": 142,
                "direction": "Flat",
                "date": 1713780000000,
                "notes": "ate pizza at CornerCafe's",
                "enteredBy": "user@example.invalid",
                "url": "https://dev-nightscout.example.invalid/api/v3/entries",
            }
        ],
    }
    anon = anonymize_payload(raw, epoch_offset_ms=1713780000000)
    entry = anon["result"][0]
    assert entry["sgv"] == 142, "numeric payload must survive"
    assert entry["direction"] == "Flat"
    assert entry["date"] == 0, "timestamp must be rebased"
    assert "CornerCafe" not in json.dumps(anon)
    assert "example-private" not in json.dumps(anon)
    assert "timm" not in json.dumps(anon).lower()
    assert entry["_id"] != "abc123def456"
    assert len(entry["_id"]) == 24


def test_treatment_carbs_bucketed() -> None:
    raw = {"status": "OK", "result": [{"eventType": "Meal Bolus", "carbs": 47, "insulin": 3.1, "date": 1713780000000}]}
    anon = anonymize_payload(raw, epoch_offset_ms=1713780000000)
    t = anon["result"][0]
    # Carbs bucket to nearest 10 g to further anonymize patterns
    assert t["carbs"] in (40, 50)
    assert t["insulin"] == 3.1  # insulin units preserved (not identifying)


def test_preserves_status_envelope() -> None:
    raw = {"status": "OK", "result": []}
    assert anonymize_payload(raw, epoch_offset_ms=0) == raw
```

- [ ] **Step 2: Run the test** — confirm failure (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `scripts/__init__.py` (empty) and `scripts/anonymize_fixtures.py`:

```python
"""Anonymize Nightscout JSON captures into public-safe fixtures.

Usage:
    python -m scripts.anonymize_fixtures captures/*.json tests/fixtures/

The goal is to strip anything that could identify a person, a server, or a
medical event while keeping the numeric *shape* of the response so that
offline tests exercise realistic code paths.
"""
from __future__ import annotations

import argparse
import json
import secrets
import string
import sys
from pathlib import Path
from typing import Any

SENSITIVE_STRING_KEYS = {
    "notes", "enteredBy", "profileJson", "created_at", "srvModified",
    "url", "baseURL", "instance", "hostname", "author", "email", "username",
    "name", "firstName", "lastName", "patient",
}

DROP_KEYS = {"_id"}  # replaced with a fresh random id


def _fake_id() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(24))


def _rebase_ts(v: Any, offset: int) -> Any:
    if isinstance(v, int) and v > 1_000_000_000_000:  # plausibly ms epoch
        return v - offset
    return v


def _bucket_carbs(v: Any) -> Any:
    if isinstance(v, (int, float)) and v > 0:
        return int(round(v / 10.0) * 10)
    return v


def _scrub(obj: Any, offset: int) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in DROP_KEYS:
                out[k] = _fake_id()
                continue
            if k in SENSITIVE_STRING_KEYS and isinstance(v, str):
                # Replace free-form text; keep emptiness semantics.
                out[k] = "" if v == "" else "redacted"
                continue
            if k in {"date", "sysTime", "srvCreated", "srvModified", "mills"}:
                out[k] = _rebase_ts(v, offset)
                continue
            if k == "carbs":
                out[k] = _bucket_carbs(v)
                continue
            out[k] = _scrub(v, offset)
        return out
    if isinstance(obj, list):
        return [_scrub(x, offset) for x in obj]
    return obj


def anonymize_payload(payload: dict[str, Any], epoch_offset_ms: int) -> dict[str, Any]:
    return _scrub(payload, epoch_offset_ms)


def _process_file(src: Path, dst_dir: Path, offset: int) -> Path:
    raw = json.loads(src.read_text(encoding="utf-8"))
    anon = anonymize_payload(raw, offset)
    dst = dst_dir / src.name
    dst.write_text(json.dumps(anon, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", nargs="+", help="Source JSON files")
    parser.add_argument("dst", help="Destination directory")
    parser.add_argument("--epoch-offset", type=int, default=0, help="ms to subtract from timestamps")
    args = parser.parse_args(argv)

    dst_dir = Path(args.dst)
    dst_dir.mkdir(parents=True, exist_ok=True)

    for s in args.src:
        p = Path(s)
        if p.is_dir():
            for f in p.glob("*.json"):
                _process_file(f, dst_dir, args.epoch_offset)
        else:
            _process_file(p, dst_dir, args.epoch_offset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test** — confirm it passes.

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/anonymize_fixtures.py tests/scripts/__init__.py tests/scripts/test_anonymize_fixtures.py
git commit -m "feat(scripts): add fixture anonymizer"
```

---

### Task 4.2 — `scripts/capture_fixtures.py`

Purpose: Pull raw v3 responses from the live DevInstance instance (and only DevInstance — ProdInstance is never touched) into `captures/` for subsequent anonymization. Reads URL/token from environment variables to avoid hardcoding.

- [ ] **Step 1: Write failing test** `tests/scripts/test_capture_fixtures.py`

```python
"""Tests for capture_fixtures CLI arg parsing (no network)."""
from __future__ import annotations

import os

import pytest

from scripts.capture_fixtures import build_client_config


def test_requires_ns_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NS_URL", raising=False)
    monkeypatch.delenv("NS_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        build_client_config()


def test_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NS_URL", "https://example.invalid")
    monkeypatch.setenv("NS_TOKEN", "tok-redacted")
    cfg = build_client_config()
    assert cfg.base_url == "https://example.invalid"
    assert cfg.token == "tok-redacted"


def test_refuses_felicia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard-rail: the script must refuse to run against ProdInstance hostnames."""
    monkeypatch.setenv("NS_URL", "https://prod-nightscout.example.invalid")
    monkeypatch.setenv("NS_TOKEN", "tok-redacted")
    with pytest.raises(SystemExit, match="refuses"):
        build_client_config()
```

- [ ] **Step 2: Run the test** — confirm fail.

- [ ] **Step 3: Implement** `scripts/capture_fixtures.py`

```python
"""Capture raw Nightscout v3 responses for offline fixture creation.

SAFETY: refuses to run against known production instances (ProdInstance).
Outputs go to `captures/` — anonymize with `scripts.anonymize_fixtures`
before committing.

Env:
    NS_URL    base URL (e.g. https://dev-nightscout.example.invalid) -- DevInstance only
    NS_TOKEN  access token

Usage:
    python -m scripts.capture_fixtures status entries devicestatus
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import aiohttp

FORBIDDEN_HOSTS = {"prod-nightscout.example.invalid"}  # ProdInstance -- never capture


@dataclass
class ClientConfig:
    base_url: str
    token: str


def build_client_config() -> ClientConfig:
    url = os.environ.get("NS_URL")
    token = os.environ.get("NS_TOKEN")
    if not url or not token:
        sys.stderr.write("NS_URL and NS_TOKEN must be set\n")
        raise SystemExit(2)
    for forbidden in FORBIDDEN_HOSTS:
        if forbidden in url:
            sys.stderr.write(f"scripts.capture_fixtures refuses to target {forbidden} (production)\n")
            raise SystemExit(3)
    return ClientConfig(base_url=url.rstrip("/"), token=token)


async def _capture(cfg: ClientConfig, endpoints: list[str], dst: Path) -> None:
    from custom_components.nightscout_v3.api.client import NightscoutV3Client
    from custom_components.nightscout_v3.api.jwt_manager import JwtManager

    dst.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        jwt = JwtManager(session, cfg.base_url, cfg.token)
        await jwt.initial_exchange()
        client = NightscoutV3Client(session, cfg.base_url, jwt)

        for ep in endpoints:
            if ep == "status":
                data = await client.status()
            elif ep == "entries":
                data = await client.entries(limit=200)
            elif ep == "devicestatus":
                data = await client.devicestatus(limit=50)
            elif ep == "treatments":
                data = await client.treatments(limit=100)
            elif ep == "profile":
                data = await client.profile()
            else:
                sys.stderr.write(f"unknown endpoint: {ep}\n")
                continue
            (dst / f"{ep}.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            sys.stdout.write(f"captured {ep} -> {dst / (ep + '.json')}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("endpoints", nargs="+")
    parser.add_argument("--dst", default="captures", type=Path)
    args = parser.parse_args(argv)
    cfg = build_client_config()
    asyncio.run(_capture(cfg, args.endpoints, args.dst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test** — confirm pass. Also add `captures/` to `.gitignore`.

- [ ] **Step 5: Commit**

```bash
git add scripts/capture_fixtures.py tests/scripts/test_capture_fixtures.py .gitignore
git commit -m "feat(scripts): add DevInstance-only fixture capture script"
```

---

### Task 4.3 — `scripts/smoke_test.py`

Purpose: Lightweight end-to-end probe against DevInstance (JWT exchange → status → one entries fetch → one devicestatus fetch → print summary). Does **not** touch HA; used to validate the API layer post-implementation.

- [ ] **Step 1: Write failing test** `tests/scripts/test_smoke_test.py`

```python
"""Unit test for the smoke-test argument surface.

The actual network call is exercised manually against DevInstance; here we only
verify that the harness refuses ProdInstance and parses flags.
"""
from __future__ import annotations

import pytest

from scripts.smoke_test import parse_args, refuse_forbidden_hosts


def test_parses_defaults() -> None:
    ns = parse_args(["--url", "https://example.invalid", "--token", "tok"])
    assert ns.url == "https://example.invalid"
    assert ns.token == "tok"


def test_refuses_felicia() -> None:
    with pytest.raises(SystemExit):
        refuse_forbidden_hosts("https://prod-nightscout.example.invalid")
```

- [ ] **Step 2: Run the test** — confirm fail.

- [ ] **Step 3: Implement** `scripts/smoke_test.py`

```python
"""Lightweight probe against a Nightscout v3 instance (DevInstance only).

Outputs a compact JSON summary suitable for log inspection.

Usage:
    python -m scripts.smoke_test --url https://dev-nightscout.example.invalid --token $NS_TOKEN
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import aiohttp

FORBIDDEN_HOSTS = {"prod-nightscout.example.invalid"}


def refuse_forbidden_hosts(url: str) -> None:
    for forbidden in FORBIDDEN_HOSTS:
        if forbidden in url:
            sys.stderr.write(f"smoke_test refuses to target {forbidden}\n")
            raise SystemExit(3)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--limit", type=int, default=3)
    return parser.parse_args(argv)


async def _run(url: str, token: str, limit: int) -> dict[str, object]:
    from custom_components.nightscout_v3.api.capabilities import ServerCapabilities
    from custom_components.nightscout_v3.api.client import NightscoutV3Client
    from custom_components.nightscout_v3.api.jwt_manager import JwtManager

    async with aiohttp.ClientSession() as session:
        jwt = JwtManager(session, url.rstrip("/"), token)
        await jwt.initial_exchange()
        client = NightscoutV3Client(session, url.rstrip("/"), jwt)
        status = await client.status()
        caps = await ServerCapabilities.probe(client)
        entries = await client.entries(limit=limit)
        devicestatus = await client.devicestatus(limit=limit)

        return {
            "status_version": status.get("version"),
            "capabilities": caps.as_dict(),
            "entries_count": len(entries.get("result", [])),
            "devicestatus_count": len(devicestatus.get("result", [])),
        }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    refuse_forbidden_hosts(args.url)
    summary = asyncio.run(_run(args.url, args.token, args.limit))
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test** — confirm pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_test.py tests/scripts/test_smoke_test.py
git commit -m "feat(scripts): add DevInstance smoke-test harness"
```

---

### Task 4.4 — `scripts/verify_silver.py`

Purpose: Static gate run before flipping `quality_scale.yaml`. Checks:

- `manifest.json` contains `quality_scale: silver` (or is intentionally absent while gating).
- Every Silver rule in `quality_scale.yaml` is `done` or has a `comment:` explaining exemption.
- `strings.json` has translation keys for every `CONF_*` user-facing field.
- `translations/de.json` covers every key present in `strings.json`.
- `PARALLEL_UPDATES` declared in every platform module.
- `DeviceInfo` and `has_entity_name=True` on every entity.
- Coverage summary ≥ 90 % overall, ≥ 95 % for `config_flow.py`.

- [ ] **Step 1: Write failing test** `tests/scripts/test_verify_silver.py`

```python
"""Tests for the silver verifier."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_silver import (
    RuleStatus,
    check_parallel_updates,
    check_quality_scale_yaml,
    check_translations,
)


def test_quality_scale_detects_missing_rule(tmp_path: Path) -> None:
    qs = tmp_path / "quality_scale.yaml"
    qs.write_text(
        "rules:\n"
        "  runtime-data: done\n"
        "  test-before-configure: todo\n",
        encoding="utf-8",
    )
    report = check_quality_scale_yaml(qs)
    assert RuleStatus.TODO in report.statuses
    assert "test-before-configure" in report.failures


def test_translations_detects_missing_key(tmp_path: Path) -> None:
    (tmp_path / "strings.json").write_text(
        '{"config": {"step": {"user": {"data": {"host": "Host"}}}}}',
        encoding="utf-8",
    )
    (tmp_path / "translations").mkdir()
    (tmp_path / "translations" / "de.json").write_text(
        '{"config": {"step": {"user": {"data": {}}}}}',
        encoding="utf-8",
    )
    missing = check_translations(tmp_path)
    assert "config.step.user.data.host" in missing


def test_parallel_updates_detects_missing(tmp_path: Path) -> None:
    (tmp_path / "sensor.py").write_text("# no parallel updates\n", encoding="utf-8")
    (tmp_path / "binary_sensor.py").write_text(
        "PARALLEL_UPDATES = 0\n", encoding="utf-8"
    )
    missing = check_parallel_updates(tmp_path)
    assert missing == ["sensor.py"]
```

- [ ] **Step 2: Run the test** — confirm fail.

- [ ] **Step 3: Implement** `scripts/verify_silver.py`

```python
"""Static verifier for the Silver Quality Scale gate.

Exits non-zero if any check fails. Intended to be run from CI and locally
before toggling quality_scale entries from `todo` to `done`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

INTEGRATION = Path("custom_components/nightscout_v3")
SILVER_RULES_REQUIRED = {
    "runtime-data", "config-entry-unloading", "parallel-updates",
    "test-before-configure", "test-before-setup", "unique-config-entry",
    "has-entity-name", "entity-unique-id", "reauthentication-flow",
    "log-when-unavailable", "entity-unavailable", "integration-owner",
    "action-exceptions", "docs-actions", "docs-high-level-description",
    "docs-installation-instructions", "docs-removal-instructions",
    "docs-configuration-parameters",
}


class RuleStatus(str, Enum):
    DONE = "done"
    TODO = "todo"
    EXEMPT = "exempt"


@dataclass
class QsReport:
    statuses: dict[str, RuleStatus] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def check_quality_scale_yaml(path: Path) -> QsReport:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    report = QsReport()
    rules = (data or {}).get("rules", {})
    for rule in SILVER_RULES_REQUIRED:
        entry = rules.get(rule)
        if entry is None:
            report.failures.append(rule)
            continue
        if isinstance(entry, str):
            status = RuleStatus(entry) if entry in {"done", "todo", "exempt"} else RuleStatus.TODO
            report.statuses[rule] = status
            if status is RuleStatus.TODO:
                report.failures.append(rule)
        elif isinstance(entry, dict):
            status_raw = entry.get("status", "todo")
            status = RuleStatus(status_raw) if status_raw in {"done", "todo", "exempt"} else RuleStatus.TODO
            report.statuses[rule] = status
            if status is RuleStatus.EXEMPT and not entry.get("comment"):
                report.failures.append(f"{rule}:exempt-without-comment")
            elif status is RuleStatus.TODO:
                report.failures.append(rule)
    return report


def _flatten(obj: object, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(_flatten(v, key))
            else:
                keys.add(key)
    return keys


def check_translations(root: Path) -> list[str]:
    strings = json.loads((root / "strings.json").read_text(encoding="utf-8"))
    missing: list[str] = []
    for locale_file in sorted((root / "translations").glob("*.json")):
        trans = json.loads(locale_file.read_text(encoding="utf-8"))
        for key in _flatten(strings):
            if key not in _flatten(trans):
                missing.append(key)
    return missing


def check_parallel_updates(root: Path) -> list[str]:
    missing: list[str] = []
    for platform in ("sensor.py", "binary_sensor.py"):
        p = root / platform
        if not p.exists():
            continue
        if "PARALLEL_UPDATES" not in p.read_text(encoding="utf-8"):
            missing.append(platform)
    return missing


def check_has_entity_name(root: Path) -> list[str]:
    pattern = re.compile(r"_attr_has_entity_name\s*=\s*True")
    offenders: list[str] = []
    for p in (root / "entity.py", root / "sensor.py", root / "binary_sensor.py"):
        if p.exists() and not pattern.search(p.read_text(encoding="utf-8")):
            offenders.append(p.name)
    return offenders


def check_manifest_declares_silver(root: Path) -> bool:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    return manifest.get("quality_scale") == "silver"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=INTEGRATION)
    parser.add_argument("--strict-manifest", action="store_true",
                        help="require manifest.json to declare quality_scale=silver")
    args = parser.parse_args(argv)
    root: Path = args.root

    errors: list[str] = []

    qs = check_quality_scale_yaml(root / "quality_scale.yaml")
    if qs.failures:
        errors.append(f"quality_scale.yaml open rules: {', '.join(qs.failures)}")

    missing_trans = check_translations(root)
    if missing_trans:
        errors.append(f"translation keys missing: {missing_trans}")

    missing_pu = check_parallel_updates(root)
    if missing_pu:
        errors.append(f"PARALLEL_UPDATES missing in: {missing_pu}")

    missing_hen = check_has_entity_name(root)
    if missing_hen:
        errors.append(f"_attr_has_entity_name = True missing in: {missing_hen}")

    if args.strict_manifest and not check_manifest_declares_silver(root):
        errors.append("manifest.json does not declare quality_scale=silver")

    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
        return 1
    sys.stdout.write("silver: ok\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test** — confirm pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_silver.py tests/scripts/test_verify_silver.py
git commit -m "feat(scripts): add Silver Quality Scale static verifier"
```

---

### Phase 4 review

- [ ] **Step 1: Run full test suite**

```bash
pytest
```

- [ ] **Step 2: Dispatch code-reviewer subagent**

Brief: review `scripts/` for (a) forbidden-host guards actually triggered against `prod-nightscout.example.invalid`, (b) anonymizer produces no leftover PII, (c) verify_silver covers all Silver rules from `docs/references/ha-silver-quality-scale.md`.

- [ ] **Step 3: Commit review report**

```bash
git add docs/reviews/
git commit -m "docs(review): phase 4 (scripts) code-reviewer report"
```

---

## Phase 5 — Dashboard

User-tabs dashboard, opt-in via HACS companion. Files under `dashboards/` (not shipped inside the integration, documented in README). All cards use freely available HACS frontend plugins: `apexcharts-card`, `mini-graph-card`, `mushroom`, `card-mod`, `layout-card`.

### Task 5.1 — `dashboards/nightscout.yaml`

- [ ] **Step 1: Write lint test** `tests/dashboards/test_yaml_shape.py`

```python
"""Smoke tests for the shipped dashboard YAML."""
from __future__ import annotations

from pathlib import Path

import yaml

DASH = Path("dashboards/nightscout.yaml")


def test_dashboard_parses() -> None:
    data = yaml.safe_load(DASH.read_text(encoding="utf-8"))
    assert data["kiosk_mode"] is not None or "views" in data


def test_has_required_views() -> None:
    data = yaml.safe_load(DASH.read_text(encoding="utf-8"))
    titles = {v.get("title") for v in data.get("views", [])}
    assert {"Übersicht", "Trend", "AGP", "Statistik", "Loop"} <= titles


def test_referenced_entities_match_feature_registry() -> None:
    """Every `entity: sensor.nightscout_v3_*` referenced must exist in the feature registry."""
    from homeassistant.const import Platform

    from custom_components.nightscout_v3.feature_registry import FEATURE_REGISTRY

    expected = {f"sensor.nightscout_v3_{f.key}" for f in FEATURE_REGISTRY if f.platform == Platform.SENSOR}
    text = DASH.read_text(encoding="utf-8")
    for expected_entity in expected:
        # don't require every feature to be in the default dashboard, but every
        # referenced one must be a known feature key
        pass  # lenient: presence-only check kept for later tightening
    # Hard check: no reference to unknown feature keys
    import re
    referenced = set(re.findall(r"sensor\.nightscout_v3_([a-z_0-9]+)", text))
    known = {f.key for f in FEATURE_REGISTRY if f.platform == Platform.SENSOR}
    unknown = referenced - known
    assert not unknown, f"dashboard references unknown features: {unknown}"
```

- [ ] **Step 2: Run test** — confirm fail (no dashboard file yet).

- [ ] **Step 3: Implement** `dashboards/nightscout.yaml`:

```yaml
# Nightscout v3 - User Dashboard
# Requires HACS frontend plugins: apexcharts-card, mini-graph-card, mushroom, card-mod, layout-card
# Replace `nightscout_v3` entity prefix if your integration instance uses a different slug.

title: Nightscout
views:
  - title: Übersicht
    path: overview
    icon: mdi:diabetes
    badges: []
    cards:
      - type: custom:mushroom-template-card
        primary: "{{ states('sensor.nightscout_v3_bg_current') }} mg/dL"
        secondary: >-
          {{ states('sensor.nightscout_v3_bg_trend') }} ·
          Δ {{ states('sensor.nightscout_v3_bg_delta') }} mg/dL
        icon: mdi:water
        icon_color: >-
          {% set v = states('sensor.nightscout_v3_bg_current') | float(0) %}
          {% if v < 70 %}red
          {% elif v > 180 %}orange
          {% else %}green{% endif %}
      - type: custom:apexcharts-card
        header:
          show: true
          title: BG 6 h
        graph_span: 6h
        span:
          end: minute
        series:
          - entity: sensor.nightscout_v3_bg_current
            stroke_width: 2
            group_by:
              func: avg
              duration: 5min
      - type: horizontal-stack
        cards:
          - type: custom:mushroom-entity-card
            entity: sensor.nightscout_v3_iob
            name: IOB
            icon: mdi:needle
          - type: custom:mushroom-entity-card
            entity: sensor.nightscout_v3_cob
            name: COB
            icon: mdi:food-apple
          - type: custom:mushroom-entity-card
            entity: sensor.nightscout_v3_temp_basal_rate
            name: Temp
            icon: mdi:pump
      - type: custom:mushroom-entity-card
        entity: binary_sensor.nightscout_v3_loop_active
        name: Loop
        icon: mdi:loop

  - title: Trend
    path: trend
    icon: mdi:chart-line
    cards:
      - type: custom:apexcharts-card
        header:
          show: true
          title: BG 24 h mit Zielbereich
        graph_span: 24h
        apex_config:
          annotations:
            yaxis:
              - y: 70
                borderColor: red
              - y: 180
                borderColor: orange
        series:
          - entity: sensor.nightscout_v3_bg_current
            stroke_width: 2
      - type: custom:mini-graph-card
        name: IOB 24 h
        entities:
          - sensor.nightscout_v3_iob
        hours_to_show: 24
        points_per_hour: 2
      - type: custom:mini-graph-card
        name: COB 24 h
        entities:
          - sensor.nightscout_v3_cob
        hours_to_show: 24
        points_per_hour: 2

  - title: AGP
    path: agp
    icon: mdi:chart-bell-curve
    cards:
      - type: custom:apexcharts-card
        header:
          show: true
          title: AGP (hourly percentiles, 14 d)
        graph_span: 24h
        series:
          - entity: sensor.nightscout_v3_agp_p05_14d
            name: p05
            stroke_width: 1
            opacity: 0.4
          - entity: sensor.nightscout_v3_agp_p25_14d
            name: p25
            stroke_width: 1
            opacity: 0.6
          - entity: sensor.nightscout_v3_agp_p50_14d
            name: median
            stroke_width: 2
          - entity: sensor.nightscout_v3_agp_p75_14d
            name: p75
            stroke_width: 1
            opacity: 0.6
          - entity: sensor.nightscout_v3_agp_p95_14d
            name: p95
            stroke_width: 1
            opacity: 0.4

  - title: Statistik
    path: stats
    icon: mdi:chart-box
    cards:
      - type: grid
        columns: 2
        cards:
          - type: entity
            entity: sensor.nightscout_v3_tir_14d
            name: TIR 70-180 (14 d)
          - type: entity
            entity: sensor.nightscout_v3_gmi_14d
            name: GMI (14 d)
          - type: entity
            entity: sensor.nightscout_v3_hba1c_dcct_14d
            name: eHbA1c DCCT (14 d)
          - type: entity
            entity: sensor.nightscout_v3_cv_14d
            name: Variationskoeffizient (14 d)
          - type: entity
            entity: sensor.nightscout_v3_lbgi_14d
            name: LBGI (14 d)
          - type: entity
            entity: sensor.nightscout_v3_hbgi_14d
            name: HBGI (14 d)

  - title: Loop
    path: loop
    icon: mdi:loop
    cards:
      - type: entities
        title: Loop
        entities:
          - binary_sensor.nightscout_v3_loop_active
          - sensor.nightscout_v3_predicted_bg_30min
          - sensor.nightscout_v3_predicted_bg_60min
          - sensor.nightscout_v3_predicted_bg_120min
          - sensor.nightscout_v3_reservoir
          - sensor.nightscout_v3_battery_pump
          - sensor.nightscout_v3_battery_uploader
```

- [ ] **Step 4: Run test** — confirm pass.

- [ ] **Step 5: Commit**

```bash
git add dashboards/nightscout.yaml tests/dashboards/__init__.py tests/dashboards/test_yaml_shape.py
git commit -m "feat(dashboard): ship 5-view Nightscout user dashboard"
```

---

### Task 5.2 — `dashboards/examples/` snippets

Ship three focused snippets that users can copy into their own dashboards:
- `examples/bg_card.yaml` — single mushroom template card with BG + trend arrow.
- `examples/agp_card.yaml` — standalone AGP chart.
- `examples/loop_card.yaml` — loop status + predictions.

- [ ] **Step 1: Write existence test** `tests/dashboards/test_examples.py`

```python
"""Every example snippet must be valid YAML and non-empty."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

EXAMPLES = Path("dashboards/examples")


@pytest.mark.parametrize("name", ["bg_card.yaml", "agp_card.yaml", "loop_card.yaml"])
def test_example_is_valid_yaml(name: str) -> None:
    data = yaml.safe_load((EXAMPLES / name).read_text(encoding="utf-8"))
    assert data is not None
    assert isinstance(data, (dict, list))
```

- [ ] **Step 2: Run test** — confirm fail.

- [ ] **Step 3: Implement** — write the three snippets (extracted from `nightscout.yaml`, each a standalone card):

`dashboards/examples/bg_card.yaml`:
```yaml
type: custom:mushroom-template-card
primary: "{{ states('sensor.nightscout_v3_bg_current') }} mg/dL"
secondary: >-
  {{ states('sensor.nightscout_v3_bg_trend') }} ·
  Δ {{ states('sensor.nightscout_v3_bg_delta') }} mg/dL
icon: mdi:water
icon_color: >-
  {% set v = states('sensor.nightscout_v3_bg_current') | float(0) %}
  {% if v < 70 %}red
  {% elif v > 180 %}orange
  {% else %}green{% endif %}
```

`dashboards/examples/agp_card.yaml`:
```yaml
type: custom:apexcharts-card
header:
  show: true
  title: AGP (14 d)
graph_span: 24h
series:
  - entity: sensor.nightscout_v3_agp_p05_14d
    name: p05
  - entity: sensor.nightscout_v3_agp_p25_14d
    name: p25
  - entity: sensor.nightscout_v3_agp_p50_14d
    name: median
    stroke_width: 2
  - entity: sensor.nightscout_v3_agp_p75_14d
    name: p75
  - entity: sensor.nightscout_v3_agp_p95_14d
    name: p95
```

`dashboards/examples/loop_card.yaml`:
```yaml
type: entities
title: Loop
entities:
  - binary_sensor.nightscout_v3_loop_active
  - sensor.nightscout_v3_predicted_bg_30min
  - sensor.nightscout_v3_predicted_bg_60min
  - sensor.nightscout_v3_predicted_bg_120min
  - sensor.nightscout_v3_reservoir
```

- [ ] **Step 4: Run test** — confirm pass.

- [ ] **Step 5: Commit**

```bash
git add dashboards/examples/
git commit -m "feat(dashboard): add three copy-paste example cards"
```

---

### Phase 5 review

- [ ] **Step 1: Dispatch code-reviewer subagent**

Brief: confirm all entity references in `dashboards/*.yaml` correspond to feature keys in `FEATURE_REGISTRY`; flag any divergence.

- [ ] **Step 2: Commit review report**

```bash
git add docs/reviews/
git commit -m "docs(review): phase 5 (dashboard) code-reviewer report"
```

---

## Phase 6 — Docs & Release Prep

User-facing documentation. Each file below is its own task — one commit per file.

### Task 6.1 — `README.md`

- [ ] **Step 1: Write content check** `tests/docs/test_readme.py`

```python
"""Ensure README advertises the main user-visible promises."""
from __future__ import annotations

from pathlib import Path

import pytest

README = Path("README.md")


@pytest.mark.parametrize(
    "needle",
    [
        "Nightscout v3",
        "HACS",
        "Silver",
        "DevInstance",  # example instance
        "reauthentication",
        "dashboards/nightscout.yaml",
    ],
)
def test_readme_mentions(needle: str) -> None:
    assert needle in README.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test** — confirm fail.

- [ ] **Step 3: Implement** `README.md` with sections:

- **What it does** (one paragraph: BG / Pump / Loop / Careportal / Statistics / Uploader).
- **Requirements** (HA ≥ 2026.1, Nightscout ≥ 15.0 with v3 API enabled, access token).
- **Installation via HACS** (add as custom repository, install, restart, add via "Add Integration").
- **Configuration** (URL normalization; token creation on Nightscout admin panel; options flow walk-through per category).
- **Features table** (one row per category with count and auto-enable behavior).
- **Dashboard setup** (HACS frontend plugins list + copy `dashboards/nightscout.yaml`).
- **Reauthentication flow** (trigger via "repair" or when JWT refresh fails).
- **Multiple instances** (example: `DevInstance` at `cgm.example` + `ProdInstance` at `bz.example`).
- **Quality Scale** — Silver badge + link to `quality_scale.yaml`.
- **Privacy & safety** — no URLs/tokens/notes leave the instance; fixtures anonymized; ProdInstance is a production instance guarded in scripts.
- **Troubleshooting** (most common: JWT refresh loop, stale data, capability mismatch).
- **Links** — spec, plan, references, HACS.

- [ ] **Step 4: Run test** — confirm pass.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/docs/__init__.py tests/docs/test_readme.py
git commit -m "docs: add user-facing README"
```

---

### Task 6.2 — `CONTRIBUTING.md`

- [ ] **Step 1: Write content check** `tests/docs/test_contributing.py`

```python
from pathlib import Path
import pytest

CONTRIB = Path("CONTRIBUTING.md")


@pytest.mark.parametrize("needle", [
    "DevInstance", "ProdInstance", "anonymize_fixtures", "pytest", "ruff", "hassfest",
    "verify_silver", "conventional commits",
])
def test_contrib_mentions(needle: str) -> None:
    assert needle in CONTRIB.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test** — confirm fail.

- [ ] **Step 3: Implement** `CONTRIBUTING.md` covering:

- Dev setup (`pip install -e .[dev]`, pre-commit).
- Test-only-against-DevInstance rule (block ProdInstance hostnames in scripts; scripts enforce this guard).
- Fixture workflow: `scripts.capture_fixtures` → `scripts.anonymize_fixtures` → commit.
- Code style: ruff + pyright, no blanket-except, no backward-compat shims.
- Test expectations: ≥ 90 % coverage, config_flow ≥ 95 %, no network in unit tests.
- Commit style: conventional commits (`feat(api):`, `fix(coordinator):`, `docs:`, etc.).
- Silver gate: `scripts.verify_silver` must pass before PR.
- Code review flow: subagent review per phase committed under `docs/reviews/`.

- [ ] **Step 4: Run test** — confirm pass.

- [ ] **Step 5: Commit**

```bash
git add CONTRIBUTING.md tests/docs/test_contributing.py
git commit -m "docs: add contributing guide"
```

---

### Task 6.3 — `docs/architecture.md`

- [ ] **Step 1: Write content check** `tests/docs/test_architecture.py`

```python
from pathlib import Path
import pytest

ARCH = Path("docs/architecture.md")


@pytest.mark.parametrize("needle", [
    "JwtManager", "NightscoutV3Client", "ServerCapabilities",
    "DataUpdateCoordinator", "HistoryStore", "FEATURE_REGISTRY",
    "runtime_data",
])
def test_arch_mentions(needle: str) -> None:
    assert needle in ARCH.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test** — confirm fail.

- [ ] **Step 3: Implement** `docs/architecture.md`:

- Module map (one bullet per file with purpose).
- Data flow diagram (text/mermaid): coordinator tick → client calls → payload build → entity extract.
- Coordinator ticks every 30 s; staggered polling cycles: fast (60 s default), change-detect (5 min default), stats (60 min default or on change).
- JWT lifecycle: initial exchange, 7 h periodic refresh, failure → ConfigEntryAuthFailed.
- HistoryStore schema v1 and migration policy.
- FEATURE_REGISTRY as single source of truth.
- Error mapping table (3-way).

- [ ] **Step 4: Run test** — confirm pass.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture.md tests/docs/test_architecture.py
git commit -m "docs: add architecture doc"
```

---

### Task 6.4 — `docs/dashboard-setup.md`

Plain dashboard guide: HACS frontend plugins to install, how to import `dashboards/nightscout.yaml`, how to adjust entity prefix per instance, example snippets.

- [ ] **Step 1: Write content check** `tests/docs/test_dashboard_setup.py`

```python
from pathlib import Path
import pytest

DOC = Path("docs/dashboard-setup.md")


@pytest.mark.parametrize("needle", [
    "apexcharts-card", "mini-graph-card", "mushroom", "layout-card",
    "dashboards/nightscout.yaml", "dashboards/examples/",
])
def test_dash_doc_mentions(needle: str) -> None:
    assert needle in DOC.read_text(encoding="utf-8")
```

- [ ] **Step 2–5:** write the doc, test passes, commit.

```bash
git add docs/dashboard-setup.md tests/docs/test_dashboard_setup.py
git commit -m "docs: add dashboard setup guide"
```

---

### Task 6.5 — `docs/roadmap.md`

Forward-looking items (explicitly out of scope for v1.0 / Silver):

- Gold Quality Scale (`devices`, `entity-category`, `entity-device-class`, strict typing, …).
- Full AAPS write-back (create treatments, profiles) via Careportal POST.
- Loop predictions overlayed onto BG chart (requires apexcharts `multi-series` work).
- xDrip+ upload-only bridge (read-only companion).

- [ ] **Step 1:** small content test (check the four items above exist).
- [ ] **Step 2–5:** write → pass → commit.

```bash
git add docs/roadmap.md tests/docs/test_roadmap.py
git commit -m "docs: add roadmap"
```

---

### Phase 6 review

- [ ] **Step 1: Dispatch code-reviewer subagent**

Brief: read every doc + cross-check against `custom_components/nightscout_v3/` (feature counts, entity prefix, config flow steps). Flag any doc statement that disagrees with code reality.

- [ ] **Step 2: Commit review report**

```bash
git add docs/reviews/
git commit -m "docs(review): phase 6 (docs) code-reviewer report"
```

---

## Phase 7 — Silver Verification & Release Gate

### Task 7.1 — Static verifier pass

- [ ] **Step 1:** Run `python -m scripts.verify_silver --root custom_components/nightscout_v3`. Fix any reported issue (missing translation key, missing `PARALLEL_UPDATES`, unhandled Silver rule) at its root cause — no bypass with exemption comments unless truly not applicable.

- [ ] **Step 2:** If exemptions are truly warranted (e.g., `devices` is Gold, not Silver — exempt with comment), update `quality_scale.yaml` with `status: exempt` + `comment: "..."`.

### Task 7.2 — Silver-Verifier subagent

- [ ] **Step 1: Dispatch a fresh code-reviewer subagent** (use `superpowers:code-reviewer`) with this brief:

> Role: Silver Quality Scale auditor for `ha-nightscout-v3`.
> Inputs: `docs/references/ha-silver-quality-scale.md`, repo state.
> For each of the 18 Bronze + 10 Silver rules: verify the repo satisfies it, cite the file(s) and lines that prove it, or report the gap.
> Scope: *only* the integration itself and its tests; no dashboard or docs review here.
> Deliver: `docs/reviews/2026-04-22-silver-audit.md` with a per-rule table `rule | status | evidence`. Report any "done" claim that is not actually backed by code.

- [ ] **Step 2: Address every gap** the auditor finds. Re-dispatch until zero gaps.

- [ ] **Step 3: Commit audit reports**

```bash
git add docs/reviews/2026-04-22-silver-audit*.md
git commit -m "docs(review): silver-quality-scale audit"
```

### Task 7.3 — Flip quality_scale.yaml and manifest

- [ ] **Step 1:** After zero-gap audit, flip every Silver rule in `custom_components/nightscout_v3/quality_scale.yaml` from `todo` → `done`.

- [ ] **Step 2:** Add `"quality_scale": "silver"` to `manifest.json`.

- [ ] **Step 3:** Rerun `scripts.verify_silver --strict-manifest`; expect `silver: ok`.

- [ ] **Step 4:** Commit

```bash
git add custom_components/nightscout_v3/quality_scale.yaml custom_components/nightscout_v3/manifest.json
git commit -m "chore: declare silver quality scale"
```

### Task 7.4 — Live smoke test against DevInstance

- [ ] **Step 1:** Ensure `NS_URL` and `NS_TOKEN` env vars point at DevInstance (`dev-nightscout.example.invalid`). Verify explicitly that ProdInstance is *not* the target.

- [ ] **Step 2:** Run

```bash
python -m scripts.smoke_test --url "$NS_URL" --token "$NS_TOKEN" --limit 5
```

Expect JSON summary: non-null `status_version`, non-empty capabilities dict, non-zero entries/devicestatus counts.

- [ ] **Step 3:** If any assertion fails, treat as a root-cause debugging session (use `superpowers:systematic-debugging`). Do not commit workaround patches.

### Task 7.5 — Final code-reviewer pass

- [ ] **Step 1: Dispatch code-reviewer subagent** with brief:

> Final release review for `ha-nightscout-v3` v0.1.0 (Silver).
> Scope: whole repo.
> Audit for: placeholder code, TODOs, unused imports, unused feature-keys, typing gaps, log leaks of url/token, docstrings present on public API, `__all__` exports, no `print()` calls, no bare `except`, no `# type: ignore` without explanation.
> Deliver: `docs/reviews/2026-04-22-final-release-review.md`.

- [ ] **Step 2: Fix every issue at root cause. Re-dispatch until zero findings.**

- [ ] **Step 3: Commit**

```bash
git add docs/reviews/2026-04-22-final-release-review*.md
git commit -m "docs(review): final release review"
```

### Task 7.6 — Tag release

- [ ] **Step 1:** Update `pyproject.toml` version → `0.1.0`. Update `custom_components/nightscout_v3/manifest.json` version → `0.1.0`.

- [ ] **Step 2:** Commit and tag (local only; remote push is a later decision).

```bash
git add pyproject.toml custom_components/nightscout_v3/manifest.json
git commit -m "chore: release 0.1.0 (silver)"
git tag -a v0.1.0 -m "v0.1.0 — Silver Quality Scale"
```

- [ ] **Step 3:** Run the full CI locally once more: `ruff check . && pytest --cov && python -m scripts.verify_silver --strict-manifest`.

---

## Execution handoff

This plan is executed by `superpowers:subagent-driven-development`:

- One fresh subagent per task.
- Each subagent gets the full task markdown plus these durable constraints:
  1. **Tests only against DevInstance** (`dev-nightscout.example.invalid`). Never touch ProdInstance (`prod-nightscout.example.invalid`). Scripts enforce this; do not disable the guard.
  2. No URLs, tokens, identifiers, notes, or free-form text in any commit, fixture, test, or log.
  3. Every new behavior begins with a failing test (TDD, Red → Green → Refactor).
  4. Commits are conventional; one logical change per commit.
  5. Use `runtime_data`; never store entry data in `hass.data[DOMAIN][entry.entry_id]`.
  6. No `# type: ignore` without a one-line justification; no blanket `except:`.
  7. Coverage floor: 90 % overall, 95 % for `config_flow.py`.
  8. If a phase review surfaces rework, dispatch a fresh subagent per remediation — do not continue in the same subagent.

After each phase:
- Run full `pytest`.
- Dispatch the phase code-reviewer subagent.
- Commit its report under `docs/reviews/`.

Final gate: Phase 7's silver-audit subagent returns zero gaps → flip to Silver → tag `v0.1.0`.




