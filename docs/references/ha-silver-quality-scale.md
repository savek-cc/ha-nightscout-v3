# Home Assistant Integration Quality Scale — Bronze + Silver Reference

> Working reference for `nightscout_v3`. Silver = Bronze + Silver rules (cumulative).
> All URLs and rule IDs verified against the developer docs in April 2026.
> Source index: https://developers.home-assistant.io/docs/core/integration-quality-scale/
> Rule pages: `https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/<rule-id>`

---

## 0. TL;DR — Summary Table

| Rule ID | Tier | One-line | Status hint for nightscout_v3 |
|---|---|---|---|
| `action-setup` | Bronze | Register service actions in `async_setup`, not `async_setup_entry` | **exempt** (initial scope: read-only sensors, no services) — revisit if we add `nightscout.treatment_log` etc. |
| `appropriate-polling` | Bronze | Pick a sensible `update_interval` | **done** — 60 s default, exposed via options flow |
| `brands` | Bronze | Submit logo/icon to `home-assistant/brands` | **todo** — PR required before HACS submission |
| `common-modules` | Bronze | Coordinator in `coordinator.py`, base entity in `entity.py` | **done** — follow the layout exactly |
| `config-flow-test-coverage` | Bronze | 100 % coverage of the config flow | **done** (target) |
| `config-flow` | Bronze | UI setup via `ConfigFlow` + `manifest.json: config_flow: true` | **done** |
| `dependency-transparency` | Bronze | Lib must be OSI-licensed, on PyPI, CI-built, tagged | **done** — we pin our `nightscout_v3_api` helper lib (or depend on existing) |
| `docs-actions` | Bronze | Document every service | **exempt** if no services, else todo |
| `docs-high-level-description` | Bronze | User-doc intro to Nightscout | **todo** — PR to `home-assistant.io` when public, or README for custom-component tier |
| `docs-installation-instructions` | Bronze | Prereqs + step-by-step | **todo** |
| `docs-removal-instructions` | Bronze | How to uninstall | **todo** |
| `entity-event-setup` | Bronze | Subscribe in `async_added_to_hass`, unsub in `async_will_remove_from_hass` | **exempt** unless we subscribe to Nightscout SSE/websocket; coordinator-only entities don't need it |
| `entity-unique-id` | Bronze | `_attr_unique_id` per entity | **done** |
| `has-entity-name` | Bronze | `_attr_has_entity_name = True`, `name=None` for the primary | **done** |
| `runtime-data` | Bronze | Typed `ConfigEntry[NightscoutData]` + `entry.runtime_data` | **done** |
| `test-before-configure` | Bronze | Probe connection in `async_step_user` before creating entry | **done** |
| `test-before-setup` | Bronze | Raise `ConfigEntryNotReady/AuthFailed` in `async_setup_entry` | **done** (via `coordinator.async_config_entry_first_refresh()`) |
| `unique-config-entry` | Bronze | Prevent the same Nightscout instance twice | **done** — `async_set_unique_id(base_url)` or the site UUID |
| `action-exceptions` | Silver | Service actions raise `ServiceValidationError` / `HomeAssistantError` | **exempt** if no services |
| `config-entry-unloading` | Silver | Implement `async_unload_entry`, clean up listeners | **done** |
| `docs-configuration-parameters` | Silver | Doc every options-flow field | **todo** |
| `docs-installation-parameters` | Silver | Doc every initial config-flow field | **todo** |
| `entity-unavailable` | Silver | Mark entities unavailable on fetch failure | **done** (inherited via `CoordinatorEntity`) |
| `integration-owner` | Silver | `codeowners: ["@savek-cc"]` (or multiple) | **done** |
| `log-when-unavailable` | Silver | Log once on down, once on recovery | **done** — coordinator handles it automatically when `UpdateFailed` is raised |
| `parallel-updates` | Silver | Explicit `PARALLEL_UPDATES` in each platform module | **done** — `PARALLEL_UPDATES = 0` on read-only coordinator platforms |
| `reauthentication-flow` | Silver | `async_step_reauth` + `async_step_reauth_confirm` | **done** — required for API secret changes |
| `test-coverage` | Silver | > 95 % coverage across all modules | **done** (target) |

Silver is achievable for `nightscout_v3` with the current design. The realistic effort lives in **tests + docs + reauth**.

---

## 1. Quality Scale YAML file format

Path: `custom_components/nightscout_v3/quality_scale.yaml`

Statuses:
- `done` — fully implemented and validated.
- `todo` — known work item; kept in-tree to signal the gap. hassfest tolerates this.
- `exempt` — rule does not apply; **must** include a `comment:` justification (hassfest will fail on bare `exempt`).

### 1.1 Short form (real NextDNS integration, Platinum — verified verbatim)

```yaml
rules:
  # Bronze
  action-setup:
    status: exempt
    comment: The integration does not register services.
  appropriate-polling: done
  brands: done
  common-modules: done
  config-flow-test-coverage: done
  config-flow: done
  dependency-transparency: done
  docs-actions:
    status: exempt
    comment: The integration does not register services.
  docs-high-level-description: done
  docs-installation-instructions: done
  docs-removal-instructions: done
  entity-event-setup: done
  entity-unique-id: done
  has-entity-name: done
  runtime-data: done
  test-before-configure: done
  test-before-setup: done
  unique-config-entry: done

  # Silver
  action-exceptions:
    status: exempt
    comment: The integration does not register services.
  config-entry-unloading: done
  docs-configuration-parameters:
    status: exempt
    comment: No options to configure.
  docs-installation-parameters: done
  entity-unavailable: done
  integration-owner: done
  log-when-unavailable: done
  parallel-updates: done
  reauthentication-flow: done
  test-coverage: done
```
Source: https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/nextdns/quality_scale.yaml

### 1.2 Exempt rules MUST have a comment

Good:
```yaml
entity-event-setup:
  status: exempt
  comment: >
    Entities of this integration do not subscribe to events; all data is
    pulled through the DataUpdateCoordinator.
```

Bad (hassfest fails):
```yaml
entity-event-setup: exempt   # no comment — rejected
```

### 1.3 Also required in `manifest.json`

To declare the **achieved** tier, add:
```json
{
  "quality_scale": "silver"
}
```
This is only valid once every rule at that tier and below is `done` or `exempt`.

---

## 2. Bronze rules — detail

### 2.1 `action-setup`
**Requires:** Service actions must be registered in `async_setup` (module-level setup called once at HA boot), NOT in `async_setup_entry`. This keeps services available even when config entries aren't loaded yet so automation validation works.

**Implement:**
```python
# __init__.py
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def _handle_action(call: ServiceCall) -> ServiceResponse:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            raise ServiceValidationError("Entry not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Entry not loaded")
        # ... use entry.runtime_data.client
    hass.services.async_register(
        DOMAIN, "log_treatment", _handle_action,
        schema=SERVICE_LOG_TREATMENT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True
```

**Pitfalls:** registering in `async_setup_entry` (services vanish on reload), forgetting to check `entry.state`, raising bare `Exception` instead of `ServiceValidationError`/`HomeAssistantError`.

**Exemption:** integration registers no services.

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup

### 2.2 `appropriate-polling`
**Requires:** The polling interval must match how fast the upstream actually changes.

**Implement (coordinator):**
```python
from datetime import timedelta
class NightscoutCoordinator(DataUpdateCoordinator[NightscoutSnapshot]):
    def __init__(self, hass, client, interval: timedelta) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=interval,  # expose in options flow
        )
```

**Pitfalls:** 5 s polling for data that changes every 5 min; hard-coded interval with no options-flow override.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/appropriate-polling

### 2.3 `brands`
**Requires:** Submit a PR to `home-assistant/brands` with a logo and icon per the README in that repo.

**Implement:** follow https://github.com/home-assistant/brands/blob/master/README.md — put `logo.png` + `icon.png` under `core/nightscout_v3/`.

**Pitfalls:** not reading the size/shape specs; missing dark-mode variant.

**No exemption.** (For pure custom components never submitted to core, this is soft-enforced.)

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/brands

### 2.4 `common-modules`
**Requires:** The coordinator must live in `coordinator.py`; the base entity class in `entity.py`.

**Layout:**
```
custom_components/nightscout_v3/
├── __init__.py
├── config_flow.py
├── const.py
├── coordinator.py        <-- NightscoutCoordinator(DataUpdateCoordinator)
├── entity.py             <-- NightscoutEntity(CoordinatorEntity)
├── manifest.json
├── quality_scale.yaml
├── sensor.py
├── binary_sensor.py
├── strings.json
└── translations/en.json
```

**Pitfalls:** coordinator logic inside `__init__.py`; duplicated boilerplate across `sensor.py`/`binary_sensor.py` instead of a shared `NightscoutEntity`.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/common-modules

### 2.5 `config-flow-test-coverage`
**Requires:** **100 %** coverage of `config_flow.py`. Happy path, every error branch (cannot_connect, invalid_auth, unknown), and duplicate-prevention (`abort:already_configured`). All flow entry points matter: `user`, `reauth`, `reconfigure`, `options`, any discovery sources declared in the manifest.

**Implement — pytest skeleton:**
```python
# tests/test_config_flow.py
from unittest.mock import AsyncMock, patch
from homeassistant.config_entries import SOURCE_USER, SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.nightscout_v3.const import DOMAIN

async def test_user_flow_happy(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"url": "https://ns.example", "api_secret": "s3cret"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

async def test_user_flow_cannot_connect(hass, mock_client) -> None:
    mock_client.get_status.side_effect = NightscoutConnectionError
    # ... assert errors == {"base": "cannot_connect"}
    # then fix the side_effect and prove recovery into CREATE_ENTRY

async def test_user_flow_duplicate(hass, mock_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = ...
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
```

**Pitfalls:** only testing happy path; skipping the recovery-after-error verification the docs explicitly require; not testing `reauth` and `reconfigure` (they also count).

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow-test-coverage

### 2.6 `config-flow`
**Requires:** UI setup. `manifest.json` has `"config_flow": true`. A `ConfigFlow` subclass with `async_step_user` exists. Secrets go in `ConfigEntry.data`; tuneables go in `ConfigEntry.options` via an options flow.

**Implement:**
```python
# config_flow.py
class NightscoutV3ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._probe(user_input)
            except NightscoutAuthError:
                errors["base"] = "invalid_auth"
            except NightscoutConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input["url"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input["url"], data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("url"): str,
                vol.Optional("api_secret"): str,
            }),
            errors=errors,
        )
```

`strings.json` must define `data` (labels) **and** `data_description` (hints — Bronze-level expectation as of 2024+):
```json
{
  "config": {
    "step": {
      "user": {
        "data": {"url": "Nightscout URL", "api_secret": "API secret"},
        "data_description": {
          "url": "Base URL of your Nightscout site (https://...)",
          "api_secret": "The API_SECRET env var you set on the Nightscout server"
        }
      }
    },
    "error": {"cannot_connect": "...", "invalid_auth": "...", "unknown": "..."},
    "abort": {"already_configured": "This Nightscout site is already set up."}
  }
}
```

**Pitfalls:** putting the API secret in `options`; missing `data_description`; not translating every error/abort key.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow

### 2.7 `dependency-transparency`
**Requires:** Every runtime dep listed in `manifest.json: requirements[]` must be (a) OSI-licensed, (b) published to PyPI, (c) built by a public CI pipeline, (d) the PyPI version corresponds to a tagged release in a public repo.

**Implement:** `"requirements": ["nightscout-v3-client==1.2.3"]` where `nightscout-v3-client` meets all four bullets. If we author the client lib, set up GitHub Actions → PyPI trusted publishing with `v1.2.3` tags.

**Pitfalls:** pulling from git URL; pinning a commit hash; private PyPI.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/dependency-transparency

### 2.8 `docs-actions`
**Requires:** Every service registered by the integration is documented (name, purpose, every field, required/optional).

**Implement:** Add to the integration's `home-assistant.io` markdown file using the `action` template, or README section if out-of-core.

**Exemption:** no services.

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-actions

### 2.9 `docs-high-level-description`
**Requires:** User-doc intro: what Nightscout is, who made it, link to https://nightscout.github.io/.

**Exemption:** helper/internal integrations with no external brand.

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-high-level-description

### 2.10 `docs-installation-instructions`
**Requires:** Prereqs (own a Nightscout site, know API_SECRET / JWT token) + the `{% include integrations/config_flow.md %}` snippet in the core docs, or equivalent README section.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-installation-instructions

### 2.11 `docs-removal-instructions`
**Requires:** Explain standard removal + any external cleanup (none for Nightscout). Use the `{% include integrations/remove_device_service.md %}` snippet if in core docs.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-removal-instructions

### 2.12 `entity-event-setup`
**Requires:** Subscribe to events only inside `async_added_to_hass` (after `self.hass`, `self.async_write_ha_state` are valid). Unsubscribe in `async_will_remove_from_hass` OR register cleanup via `self.async_on_remove(...)`.

**Implement:**
```python
async def async_added_to_hass(self) -> None:
    await super().async_added_to_hass()
    self.async_on_remove(
        self.coordinator.client.events.subscribe(
            "treatment", self._handle_treatment
        )
    )
```

**Pitfalls:** subscribing in `__init__`; forgetting `await super().async_added_to_hass()`; manual unsub without cleanup guarantees.

**Exemption:** integration uses only coordinator polling with no push events (valid for Nightscout v1 poll mode — mark `exempt` with a clear comment if we don't wire the SSE/websocket endpoint).

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-event-setup

### 2.13 `entity-unique-id`
**Requires:** `_attr_unique_id` set on every entity, stable across restarts, unique per integration+platform.

**Implement:**
```python
self._attr_unique_id = f"{entry.unique_id}_bg_current"
```

**Pitfalls:** using timestamps or random UUIDs; using the user-set entity name; reusing an ID across platforms.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unique-id

### 2.14 `has-entity-name`
**Requires:** `_attr_has_entity_name = True`. For the entity that **represents the device itself**, set `_attr_name = None` so HA uses the device name directly ("Nightscout DevInstance"). For secondary entities, use a short field name that HA combines with the device ("Nightscout DevInstance BG", "Nightscout DevInstance IOB").

**Implement (base entity):**
```python
# entity.py
class NightscoutEntity(CoordinatorEntity[NightscoutCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entity_description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            name=coordinator.config_entry.title,
            manufacturer="Nightscout Foundation",
            configuration_url=coordinator.client.base_url,
        )
```
Prefer `translation_key=` on the `EntityDescription` + translations instead of `_attr_name` strings.

**Pitfalls:** repeating the device name in the entity name ("Nightscout DevInstance Nightscout BG"); missing `DeviceInfo`.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/has-entity-name

### 2.15 `runtime-data`
**Requires:** Store runtime state on `ConfigEntry.runtime_data` with a typed `ConfigEntry[T]`. No `hass.data[DOMAIN][entry_id]` dicts anymore.

**Implement:**
```python
# coordinator.py or __init__.py
from dataclasses import dataclass
from homeassistant.config_entries import ConfigEntry

@dataclass
class NightscoutData:
    coordinator: NightscoutCoordinator
    client: NightscoutClient

type NightscoutConfigEntry = ConfigEntry[NightscoutData]

# __init__.py
async def async_setup_entry(hass: HomeAssistant, entry: NightscoutConfigEntry) -> bool:
    client = NightscoutClient(entry.data["url"], entry.data.get("api_secret"))
    coordinator = NightscoutCoordinator(hass, client, entry.options.get("scan_interval", 60))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = NightscoutData(coordinator=coordinator, client=client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

**Pitfalls:** continuing to shove things into `hass.data`; not using the typed alias in function signatures (breaks `strict-typing` later); reassigning `runtime_data` mid-lifetime.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data

### 2.16 `test-before-configure`
**Requires:** Before `async_create_entry`, verify the credentials/URL actually connect. Report failures via the `errors` dict — do NOT abort.

**Implement:** see code block under `config-flow` above. Error keys:
- `cannot_connect` — network/DNS/404/500
- `invalid_auth` — 401/403 from Nightscout
- `unknown` — everything else, with `_LOGGER.exception()`

**Pitfalls:** catching only the vendor exception and letting `Exception` escape; raising instead of returning an `errors=` form (user gets no recovery path).

**Exemption:** helper integrations; auto-discovery-only integrations that validate at runtime.

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-configure

### 2.17 `test-before-setup`
**Requires:** During `async_setup_entry`, detect bad state early and raise:
- `ConfigEntryNotReady` — transient (Nightscout down) → HA retries with backoff.
- `ConfigEntryAuthFailed` — bad creds → triggers the reauth flow.
- `ConfigEntryError` — permanent, unrecoverable.

**Implement (idiomatic with coordinator):**
```python
async def async_setup_entry(hass, entry: NightscoutConfigEntry) -> bool:
    coordinator = NightscoutCoordinator(hass, client, ...)
    # This raises ConfigEntryNotReady on UpdateFailed and
    # ConfigEntryAuthFailed if the coordinator raises it. Done for free.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = NightscoutData(coordinator, client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```
In the coordinator's `_async_update_data`:
```python
async def _async_update_data(self) -> NightscoutSnapshot:
    try:
        return await self.client.fetch_snapshot()
    except NightscoutAuthError as err:
        raise ConfigEntryAuthFailed(err) from err
    except NightscoutConnectionError as err:
        raise UpdateFailed(err) from err
```

**Difference vs `test-before-configure`:**
- `test-before-configure` = in the **config flow**, returns `errors` dict, user still editing form.
- `test-before-setup` = in **`async_setup_entry`** at load time, raises exceptions, triggers retries or reauth.

**Pitfalls:** swallowing all exceptions → HA thinks setup succeeded and entities report weird stale data; raising `HomeAssistantError` instead of the three specific types.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-setup

### 2.18 `unique-config-entry`
**Requires:** Prevent the same Nightscout site from being configured twice.

**Implement (preferred — unique id):**
```python
await self.async_set_unique_id(normalized_base_url)  # or site UUID from /status
self._abort_if_unique_id_configured()
```
Must fire **after** you've probed the service (so you know the id is real) and **before** `async_create_entry`.

For the reauth flow, pair with `self._abort_if_unique_id_mismatch()` to stop users from swapping their reauth to a different site.

**Alternative:** `self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})` if no reliable unique id exists.

**Pitfalls:** setting the unique id too late (after `create_entry`); normalizing inconsistently (trailing slash, scheme); skipping this in discovery flows.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/unique-config-entry

---

## 3. Silver rules — detail

### 3.1 `action-exceptions`
**Requires:** Service action handlers must raise:
- `ServiceValidationError` — for bad input (`end_date < start_date`, unknown `entry_id`).
- `HomeAssistantError` — for integration/network failures.

**Implement:**
```python
async def _handle_log_treatment(call: ServiceCall) -> None:
    if call.data["carbs"] < 0:
        raise ServiceValidationError("carbs must be >= 0")
    try:
        await client.post_treatment(call.data)
    except NightscoutConnectionError as err:
        raise HomeAssistantError("Could not reach Nightscout") from err
```

**Pitfalls:** using `HomeAssistantError` for user input mistakes (bad UX), letting raw `Exception` escape.

**Exemption:** no services. With a comment.

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-exceptions

### 3.2 `config-entry-unloading`
**Requires:** `async_unload_entry` must exist AND clean up everything: forward-unload platforms, close clients, cancel background tasks, unsubscribe listeners.

**Implement:**
```python
async def async_unload_entry(hass, entry: NightscoutConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok
```
For simple listener cleanup, `entry.async_on_unload(unsub_cb)` in `async_setup_entry` runs on both unload success and `async_setup_entry` failure.

**Pitfalls:** relying on `entry.async_on_unload` alone — the docs explicitly say this is **not enough**; you still need `async_unload_entry` returning the `async_unload_platforms` result. Not awaiting client close → leaked aiohttp sessions.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-entry-unloading

### 3.3 `docs-configuration-parameters`
**Requires:** Every option exposed by the options flow is documented. In core, use `{% include integrations/option_flow.md %}` + the `configuration_basic` template.

**Exemption:** no options flow. With comment.

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-configuration-parameters

### 3.4 `docs-installation-parameters`
**Requires:** Every initial config-flow field documented with where to find the value (e.g. "API secret: set as `API_SECRET` env var on the Nightscout server; token alternative: generate in Admin Tools"). Use `configuration_basic` template.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-installation-parameters

### 3.5 `entity-unavailable`
**Requires:** If we can't fetch, the entity state is `unavailable`, not a stale value.

**Implement (CoordinatorEntity — free):**
`CoordinatorEntity.available` already returns `self.coordinator.last_update_success`. Just make sure `_async_update_data` raises `UpdateFailed` on connection errors. That's it.

**Override when you need extra conditions:**
```python
@property
def available(self) -> bool:
    return super().available and self.coordinator.data is not None \
        and self.entity_description.key in self.coordinator.data
```

**Exemption:** entities that represent things addressable even when offline (Wake-on-LAN switch, IR blaster) should stay `off`, not `unavailable`. Not relevant for Nightscout.

**Pitfalls:** reading `self.coordinator.data` in `native_value` without guarding against `None`; setting `_attr_available = True` eagerly in `_handle_coordinator_update` and forgetting the error path.

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unavailable

### 3.6 `integration-owner`
**Requires:** `"codeowners": ["@github-handle"]` in `manifest.json`. Multiple owners allowed.

**Implement:**
```json
{
  "domain": "nightscout_v3",
  "name": "Nightscout v3",
  "codeowners": ["@savek-cc"],
  "config_flow": true,
  "documentation": "https://github.com/savek-cc/ha-nightscout-v3",
  "iot_class": "cloud_polling",
  "integration_type": "service",
  "requirements": ["nightscout-v3-client==X.Y.Z"]
}
```

**Pitfalls:** claiming ownership then ignoring issues; wrong `iot_class` (Nightscout is `cloud_polling`).

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/integration-owner

### 3.7 `log-when-unavailable`
**Requires:** Log **once** when the service becomes unavailable and **once** when it recovers — at INFO level. No spam every polling cycle.

**Implement (coordinator — automatic):** `DataUpdateCoordinator` handles this for you. The first `UpdateFailed` logs at WARNING; subsequent failures are silenced; on recovery it logs again. Just make sure `_async_update_data` raises `UpdateFailed` on connection errors (not catches-and-returns-None).

**Implement (non-coordinator entity):** use the flag pattern:
```python
self._unavailable_logged = False

async def async_update(self) -> None:
    try:
        data = await self.client.fetch()
    except NightscoutConnectionError:
        self._attr_available = False
        if not self._unavailable_logged:
            _LOGGER.info("Nightscout is unavailable")
            self._unavailable_logged = True
        return
    if self._unavailable_logged:
        _LOGGER.info("Nightscout recovered")
        self._unavailable_logged = False
    self._attr_available = True
```

**Pitfalls:** logging at WARNING/ERROR on every cycle; catching the exception and never raising `UpdateFailed` so the coordinator's built-in throttling never kicks in.

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/log-when-unavailable

### 3.8 `parallel-updates`
**Requires:** Every platform module (`sensor.py`, `binary_sensor.py`, `switch.py`, ...) sets a module-level `PARALLEL_UPDATES` integer. Value meaning:
- `0` — unlimited (fine when a coordinator already serializes fetches, so all entities share one request)
- `1` — one at a time (typical for write-heavy platforms / fragile devices)
- `N` — custom cap

**Implement (coordinator-backed read-only platforms):**
```python
# sensor.py, binary_sensor.py
PARALLEL_UPDATES = 0
```
**Implement (write platforms — button, switch, number):**
```python
# switch.py
PARALLEL_UPDATES = 1   # serialize writes to Nightscout
```

**Pitfalls:** not setting it at all (hassfest / quality-scale rule fails); setting it inside the class (must be module-level).

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates

### 3.9 `reauthentication-flow`
**Requires:** UI path to update creds without deleting+re-adding the entry. Triggered automatically when `ConfigEntryAuthFailed` is raised in `async_setup_entry` or by the coordinator.

**Implement:**
```python
# config_flow.py
class NightscoutV3ConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            reauth_entry = self._get_reauth_entry()   # HA 2024.x helper
            try:
                await self._probe({
                    "url": reauth_entry.data["url"],
                    "api_secret": user_input["api_secret"],
                })
            except NightscoutAuthError:
                errors["base"] = "invalid_auth"
            except NightscoutConnectionError:
                errors["base"] = "cannot_connect"
            else:
                # Ensure they're reauthing the *same* site
                await self.async_set_unique_id(reauth_entry.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={"api_secret": user_input["api_secret"]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("api_secret"): str}),
            errors=errors,
        )
```
`strings.json` needs `config.step.reauth_confirm.{title,description,data,data_description}`.

**Pitfalls:** forgetting `_abort_if_unique_id_mismatch` → user accidentally rewrites entry with a different account's creds; not using `async_update_reload_and_abort` (manual update + reload is fragile).

**Exemption:** integration has no authentication. With comment.

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow

### 3.10 `test-coverage`
**Requires:** **>95 %** test coverage across the whole integration. `config_flow.py` specifically is **100 %** (rule `config-flow-test-coverage`).

**Implement:** run `pytest` against `tests/components/nightscout_v3/` (core layout) or `tests/` in the custom component. Use `pytest-homeassistant-custom-component` as the runner for out-of-core work. The HA core test harness uses `pytest-cov` under the hood; coverage is measured per file. CI-gate with:
```toml
# pyproject.toml
[tool.coverage.run]
source = ["custom_components.nightscout_v3"]
[tool.coverage.report]
fail_under = 95
exclude_lines = ["if TYPE_CHECKING:", "raise NotImplementedError"]
```

Key fixtures to build in `tests/conftest.py`:
```python
@pytest.fixture
def mock_client():
    client = AsyncMock(spec=NightscoutClient)
    client.get_status.return_value = FAKE_STATUS
    client.get_entries.return_value = FAKE_ENTRIES
    return client

@pytest.fixture
async def init_integration(hass, mock_client) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="https://ns.example",
        data={"url": "https://ns.example", "api_secret": "s3cret"},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.nightscout_v3.coordinator.NightscoutClient",
               return_value=mock_client):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry
```

**Pitfalls:** pinning coverage to `src/` only and missing `coordinator.py`/`entity.py`; using `# pragma: no cover` to paper over the 5 % gap (reviewers will notice).

**No exemption.**

Source: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-coverage

---

## 4. Test patterns reviewers expect at Silver

For a Silver-grade integration, tests must demonstrate each of these is **exercised** (not just present in code):

### 4.1 Config-flow tests (`tests/test_config_flow.py`)
- `test_user_flow_happy` → CREATE_ENTRY
- `test_user_flow_cannot_connect` → FORM with `errors == {"base": "cannot_connect"}`, then recover
- `test_user_flow_invalid_auth` → same pattern
- `test_user_flow_unknown_error` → `errors == {"base": "unknown"}`, with unexpected exception logged
- `test_user_flow_duplicate` → ABORT `already_configured`
- `test_reauth_flow_happy` → ABORT `reauth_successful`, entry data updated
- `test_reauth_flow_invalid_auth` → FORM with error, then recover
- `test_reauth_flow_account_mismatch` → ABORT `unique_id_mismatch`
- `test_options_flow_happy` (if options flow exists)

### 4.2 Setup / unload (`tests/test_init.py`)
```python
async def test_setup_and_unload(hass, init_integration) -> None:
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

async def test_setup_retry_on_connection_error(hass, mock_client) -> None:
    mock_client.get_status.side_effect = NightscoutConnectionError
    entry = MockConfigEntry(...)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY

async def test_setup_triggers_reauth_on_auth_error(hass, mock_client) -> None:
    mock_client.get_status.side_effect = NightscoutAuthError
    entry = MockConfigEntry(...)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)
```

### 4.3 Coordinator / unavailability (`tests/test_coordinator.py`)
```python
async def test_coordinator_unavailable_logs_once(
    hass, init_integration, mock_client, caplog
) -> None:
    mock_client.get_status.side_effect = NightscoutConnectionError
    await _trigger_update(hass, init_integration)
    await _trigger_update(hass, init_integration)   # second failure — must NOT log again
    warnings = [r for r in caplog.records
                if r.levelno == logging.WARNING and "Nightscout" in r.message]
    assert len(warnings) == 1

    # recovery
    mock_client.get_status.side_effect = None
    mock_client.get_status.return_value = FAKE_STATUS
    await _trigger_update(hass, init_integration)
    infos = [r for r in caplog.records if "unavailable" in r.message.lower()]
    # ... assert the "back online" log is emitted
```

### 4.4 Entities (`tests/test_sensor.py`)
- Snapshot test: `assert sensor.state == "7.2"` after coordinator update.
- Unavailable propagation: force `UpdateFailed`, assert `state == STATE_UNAVAILABLE`.
- `unique_id`, `has_entity_name`, `device_info` present.
- `PARALLEL_UPDATES` is set on the platform module (trivial import assertion).

### 4.5 Snapshot tests (optional but recommended)
Use `syrupy` + `snapshot_platform()` fixture (core pattern) to freeze the entity registry, device registry, and state for each platform. Catches regressions in `unique_id` / `name` / `device_class` / `entity_category` cheaply.

---

## 5. Silver readiness checklist for `nightscout_v3`

Map each rule → concrete deliverable in this repo. (✔ = file/PR needed)

**Bronze**
- [ ] `brands` — PR to `home-assistant/brands` with Nightscout logo
- [✔] `appropriate-polling` — `coordinator.py` `update_interval` from options (default 60 s)
- [✔] `common-modules` — `coordinator.py`, `entity.py` present
- [✔] `config-flow` — `config_flow.py` with `async_step_user`, `manifest.json: config_flow: true`, `strings.json` with `data_description`
- [✔] `config-flow-test-coverage` — `tests/test_config_flow.py` covering all branches (100 %)
- [✔] `dependency-transparency` — `requirements: ["nightscout-v3-client==..."]` pinned to a tagged PyPI release
- [ ] `docs-*` — README (or core docs PR) with high-level description, install, removal, action docs
- [—] `entity-event-setup` — **exempt** (coordinator-only) with comment, unless we wire SSE
- [✔] `entity-unique-id` — `f"{entry.unique_id}_{description.key}"`
- [✔] `has-entity-name` — base `NightscoutEntity` sets `_attr_has_entity_name = True`, `DeviceInfo`
- [✔] `runtime-data` — `@dataclass NightscoutData`, `type NightscoutConfigEntry = ConfigEntry[NightscoutData]`
- [✔] `test-before-configure` — connection probe in `async_step_user`
- [✔] `test-before-setup` — `await coordinator.async_config_entry_first_refresh()` in `async_setup_entry`
- [✔] `unique-config-entry` — `async_set_unique_id(normalized_url)` + `_abort_if_unique_id_configured()`
- [—] `action-setup` / `docs-actions` — **exempt** until we add services

**Silver**
- [—] `action-exceptions` — **exempt** with comment, flip to done once services land
- [✔] `config-entry-unloading` — `async_unload_entry` forwards + closes client
- [ ] `docs-configuration-parameters` — option fields (`scan_interval`, `mmol/dl`, target range) documented
- [ ] `docs-installation-parameters` — URL + API secret / token documented
- [✔] `entity-unavailable` — inherited from `CoordinatorEntity`; override `available` where needed
- [✔] `integration-owner` — `"codeowners": ["@savek-cc"]`
- [✔] `log-when-unavailable` — raise `UpdateFailed` in coordinator; HA handles the logging
- [✔] `parallel-updates` — `PARALLEL_UPDATES = 0` in `sensor.py`/`binary_sensor.py`; `= 1` in any write platforms
- [✔] `reauthentication-flow` — `async_step_reauth` + `async_step_reauth_confirm`, raise `ConfigEntryAuthFailed` on 401
- [ ] `test-coverage` — `pyproject.toml` `fail_under = 95`, CI gate

Any rule marked `[—]` (exempt) MUST carry a `comment:` in `quality_scale.yaml` — hassfest will fail otherwise.

---

## 6. Gaps & caveats

- The individual rule pages on `developers.home-assistant.io` do not always quote the exact string constants hassfest looks for. Authoritative validator: `script/hassfest/quality_scale.py` in the core repo — consult if a PR fails the `quality_scale` check.
- `test-coverage` threshold ("above 95 %") comes from the checklist overview page; individual rule page does not restate the number explicitly.
- The `brands` rule has no formal enforcement for HACS-only custom components; treat as "done when we have a logo PR up" for out-of-core lifecycles.
- `config_flow` rule expects `data_description` keys in `strings.json`; this was upgraded from "nice to have" to Bronze expectation circa HA 2024.3 and is not always called out on the rule page itself, but hassfest now warns.
- Some rule pages (`test-coverage`, `log-when-unavailable`) are light on implementation detail; the patterns above come from real Platinum-tier integrations (`nextdns`, `airzone`) inspected in April 2026.

## 7. Real-world quality_scale.yaml references

- NextDNS (Platinum): https://github.com/home-assistant/core/blob/dev/homeassistant/components/nextdns/quality_scale.yaml
- ElevenLabs (partial, shows `todo` + exempt patterns): https://github.com/home-assistant/core/blob/dev/homeassistant/components/elevenlabs/quality_scale.yaml
- Official docs index: https://developers.home-assistant.io/docs/core/integration-quality-scale/
- Rules index: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/
- Checklist overview: https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist
