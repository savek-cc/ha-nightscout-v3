# HA Core Reference Integrations for `nightscout_v3`

Research target: copy idioms from HA-core integrations that share the
nightscout_v3 shape — REST backend, single token / JWT auth with 401-refresh,
one or more `DataUpdateCoordinator`s, multiple entity platforms (sensor,
binary_sensor, number, button), aiming for the Silver Quality Scale.

## Candidate evaluation (why we kept/dropped each)

| Candidate | Kept? | Rationale |
|---|---|---|
| `husqvarna_automower` | YES | Formally **Silver**, with `quality_scale.yaml` in repo. Canonical JWT-bearer + `ConfigEntryAuthFailed` on 401, coordinator, 10 platforms incl. `button`/`number`. Authoritative modern template. |
| `tessie` | YES | Formally **Silver** (`quality_scale.yaml`). Simple static bearer-token auth (no OAuth dance) — closest to how a Nightscout v3 JWT issued from an API secret feels in use. Clean reauth flow, 12 platforms incl. button + number. |
| `github` | YES | Polling, single access-token auth, `runtime_data` dict keyed by repository (a fan-out pattern we may want for multiple Nightscout profiles). Small, readable diagnostics. |
| `nightscout` (HA core) | YES (contextual) | Not a structural template — Bronze, sensor-only, no coordinator. We reference it ONLY for domain-collision handling (`DOMAIN = "nightscout"` already taken) and the existing `hash_from_url` unique-id convention we must coexist with. |
| `airzone_cloud` | no | No `quality_scale.yaml` in repo, quality level unannotated in manifest. Its JWT refresh is handled entirely inside `aioairzone_cloud`, so the HA code doesn't show the refresh pattern we need to copy. Less instructive than husqvarna/tessie. |
| `tailscale` | no | No quality_scale file or manifest entry; only 2 platforms; auth is stateless API-key — nothing husqvarna/tessie don't show better. |
| `whoop` | no | Not present in HA core (`repos/home-assistant/core/contents/homeassistant/components/whoop` returns 404). Skip. |
| `synology_dsm` | no | Still Bronze-in-progress with `config-flow` marked `todo` and critical review comments in their `quality_scale.yaml`. Useful for multi-coordinator ideas but not a Silver template. |
| `fitbit` | no | Bronze-in-progress; most Silver rules marked `todo`. Also OAuth via `application_credentials`, not a fit for our JWT/API-secret model. |
| `octoprint` | no | Local REST, HTTP-Basic, no reauth flow; doesn't exercise JWT/401-refresh path. |

## Primary references (detail)

### 1. Husqvarna Automower — gold-standard Silver-to-Platinum template

- **Repo path**: `homeassistant/components/husqvarna_automower/`
- **Quality Scale**: **Silver** in `manifest.json`; internal `quality_scale.yaml` shows every Silver rule `done` and most Gold rules done, several Platinum done. This is the highest-signal file in the research set.
- **quality_scale.yaml**: https://github.com/home-assistant/core/blob/dev/homeassistant/components/husqvarna_automower/quality_scale.yaml
- **Why it's relevant**: modern (2024+) idioms, JWT bearer, reauth on 401 via `ConfigEntryAuthFailed`, `ConfigEntry[CoordinatorType]` subscripted-generic runtime_data, multiple platforms including `button` and `number` — exactly our shape. Caveat: real-world auth is OAuth2 via `application_credentials`; we strip that layer and inject our own JWT.

**Key files worth copying patterns from**

- `__init__.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/husqvarna_automower/__init__.py)
  - 3-branch exception pattern on first token fetch: `ClientResponseError` → if 4xx `ConfigEntryAuthFailed` else `ConfigEntryNotReady`. Sets `entry.runtime_data = coordinator` (no wrapper dataclass needed when there's one coordinator). Forwards platform setup exactly once at the end.
- `coordinator.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/husqvarna_automower/coordinator.py)
  - `type AutomowerConfigEntry = ConfigEntry[AutomowerDataUpdateCoordinator]` — the PEP-695 alias used across the integration. Clean `_async_update_data` that only needs to distinguish `ApiError` → `UpdateFailed` vs `AuthError` → `ConfigEntryAuthFailed`. For v3, this is the entire 401-refresh contract we need.
- `api.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/husqvarna_automower/api.py) — 45 lines
  - `AsyncConfigEntryAuth(AbstractAuth)` wraps the HA OAuth2 session behind a thin `async_get_access_token()` method; the library consumes that interface. We'll mirror this with a `NightscoutAuth` class that refreshes a JWT from an API secret on 401.
- `config_flow.py` — `async_step_reauth` → `async_step_reauth_confirm` → on success `async_update_reload_and_abort(reauth_entry, data=data)`. This is the exact Silver-grade reauth shape.
- `quality_scale.yaml` — read end-to-end; it's effectively a checklist of what Silver means in April 2026.

---

### 2. Tessie — simplest Silver reference, closest auth model to ours

- **Repo path**: `homeassistant/components/tessie/`
- **Quality Scale**: **Silver** (`manifest.json`), `quality_scale.yaml` present with every Silver rule `done` and most Gold rules done.
- **quality_scale.yaml**: https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/quality_scale.yaml
- **Why it's relevant**: static bearer token authenticates every request; no OAuth2 token endpoint. That's the same mental model as a Nightscout hashed-secret JWT ("token string in header, re-prompt if invalid"). Test suite is compact and readable.

**Key files worth copying patterns from**

- `__init__.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/__init__.py)
  - `type TessieConfigEntry = ConfigEntry[TessieData]` with `TessieData` being a dataclass (`models.py`). Good template for when we want runtime_data to carry `api`, `coordinator`, and e.g. `aiosqlite` connection. Uses `ConfigEntryAuthFailed` / `ConfigEntryNotReady` / `ConfigEntryError(translation_domain=..., translation_key="cannot_connect")` — the three-way pattern.
- `coordinator.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/coordinator.py) lines 75-99
  - The single `_async_update_data` we will crib verbatim: catches `InvalidToken/MissingToken` → `ConfigEntryAuthFailed`, `ClientResponseError` with `status == 401` → `ConfigEntryAuthFailed`, other client errors → `UpdateFailed(translation_domain=..., translation_key="cannot_connect")`.
- `config_flow.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/config_flow.py)
  - `_async_validate_access_token` is a top-level helper reused by `async_step_user` and `async_step_reauth_confirm`. Only ~100 lines total — the minimum-viable reauth-capable config flow.
- `diagnostics.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/diagnostics.py) — 55-line file, uses `async_redact_data` with a literal `REDACT` list per data section. Easy to copy.
- `entity.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/entity.py) — `TessieBaseEntity(CoordinatorEntity[...])` with `_attr_has_entity_name = True`, `_attr_translation_key = key`, and `_async_update_attrs()` abstract hook called from `_handle_coordinator_update`. This is the pattern we adopt for `NightscoutEntity`.

**Tests**

- `tests/components/tessie/conftest.py` — `@pytest.fixture(autouse=True)` with `patch("tesla_fleet_api.tessie.Vehicle.state", new_callable=AsyncMock)` returning canned fixtures. We'll copy this exact shape to fake `py_nightscout` or our own client.
- `tests/components/tessie/test_config_flow.py` — parametrized `test_form_errors` that runs every exception × error-mapping pair in one function; paired `test_reauth` + `test_reauth_errors` covering the full matrix. This is the reference for our own config flow tests.

---

### 3. GitHub — multi-key fan-out with single access token

- **Repo path**: `homeassistant/components/github/`
- **Quality Scale**: no formal Silver tag in manifest or repo file, but the integration is old/stable and follows the Silver idioms; we cite it as a **runtime_data fan-out** example, not as a Silver certification target.
- **Why it's relevant**: `entry.runtime_data` is a `dict[str, GitHubDataUpdateCoordinator]` keyed by repository — directly analogous to if we ever want `dict[str, NightscoutProfileCoordinator]` keyed by Nightscout profile/site. Also good diagnostics example that pulls a live rate-limit call rather than only dumping cached data.

**Key files**

- `__init__.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/github/__init__.py) — `async_cleanup_device_registry` shows how to prune stale devices when the user removes items from options, which we'll need if our options flow lets the user disable sub-features.
- `coordinator.py` (https://github.com/home-assistant/core/blob/dev/homeassistant/components/github/coordinator.py) lines 108 / 138-155 — `type GithubConfigEntry = ConfigEntry[dict[str, GitHubDataUpdateCoordinator]]`; `_async_update_data` splits expected (connection/ratelimit) vs unexpected (`GitHubException`) → both raise `UpdateFailed` but only the unexpected path logs a traceback.
- `diagnostics.py` — returns live rate-limit probe + per-coordinator data. We want the same for Nightscout (e.g. server `/api/v3/status` + last-tick summaries).

---

### 4. `nightscout` (HA core) — coexistence reference only

- **Repo path**: `homeassistant/components/nightscout/`
- **Quality Scale**: Bronze (no quality_scale.yaml, single sensor platform, no coordinator, `entry.runtime_data = api` is just the py_nightscout client object).
- **Why it matters for us**: domain `"nightscout"` is already taken. Our integration must use `DOMAIN = "nightscout_v3"` (or similar), and its unique-id derivation (`hash_from_url(url)` → md5 hex) is something we may want to reproduce so that users migrating from the core integration keep the same `unique_id` if desired. File: https://github.com/home-assistant/core/blob/dev/homeassistant/components/nightscout/utils.py

## Snippet templates (short, load-bearing)

### runtime_data typed dataclass (from Tessie `models.py` shape)

Source: https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/__init__.py#L57
```python
# __init__.py (our version)
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .api import NightscoutClient
from .coordinator import NightscoutCoordinator
from .storage import NightscoutHistoryStore  # aiosqlite wrapper

@dataclass
class NightscoutData:
    client: NightscoutClient
    coordinator: NightscoutCoordinator
    store: NightscoutHistoryStore

type NightscoutConfigEntry = ConfigEntry[NightscoutData]
```

### coordinator `_async_update_data` with auth-refresh on 401

Source (pattern): https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/coordinator.py#L75-L99
```python
# coordinator.py (nightscout_v3)
async def _async_update_data(self) -> NightscoutPayload:
    try:
        return await self.client.fetch_tick()
    except NightscoutAuthError as err:              # 401 after one refresh attempt
        raise ConfigEntryAuthFailed from err
    except ClientResponseError as err:
        if err.status == HTTPStatus.UNAUTHORIZED:   # safety net
            raise ConfigEntryAuthFailed from err
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except (ClientError, TimeoutError) as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
```

### config_flow reauth pair

Source: https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/config_flow.py#L73-L99
```python
async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
    return await self.async_step_reauth_confirm()

async def async_step_reauth_confirm(
    self, user_input: Mapping[str, Any] | None = None
) -> ConfigFlowResult:
    errors: dict[str, str] = {}
    if user_input:
        errors = await _validate_credentials(self.hass, user_input)
        if not errors:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=user_input,
            )
    return self.async_show_form(
        step_id="reauth_confirm",
        data_schema=REAUTH_SCHEMA,
        errors=errors,
    )
```

### Parametrized config_flow error test

Source: https://github.com/home-assistant/core/blob/dev/tests/components/tessie/test_config_flow.py#L90-L127
```python
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (NightscoutAuthError(), {CONF_API_KEY: "invalid_auth"}),
        (asyncio.TimeoutError(), {"base": "cannot_connect"}),
        (ClientError(), {"base": "cannot_connect"}),
        (Exception("boom"), {"base": "unknown"}),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_client_probe: AsyncMock,
    side_effect: BaseException,
    error: dict[str, str],
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_client_probe.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_CONFIG,
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == error
    # Recovery path: clear the side effect and submit again → CREATE_ENTRY.
    mock_client_probe.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], TEST_CONFIG,
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
```

### Entity base class (from Tessie)

Source: https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/entity.py#L22-L67
```python
class NightscoutBaseEntity(CoordinatorEntity[NightscoutCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: NightscoutCoordinator, key: str) -> None:
        self.key = key
        self._attr_translation_key = key
        super().__init__(coordinator)
        self._async_update_attrs()

    def _handle_coordinator_update(self) -> None:
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @abstractmethod
    def _async_update_attrs(self) -> None: ...
```

### Diagnostics (from Tessie)

Source: https://github.com/home-assistant/core/blob/dev/homeassistant/components/tessie/diagnostics.py
```python
REDACT = ["url", "api_secret", "token", "_id", "identifier", "device_name"]

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NightscoutConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data
    return {
        "options": dict(entry.options),
        "coordinator": async_redact_data(data.coordinator.data or {}, REDACT),
        "last_status": async_redact_data(await data.client.server_status_safe(), REDACT),
    }
```

## Gotchas surfaced in review comments / commit history

- **`synology_dsm/quality_scale.yaml`** explicitly calls out patterns not to copy for config flow tests:
  > `test_user` initializes flow with `None` data · imports a fixture that already patches, but then patches again · doesn't continue the old flow but creates a second one · Flows should end in CREATE_ENTRY or ABORT.

  Our tests should always end the flow (CREATE_ENTRY or ABORT), parametrize errors instead of restarting, and patch only where the code under test actually looks up the symbol (prefer patching inside `config_flow` namespace, not the library namespace).
- **`fitbit/quality_scale.yaml`** comment: "consts.py -> const.py · fixture could be autospecced and also be combined with the config flow one · Consider creating a fixture of the mock config entry". We will adopt `MockConfigEntry` fixtures from the start.
- **Tessie `async_set_updated_data`** override in husqvarna's coordinator (lines 148-161): the default impl resets the polling timer on every websocket push; if we ever add push (Nightscout WebSocket), we must likewise override or our scheduled coordinator tick won't fire at the expected cadence. Not immediately relevant but worth pinning.
- **Husqvarna config flow** aborts on `missing_amc_scope` and handles scope mismatch explicitly; lesson is to validate token *capabilities* on setup, not just auth. For Nightscout v3 we should probe `/api/v3/status` to confirm the JWT actually has the roles it claims.

## Patterns we'll adopt for `nightscout_v3`

Checklist with provenance for each line:

- [x] `type NightscoutConfigEntry = ConfigEntry[NightscoutData]` PEP-695 alias  — **husqvarna_automower** (`coordinator.py` line 35) / **tessie** (`__init__.py` line 57)
- [x] `NightscoutData` dataclass holding `client`, `coordinator`, `store` (aiosqlite)  — **tessie** `models.py` shape
- [x] Three-way setup failure: `ConfigEntryAuthFailed` (4xx/invalid token) · `ConfigEntryNotReady` (transient network) · `ConfigEntryError(translation_domain, translation_key)` (unexpected)  — **tessie** `__init__.py` lines 73-83
- [x] Coordinator `_async_update_data` maps `AuthError → ConfigEntryAuthFailed`, `ApiError → UpdateFailed(translation_key="cannot_connect")`, generic client errors also `UpdateFailed`  — **husqvarna_automower** / **tessie** coordinator bodies
- [x] Thin auth class (`NightscoutAuth`) with single `async_get_access_token()` contract, refresh logic lives inside, 401 bubbles up as a typed exception  — **husqvarna_automower** `api.py`
- [x] `async_step_user` + `async_step_reauth` + `async_step_reauth_confirm`, with a shared `_validate_credentials(hass, data) -> dict[str, str]` returning the HA errors dict  — **tessie** `config_flow.py` lines 27-99
- [x] `async_update_reload_and_abort(self._get_reauth_entry(), data=user_input)` on successful reauth  — **tessie** `config_flow.py` line 90
- [x] `CoordinatorEntity[...]` base with `_attr_has_entity_name = True`, `_attr_translation_key = key`, and abstract `_async_update_attrs` called from `_handle_coordinator_update`  — **tessie** `entity.py` lines 22-67
- [x] `diagnostics.py` with a module-level `REDACT` list and `async_redact_data` — **tessie** and **github** both show this
- [x] Diagnostics includes a live server probe (not just cached coordinator.data)  — **github** `diagnostics.py` lines 31-36
- [x] Config-flow tests: parametrize `(side_effect, error)` over every exception the library can raise; always drive the flow to CREATE_ENTRY or ABORT; patch in the namespace where the code looks up the symbol  — **tessie** `test_config_flow.py` + **synology_dsm** review comments
- [x] Test fixtures: `conftest.py` with `autouse=True` AsyncMocks returning canned JSON loaded via `load_json_value_fixture`; one fixture per logical API surface  — **husqvarna_automower** and **tessie** conftests
- [x] For unique-id: if we want compatibility with the core `nightscout` integration, reuse `hashlib.md5(url).hexdigest()` style from its `utils.hash_from_url`  — **nightscout** core `utils.py`
- [x] `DOMAIN = "nightscout_v3"` (or similar) to avoid collision with core `nightscout`
- [x] Full `quality_scale.yaml` file committed from day one, using **husqvarna_automower/quality_scale.yaml** as the structural template (it's the most complete of the researched files)

## References — raw source URLs used

- Husqvarna Automower: https://github.com/home-assistant/core/tree/dev/homeassistant/components/husqvarna_automower/
- Husqvarna tests: https://github.com/home-assistant/core/tree/dev/tests/components/husqvarna_automower/
- Tessie: https://github.com/home-assistant/core/tree/dev/homeassistant/components/tessie/
- Tessie tests: https://github.com/home-assistant/core/tree/dev/tests/components/tessie/
- GitHub: https://github.com/home-assistant/core/tree/dev/homeassistant/components/github/
- Nightscout (core): https://github.com/home-assistant/core/tree/dev/homeassistant/components/nightscout/
- Synology DSM quality_scale (anti-patterns): https://github.com/home-assistant/core/blob/dev/homeassistant/components/synology_dsm/quality_scale.yaml
- Fitbit quality_scale (anti-patterns): https://github.com/home-assistant/core/blob/dev/homeassistant/components/fitbit/quality_scale.yaml
