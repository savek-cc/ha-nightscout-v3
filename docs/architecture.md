# Architecture

How `ha-nightscout-v3` is organized, from the HTTP edge to the HA entity
platform.

## Module map

| File                                               | Purpose                                                                                                           |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `api/auth.py`                                      | `JwtManager` — exchanges the user's access token for a JWT, caches it, refreshes every ~7 h.                      |
| `api/client.py`                                    | `NightscoutV3Client` — thin async HTTP client over `aiohttp`; all requests go through it.                         |
| `api/capabilities.py`                              | `ServerCapabilities` — probes `GET /api/v3/status` and distills supported features.                               |
| `api/exceptions.py`                                | `ApiError`, `AuthError` — two errors crossing every API boundary.                                                 |
| `history_store.py`                                 | `HistoryStore` — async SQLite wrapper backing the stats windows and the change-detect cursor.                     |
| `statistics.py`                                    | Pure-Python BG statistics (mean/SD/CV/GMI/HbA1c/TIR/LBGI/HBGI/hourly profile/AGP percentiles). No IO, no HA deps. |
| `feature_registry.py`                              | `FEATURE_REGISTRY` + `stats_feature_defs(window)` — single source of truth for every entity.                      |
| `coordinator.py`                                   | `NightscoutCoordinator` (a `DataUpdateCoordinator`) — staggered polling cycles, payload assembly.                 |
| `entity.py`                                        | `NightscoutEntity` — base entity with `has_entity_name`, `device_info`, extractor plumbing.                       |
| `sensor.py`, `binary_sensor.py`                    | Platform glue — iterate enabled features, instantiate `NightscoutSensor` / `NightscoutBinarySensor`.              |
| `config_flow.py`                                   | User / reauth / options flows (5 options sub-steps).                                                              |
| `diagnostics.py`                                   | `async_get_config_entry_diagnostics` with `async_redact_data` over `url`, `access_token`, `reason`, `notes`.      |
| `models.py`                                        | `NightscoutRuntimeData` dataclass shipped via `ConfigEntry.runtime_data`.                                         |
| `const.py`                                         | DOMAIN, option keys, defaults, ALLOWED_STATS_WINDOWS.                                                             |
| `__init__.py`                                      | `async_setup_entry` / `async_unload_entry`; wires all of the above.                                               |

## Data flow

```
User token ──► JwtManager ──► NightscoutV3Client
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
           get_entries       get_devicestatus     get_treatments
                 │                  │                  │
                 └──────────────────┼──────────────────┘
                                    ▼
                       ┌────────────────────────┐
                       │  NightscoutCoordinator │
                       │  (DataUpdateCoordinator)│
                       └────────────────────────┘
                                    │
          ┌─────────────┬───────────┼───────────┬─────────────┐
          ▼             ▼           ▼           ▼             ▼
       fast (60 s)  change    stats (60 m)  HistoryStore   capability
       BG / Pump /  detect    compute_all   (SQLite)       rediscovery
       Loop /       (5 min)   per window                   (on-demand)
       Uploader
                                    │
                                    ▼
                       ┌────────────────────────┐
                       │   coordinator.data     │◄──── entity.available
                       │   (nested dict)        │◄──── entity._extract()
                       └────────────────────────┘
                                    │
          ┌─────────────┬───────────┴───────────┬─────────────┐
          ▼             ▼                       ▼             ▼
    NightscoutSensor  (… one per enabled FeatureDef …)  NightscoutBinarySensor
```

## Coordinator timing

The coordinator schedules itself every 30 s and decides per-tick which
cycle(s) to run:

- **fast cycle** (default 60 s): `/entries?limit=2`, `/devicestatus?limit=1`.
- **change-detect cycle** (default 5 min): `/lastModified` — if the
  `devicestatus` or `treatments` cursor moved, mark the stats window dirty.
- **stats cycle** (default 60 min *or* when dirty): pull the window from
  `HistoryStore`, run `compute_all`, persist `payload["agp_summary"]` and
  siblings to the cache. Adds `p5_by_hour`…`p95_by_hour` lists for dashboard
  consumption.

All three intervals are user-adjustable in Options → Polling.

## JWT lifecycle

1. Config flow: user provides token. `JwtManager.exchange_for_jwt` POSTs
   `/api/v2/authorization/request/{token}` (or v3 equivalent) → JWT, expiry.
2. Coordinator setup: JWT stored in memory only (`runtime_data`), never on
   disk. Every client request adds `Authorization: Bearer <jwt>`.
3. Background refresh: if JWT expires in < 30 min, `JwtManager.refresh()` is
   called before the next request.
4. On `401` / `403`: coordinator raises `ConfigEntryAuthFailed` → HA shows
   the reauth flow. User pastes a new token → fresh JWT.

## HistoryStore schema v1

```sql
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sgv         INTEGER NOT NULL,
    date_ms     INTEGER NOT NULL,
    direction   TEXT,
    type        TEXT,
    srv_mod_ms  INTEGER,
    UNIQUE (date_ms, sgv)
);
CREATE INDEX idx_entries_date ON entries(date_ms);

CREATE TABLE IF NOT EXISTS stats_cache (
    window_days INTEGER PRIMARY KEY,
    payload     TEXT NOT NULL,       -- JSON
    computed_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY
);
INSERT OR IGNORE INTO schema_version (version) VALUES (1);
```

Migration policy: additive only. A schema bump writes a new
`schema_version` row and runs `ALTER TABLE` / `CREATE TABLE` statements
idempotently. Never delete or rename columns in a minor release.

## FEATURE_REGISTRY as single source of truth

`FEATURE_REGISTRY` is a `list[FeatureDef]` defined once in
`feature_registry.py`. Every sensor, every option, every diagnostics field,
and every dashboard reference derives from it. Adding a feature means
exactly one commit touching:

- `feature_registry.py` — new `FeatureDef` entry.
- `coordinator.py` — populate the extractor path in `_build_payload`.
- `strings.json` + `translations/*.json` — one name key.
- A test.

Stats entities are expanded programmatically via `stats_feature_defs(window)`
because they're parameterized by window; the mandatory 14 d window is always
present, others are added by the Options flow.

## Error mapping

| Source                              | Raised                       | HA sees                               |
| ----------------------------------- | ---------------------------- | ------------------------------------- |
| aiohttp `ClientConnectionError`     | `ApiError` (status=None)     | `UpdateFailed` (coordinator retry)    |
| HTTP 5xx, malformed JSON            | `ApiError`                   | `UpdateFailed`                        |
| HTTP 401 / 403 / invalid_token      | `AuthError`                  | `ConfigEntryAuthFailed` → reauth flow |
| Capability probe fails on reconfig  | `ConfigEntryNotReady`        | retry with backoff                    |
| Statistics empty window             | `_empty_payload()` (no raise) | zeroed sensors, `available = True`    |

## runtime_data

Per Silver rule `runtime-data`, all per-instance state lives on
`ConfigEntry.runtime_data` (a `NightscoutRuntimeData` dataclass):

```python
@dataclass
class NightscoutRuntimeData:
    client: NightscoutV3Client
    coordinator: NightscoutCoordinator
    capabilities: ServerCapabilities
    jwt_state: JwtState
```

Nothing under `hass.data[DOMAIN][entry.entry_id]`. Unload nukes
`runtime_data` implicitly when HA releases the entry.
