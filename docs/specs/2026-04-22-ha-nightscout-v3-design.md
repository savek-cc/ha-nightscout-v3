# Lastenheft — ha-nightscout-v3

**Datum:** 2026-04-22
**Status:** Brainstorming abgeschlossen, bereit für Implementation-Plan
**Version:** 1.0 (Spec für v1-Release mit Ziel HA Quality Scale Silver)

## 1. Ziel & Kontext

Eine Home-Assistant-Custom-Integration, die über die **Nightscout API v3** den vollen Funktionsumfang einer modernen AAPS-Closed-Loop-Installation in HA abbildet: Live-Blutzucker, IOB/COB, Pumpendaten, Loop-Status, Sensor-Alter, sowie laufend aktualisierte klinische Statistiken (GMI/eHbA1c, Time-in-Range, CV, AGP-Perzentile, Tagesprofil).

**Motivation:** Die Core-HA-Integration `nightscout` liefert nur den aktuellen Blutzucker und nutzt die v1-API. Für Closed-Loop-Nutzer fehlen alle Pumpen-, Loop- und Analytik-Werte. Diese Integration schließt diese Lücke.

**Ziel-Qualität:** HA Quality Scale **Silver**. Implementierung vom ersten Tag an public-release-tauglich; Endziel ist offizielle HACS-Aufnahme. Entwicklung erfolgt zunächst im lokalen Git (kein Push) bis Reife-Status erreicht ist.

## 2. Scope

### In scope (v1)

- Custom-Integration `nightscout_v3` (Domain), koexistent mit Core-`nightscout`
- Beliebig viele Config-Entries (je Entry = eine NS-Instanz / ein Nutzer)
- Nightscout API v3 ausschließlich für Daten-Endpoints; API v2 nur für JWT-Tausch (`/api/v2/authorization/request/<token>`)
- Read-only: alle Sensoren werden aus NS gelesen, keine Write-Operationen
- Feature-Kategorien: BG, Pump, Closed Loop, Careportal (read-only), Statistics, Uploader
- Auto-Capability-Probe beim Setup; Features automatisch aktiviert, sofern vom Server unterstützt
- User kann pro Feature aktivieren/deaktivieren (Options-Flow) → Subset-Steuerung
- Laufende Statistiken mit Default-Fenster 14d und optional 1/7/30/90d
- AGP-Perzentile (5/25/50/75/95) und Tagesprofil als Sensor-Attribut
- Eigenes SQLite-basiertes History-Fenster, unabhängig vom HA-Recorder
- Dashboard-YAML mit Tabs pro Nutzer, basierend auf Community-Cards (`apexcharts-card`, `mini-graph-card`, `mushroom`, `markdown`)
- Diagnostics-Export mit Redaction
- Reauth-Flow
- Vollständige Test-Suite gegen Fixtures
- Übersetzungen DE + EN

### Out of scope (v1 — explizit Non-Goals)

- Eigene Lovelace-Custom-Card (verschoben in v2, separate Build-Toolchain nötig)
- Write-Operationen gegen Careportal (Carbs/Boli/Notes/Announcements — v2)
- Unterstützung für Nightscout-Versionen < 15.0 / API-Version < 3.0
- Alarm-Templates / Notification-Blueprints (kann Community später beisteuern)
- Integration der AAPS-Autotune-Daten als eigene Sensoren
- Unterstützung für Dexcom-G7-spezifische Events (keine klare NS-Repräsentation)

### Zukunft (Roadmap v2+)

- Eigene `<nightscout-v3-card>` Custom Lovelace Card (LitElement, eigenes HACS-Plugin)
- Careportal-Schreib-Services (`add_carbs`, `add_note`, `mark_site_change`, `mark_sensor_change`) mit Safeguards (Max-Grenze, Confirm-Dialog)
- Gold-Scale (translations für alle Fehlertexte, stricter typing, Platinum-ready)

## 3. Architektur

### 3.1 Modulstruktur

```
custom_components/nightscout_v3/
├── __init__.py              # async_setup_entry/async_unload_entry, runtime_data, platforms
├── manifest.json            # domain, version, requirements, iot_class="cloud_polling"
├── const.py                 # Domain, default intervals, feature keys, capability keys
├── api/
│   ├── __init__.py
│   ├── auth.py              # JwtManager: initial exchange + auto-refresh
│   ├── client.py            # NightscoutV3Client: aiohttp-basierter Wrapper
│   ├── capabilities.py      # ServerCapabilities: probe beim Setup
│   └── exceptions.py        # ApiError, AuthError, NotReady
├── coordinator.py           # NightscoutCoordinator (Tick-basiert, gestaffelte Zyklen)
├── history_store.py         # aiosqlite-basierter History-Store
├── statistics.py            # pure-python Auswertungen
├── feature_registry.py      # FEATURE_REGISTRY: category/capability/extractor pro Feature
├── config_flow.py           # User- und Options-Flow, kategorisiert
├── sensor.py                # SensorEntity-Implementierungen
├── binary_sensor.py         # BinarySensorEntity-Implementierungen
├── diagnostics.py           # redacted Diag-Dump
├── entity.py                # NightscoutEntity-Basisklasse (CoordinatorEntity-Erweiterung)
├── strings.json             # Übersetzungs-Quelle (en)
└── translations/
    ├── en.json
    └── de.json

tests/
├── conftest.py              # HA-Fixtures, aioresponses
├── fixtures/                # anonymisierte JSON-Responses
├── test_auth.py
├── test_client.py
├── test_capabilities.py
├── test_statistics.py
├── test_history_store.py
├── test_coordinator.py
├── test_config_flow.py
├── test_init.py
└── test_diagnostics.py

dashboards/
├── nightscout.yaml          # Haupt-Dashboard mit User-Tabs
└── examples/                # einzelne Card-Snippets pro Kategorie

docs/
├── specs/2026-04-22-ha-nightscout-v3-design.md
├── architecture.md
├── quality-scale-silver.md
├── dashboard-setup.md
└── roadmap.md

scripts/
├── smoke_test.py            # manueller Live-Test gegen DevInstance
└── capture_fixtures.py      # Fixture-Aufzeichnung (nur Dev)

.github/
└── workflows/ci.yml
```

### 3.2 Kern-Prinzipien

- **Framework-unabhängige Kerne:** `api/`, `coordinator.py` (bis auf `DataUpdateCoordinator`-Basis), `history_store.py`, `statistics.py`, `feature_registry.py` importieren **kein** HA-Produktionscode außer wo technisch nötig — dadurch unit-testbar ohne HA-Instanz.
- **FEATURE_REGISTRY** ist Single-Source-of-Truth: Welche Features existieren, welche Kategorie, welche Capability, welcher Extractor, welche Platform. Sowohl Config-Flow als auch Entity-Setup lesen daraus.
- **runtime_data** (Silver-Requirement): Config-Entry speichert `runtime_data: NightscoutRuntimeData(client, coordinator, history_store, capabilities)` — kein `hass.data`.
- **Eine Config-Entry = eine Instanz = ein User**. DeviceInfo pro Entry (Name des Users), alle Sensoren an dieses Device gehängt.
- **Public-safe**: Kein Code, keine Config, keine Tests enthalten konkrete Instanz-URLs, Tokens oder personenbezogene Daten. Fixtures sind anonymisiert (fake-Identifier, rund gerundete Werte).

### 3.3 Komponenten-Detail

#### 3.3.1 `api/auth.py` — JwtManager

```
JwtManager(client, access_token)
  async def initial_exchange() -> JwtState
      POST {base}/api/v2/authorization/request/{access_token}
      → speichert jwt + iat + exp

  async def get_valid_jwt() -> str
      if exp - now < refresh_threshold: await refresh()
      return jwt

  async def refresh() -> JwtState
      retry mit exponential backoff (max 5 Versuche, 1s-60s)
      bei 401 → AuthError (löst ConfigEntryAuthFailed aus)
```

Zeitrahmen: JWT-Lifetime beim getesteten Server 8h (28800s). `refresh_threshold = 3600s` (1h vor Ablauf erneuern). Hintergrund-Task `async_track_time_interval(hass, _refresh, 7h)` als zweite Linie zur proaktiven Erneuerung.

#### 3.3.2 `api/client.py` — NightscoutV3Client

```
NightscoutV3Client(session, base_url, jwt_manager)
  async def get_status() -> dict                # /api/v3/status
  async def get_last_modified() -> dict         # /api/v3/lastModified
  async def get_devicestatus(limit=1) -> list
  async def get_entries(limit, since_date=None, before_date=None, lastModified=None) -> list
  async def get_treatments(event_type=None, limit=1, lastModified=None) -> list
  async def get_profile(latest=True) -> dict
```

Alle Methoden:
- Authorization-Header automatisch via `jwt_manager.get_valid_jwt()`
- `aiohttp.ClientTimeout(total=30)`
- Bei 401 → `raise AuthError` (Coordinator macht `ConfigEntryAuthFailed`)
- Bei 5xx oder Timeout → `raise ApiError` (Coordinator macht `UpdateFailed`)
- Response-Validation: nur `status == 200` + `result`-Feld akzeptieren

#### 3.3.3 `api/capabilities.py` — ServerCapabilities

```
ServerCapabilities(
    units: Literal["mg/dl", "mmol/L"],
    has_openaps: bool,                  # → Loop-Category
    has_pump: bool,                     # → Pump-Category
    has_uploader_battery: bool,         # → Uploader-Category
    has_entries: bool,                  # Muss True sein, sonst Setup-Fehler
    has_treatments_sensor_change: bool,
    has_treatments_site_change: bool,
    has_treatments_insulin_change: bool,
    has_treatments_pump_battery_change: bool,
    last_probed_at: datetime,
)

async def probe(client) -> ServerCapabilities
    parallel: status, devicestatus?limit=1, entries?limit=1, treatments je eventType
```

Wird im Config-Flow und im Options-Flow-"Rediscover"-Button aufgerufen. Persistiert in `entry.data["capabilities"]` als Dict (letztbekannter Stand), plus Timestamp.

#### 3.3.4 `history_store.py` — HistoryStore

aiosqlite-Wrapper. Schema siehe Abschnitt 5.1. Public API:

```
async def open(path) -> HistoryStore
async def close()
async def insert_batch(entries_list) -> int  # neu eingefügt
async def entries_in_window(days: int) -> list[dict]
async def get_sync_state(collection) -> SyncState
async def update_sync_state(collection, last_modified, oldest_date)
async def prune(keep_days: int)
async def get_stats_cache(window_days) -> dict | None
async def set_stats_cache(window_days, payload)
async def is_corrupt() -> bool
async def recover_from_corruption() -> Path  # returned backup path
```

Init-Pfad: `Path(hass.config.path(".storage")) / f"nightscout_v3_{entry_id}.db"`. Schema-Migration via `schema_version`-Tabelle (v1 dokumentiert hier, zukünftige Versionen via `migrations/` Sub-Modul).

#### 3.3.5 `statistics.py` — Auswertungen

Pure-Python, keine async, keine IO:

```
def compute_all(entries: list[dict], window_days: int) -> dict:
    return {
        "window_days": window_days,
        "sample_count": n,
        "mean_mgdl": float,
        "sd_mgdl": float,
        "cv_percent": float,
        "gmi_percent": float,           # 3.31 + 0.02392 * mean_mgdl
        "hba1c_dcct_percent": float,    # (mean + 46.7) / 28.7
        "tir_in_range_percent": float,  # 70 ≤ bg ≤ 180 (konfigurierbar)
        "tir_low_percent": float,       # bg < 70
        "tir_very_low_percent": float,  # bg < 54
        "tir_high_percent": float,      # bg > 180
        "tir_very_high_percent": float, # bg > 250
        "lbgi": float,                  # Low Blood Glucose Index
        "hbgi": float,                  # High Blood Glucose Index
        "hourly_profile": list[dict],   # 24 Einträge mit mean/median/min/max/n
        "agp_percentiles": list[dict],  # 24 Einträge × 5 Perzentile (5/25/50/75/95)
        "computed_at_ms": int,
    }
```

Referenzwerte aus ADA/ATTD-Konsensus-Paper werden als Testfixtures genutzt (bekannte Datensätze mit publizierten Erwartungswerten).

#### 3.3.6 `feature_registry.py` — FEATURE_REGISTRY

```python
class Category(StrEnum):
    BG = "bg"
    PUMP = "pump"
    LOOP = "loop"
    CAREPORTAL = "careportal"
    STATISTICS = "statistics"
    UPLOADER = "uploader"

@dataclass(frozen=True)
class FeatureDef:
    key: str
    category: Category
    platform: Platform                  # SENSOR | BINARY_SENSOR
    capability_check: Callable[[ServerCapabilities], bool]
    default_enabled: bool               # wenn capability erfüllt: default an
    translation_key: str
    extractor: Callable[[CoordinatorData], Any]
    device_class: str | None
    state_class: str | None
    unit_of_measurement: str | None
    icon: str | None

FEATURE_REGISTRY: list[FeatureDef] = [ ... ]  # vollständige Liste siehe Abschnitt 4
```

#### 3.3.7 `coordinator.py` — NightscoutCoordinator

Erbt von `DataUpdateCoordinator`. Tick-Basis 30s (konfigurierbar). `_async_update_data()` implementiert gestaffelte Zyklen (siehe Abschnitt 6).

#### 3.3.8 `config_flow.py` — Config- und Options-Flow

Schritte (siehe Abschnitt 7 für Detail-Ablauf).

### 3.4 Domain-Name und Unique-ID-Strategie

- Domain: `nightscout_v3`
- Config-Entry `unique_id`: SHA-256 der normalisierten URL (ersten 16 Hex-Zeichen) → verhindert Dubletten
- Entity `unique_id`: `{entry.entry_id}_{feature_key}` → eindeutig global
- DeviceInfo `identifiers`: `{(DOMAIN, entry.entry_id)}`

## 4. Features — Vollständige Liste

Alle Features sind über `FEATURE_REGISTRY` konfigurierbar. "Default enabled" gilt nur, wenn die Capability vom Server erfüllt wird.

### 4.1 Kategorie BG (Blood Glucose)

| Feature-Key | Platform | Beschreibung | Quelle | Einheit |
|---|---|---|---|---|
| `bg_current` | sensor | Aktueller Blutzucker | entries[0].sgv | mg/dL oder mmol/L (units) |
| `bg_delta` | sensor | Differenz zum vorletzten SGV | entries[0]-entries[1] | mg/dL |
| `bg_direction` | sensor | Trend-Label ("Flat", "FortyFiveUp" ...) | entries[0].direction | - |
| `bg_trend_arrow` | sensor | Unicode-Pfeil für Dashboards | abgeleitet | - |
| `bg_stale_minutes` | sensor | Minuten seit letztem Entry | now - entries[0].date | min |

### 4.2 Kategorie PUMP

| Feature-Key | Beschreibung | Quelle |
|---|---|---|
| `pump_reservoir` | Reservoir-Units | devicestatus.pump.reservoir |
| `pump_battery` | Pumpenbatterie % | devicestatus.pump.battery.percent |
| `pump_status` | Statustext (Closed Loop / Open Loop / Disconnect) | devicestatus.pump.status.status |
| `pump_base_basal` | aktuelle Grundrate U/h | devicestatus.pump.extended.BaseBasalRate |
| `pump_temp_basal_rate` | aktive Temp-Basalrate U/h | abgeleitet aus Treatments oder extended |
| `pump_temp_basal_remaining` | Restzeit Temp-Basal | devicestatus.pump.extended.TempBasalRemaining |
| `pump_active_profile` | aktives AAPS/Profil-Name | devicestatus.pump.extended.ActiveProfile |
| `pump_last_bolus_time` | Zeitstempel letzter Bolus | devicestatus.pump.extended.LastBolus |
| `pump_last_bolus_amount` | Menge letzter Bolus (U) | devicestatus.pump.extended.LastBolusAmount |

### 4.3 Kategorie LOOP (Closed Loop — OpenAPS-Block)

| Feature-Key | Beschreibung | Quelle |
|---|---|---|
| `loop_mode` | Loop-Modus ("Closed" / "Open" / "Suspended") | abgeleitet |
| `loop_active` (binary) | Loop läuft? | devicestatus-Alter < 10 min + openaps present |
| `loop_eventual_bg` | Prognostizierter BG | openaps.suggested.eventualBG |
| `loop_target_bg` | Zielwert | openaps.suggested.targetBG |
| `loop_iob` | Insulin on Board | openaps.iob.iob |
| `loop_basaliob` | Basal-IOB | openaps.iob.basaliob |
| `loop_activity` | Insulin-Aktivität | openaps.iob.activity |
| `loop_cob` | Carbs on Board | openaps.suggested.COB |
| `loop_sensitivity_ratio` | Autosens-Ratio | openaps.suggested.sensitivityRatio |
| `loop_reason` | AAPS-Entscheidungstext | openaps.suggested.reason |
| `loop_pred_bgs` | Prediction-Arrays (IOB/COB/ZT) als Attribut | openaps.suggested.predBGs |
| `loop_last_enacted_age_minutes` | Minuten seit letzter Loop-Enact | devicestatus.created_at |

### 4.4 Kategorie CAREPORTAL (read-only)

| Feature-Key | Beschreibung | Quelle |
|---|---|---|
| `care_sage_days` | Sensor-Alter Tage | treatments?eventType$eq=Sensor+Change&limit=1 |
| `care_iage_days` | Insulin-Alter (Patrone) Tage | treatments?eventType$eq=Insulin+Change |
| `care_cage_days` | Katheter-Alter Tage | treatments?eventType$eq=Site+Change |
| `care_bage_days` | Pumpen-Batterie Alter Tage | treatments?eventType$eq=Pump+Battery+Change |
| `care_last_meal_carbs` | letzte angekündigte Carb-Menge (g) | treatments?eventType$in=[Meal+Bolus,Carbs] |
| `care_carbs_today` | Summe Carbs heute (g) | treatments der letzten 24h |
| `care_last_note` | Letzte Notiz/Announcement | treatments?eventType$in=[Note,Announcement] |

### 4.5 Kategorie STATISTICS (pro aktiviertem Fenster)

Für jedes aktivierte Fenster aus `options.stats_windows` (Pflicht: 14, optional: 1/7/30/90) werden diese Sensoren angelegt:

| Feature-Key-Pattern | Beschreibung |
|---|---|
| `stat_gmi_{w}d` | GMI / eHbA1c (%) |
| `stat_tir_in_range_{w}d` | TIR 70-180 (%) |
| `stat_tir_low_{w}d` | % unter 70 |
| `stat_tir_very_low_{w}d` | % unter 54 |
| `stat_tir_high_{w}d` | % über 180 |
| `stat_tir_very_high_{w}d` | % über 250 |
| `stat_mean_{w}d` | Mittelwert (mg/dL) |
| `stat_sd_{w}d` | Standardabweichung |
| `stat_cv_{w}d` | Variationskoeffizient (%) |
| `stat_lbgi_{w}d` | Low Blood Glucose Index |
| `stat_hbgi_{w}d` | High Blood Glucose Index |
| `stat_hourly_profile_{w}d` | 24h-Mittelwerte als Attribut |
| `stat_agp_{w}d` | Perzentil-Bands als Attribut |

### 4.6 Kategorie UPLOADER

| Feature-Key | Beschreibung | Quelle |
|---|---|---|
| `uploader_battery` | Handy-Batterie % | devicestatus.uploaderBattery oder pump.battery |
| `uploader_online` (binary) | Handy-Upload aktiv (letzter devicestatus < 15 min) | abgeleitet |
| `uploader_charging` (binary) | Lädt gerade? | devicestatus.isCharging |

## 5. Datenmodell & Persistenz

### 5.1 HistoryStore-Schema

```sql
CREATE TABLE schema_version (version INTEGER PRIMARY KEY) WITHOUT ROWID;
INSERT INTO schema_version VALUES (1);

CREATE TABLE entries (
    identifier   TEXT PRIMARY KEY,
    date         INTEGER NOT NULL,
    sgv          INTEGER NOT NULL,
    direction    TEXT,
    type         TEXT NOT NULL,
    noise        INTEGER,
    srv_modified INTEGER NOT NULL
) WITHOUT ROWID;
CREATE INDEX idx_entries_date ON entries(date DESC);

CREATE TABLE sync_state (
    collection     TEXT PRIMARY KEY,
    last_modified  INTEGER NOT NULL,
    oldest_date    INTEGER NOT NULL,
    newest_date    INTEGER NOT NULL,
    updated_at_ms  INTEGER NOT NULL
) WITHOUT ROWID;

CREATE TABLE stats_cache (
    window_days  INTEGER NOT NULL,
    computed_at  INTEGER NOT NULL,
    payload      TEXT NOT NULL,
    PRIMARY KEY (window_days)
) WITHOUT ROWID;
```

Pfad: `<hass_config>/.storage/nightscout_v3_<entry_id>.db`

### 5.2 Config-Entry-Struktur

```python
entry.data = {
    "url": str,
    "access_token": str,
    "capabilities": dict,    # letzter Stand des Probings
    "capabilities_probed_at": int,  # ms epoch
}
entry.options = {
    "enabled_features": {feature_key: bool, ...},
    "stats_windows": [14, 30, ...],         # 14 ist Pflicht
    "tir_low_threshold_mgdl": 70,
    "tir_high_threshold_mgdl": 180,
    "tir_very_low_threshold_mgdl": 54,
    "tir_very_high_threshold_mgdl": 250,
    "poll_fast_seconds": 60,
    "poll_change_detect_minutes": 5,
    "poll_stats_minutes": 60,
}
entry.unique_id = sha256(normalized_url)[:16]
```

### 5.3 Runtime-Data

```python
@dataclass
class NightscoutRuntimeData:
    client: NightscoutV3Client
    coordinator: NightscoutCoordinator
    history_store: HistoryStore
    capabilities: ServerCapabilities
    jwt_manager: JwtManager
    jwt_refresh_unsub: Callable  # unsub für async_track_time_interval

entry.runtime_data: NightscoutRuntimeData
```

## 6. Datenfluss

### 6.1 Setup

```
async_setup_entry(entry)
  1. client = NightscoutV3Client(aiohttp_session, entry.data.url)
  2. jwt_manager = JwtManager(client, entry.data.access_token)
     await jwt_manager.initial_exchange()
         → on 401: ConfigEntryAuthFailed
         → on network: ConfigEntryNotReady
  3. capabilities = await ServerCapabilities.probe(client)
     → update entry.data["capabilities"]
  4. history_store = await HistoryStore.open(hass.config.path(...))
     if is_first_setup or store is empty:
         backfill_task = asyncio.create_task(backfill(client, store, max_window))
  5. coordinator = NightscoutCoordinator(hass, client, capabilities, history_store, entry)
     await coordinator.async_config_entry_first_refresh()
  6. jwt_refresh_unsub = async_track_time_interval(hass, _refresh_jwt, 7h)
  7. entry.runtime_data = NightscoutRuntimeData(...)
  8. await hass.config_entries.async_forward_entry_setups(entry, [SENSOR, BINARY_SENSOR])
  9. entry.async_on_unload(entry.add_update_listener(_async_update_listener))
```

### 6.2 Coordinator-Tick (30s)

```
_async_update_data():
    tick += 1
    if tick % 2 == 0:     # alle 60s
        await _fast_cycle()      # devicestatus + entries
    if tick % 10 == 0:    # alle 5 min
        await _change_detect_cycle()  # lastModified → ggf Treatments, history incremental
    if stats_dirty or tick % 120 == 0:  # alle 60 min oder wenn geänderte Entries
        await _stats_cycle()     # recompute all enabled windows
    return self._build_coordinator_data()
```

### 6.3 JWT-Refresh-Strategie

- Proaktiv: `async_track_time_interval(hass, _refresh, timedelta(hours=7))` — unabhängig von Coordinator-Tick
- Reaktiv: `JwtManager.get_valid_jwt()` refresht auch on-demand wenn `exp - now < 3600s`
- Bei Fehler: exponential backoff (1s, 2s, 4s, 8s, 16s, 32s, 64s → max 5 retries)
- Nach 5 konsekutiven Fehlern: `ConfigEntryAuthFailed` → HA zeigt "Reparieren"-Karte

### 6.4 Unload / Reload

```
async_unload_entry(entry):
    entry.runtime_data.jwt_refresh_unsub()
    await entry.runtime_data.coordinator.async_shutdown()
    await entry.runtime_data.history_store.close()
    return await hass.config_entries.async_unload_platforms(entry, [...])
```

`async_update_listener` auf Options-Flow-Änderungen: Reload via `hass.config_entries.async_reload(entry.entry_id)`.

## 7. Config-Flow

### 7.1 User-Flow (neue Instanz)

| Step | Input | Aktion |
|---|---|---|
| `user` | `url`, `access_token` | Normalisierung, URL-Validierung, dedup via unique_id |
| `user` | - | JWT-Exchange testen (`test-before-configure`-Rule) |
| `user` | - | Capabilities probing |
| `detected` | Zusammenfassung der gefundenen Features | Bestätigungsdialog: "Alle X verfügbaren Features aktivieren?" [Ja] → direkt create-entry / [Anpassen] → Step `customize` |
| `customize` | Pro Kategorie Checkbox-Gruppe | User wählt Subset |
| `stats` | Stats-Fenster (14d fest + Checkboxen für 1/7/30/90d) | Auswahl |
| `finish` | - | `async_create_entry(title=title, data={url, access_token, capabilities}, options={enabled_features, stats_windows, thresholds})` |

### 7.2 Options-Flow

| Step | Aktion |
|---|---|
| `init` | Menu: "Features anpassen" / "Statistik-Fenster" / "TIR-Grenzen" / "Polling-Intervalle" / "Server-Fähigkeiten neu prüfen" |
| `rediscover` | Führt Capabilities-Probe erneut aus, zeigt Diff (neu verfügbar / weggefallen) |

### 7.3 Reauth-Flow

Bei `ConfigEntryAuthFailed`: HA zeigt "Reparieren"-Karte. Reauth-Step fragt nur nach neuem `access_token` (URL bleibt aus `entry.data`). Nach erfolgreichem JWT-Exchange: `async_update_entry` mit neuem Token.

## 8. Fehlerbehandlung

### 8.1 Fehlerkategorien

| Fehler | HA-Auswirkung |
|---|---|
| 401 beim JWT-Exchange (Token ungültig) | `ConfigEntryAuthFailed` → Reauth |
| 404 / 5xx beim Probing im Setup | `ConfigEntryNotReady` → HA retried automatisch (exp. backoff) |
| Netzwerk-Timeout im Coordinator-Tick | `UpdateFailed` → Sensoren zeigen letzten Wert + `available` basierend auf `last_update_success` |
| 401 während Betrieb (Token vom User rotiert) | `ConfigEntryAuthFailed` via Coordinator → Reauth |
| HistoryStore corrupt (Schema/File-Error) | Backup + Neu-Init + Backfill (logged Warning, kein Fehler-Propagate) |
| Statistik-Compute-Exception | Log-Exception, stats_cache bleibt letztgültig, Sensor zeigt alten Wert + `available = True` |
| Fehlender `devicestatus` (Uploader-Pause) | Live-Sensoren der Kategorien PUMP/LOOP werden `unavailable`, BG bleibt aus `entries` verfügbar |

### 8.2 Verfügbarkeits-Semantik pro Sensor

Sensor ist `available = False` wenn:
- Coordinator hat seit 3 Ticks keinen Erfolg (keine Live-Daten mehr)
- ODER: Sensor liest aus `devicestatus` und letzter devicestatus-Record ist älter als 15 min
- ODER: Sensor ist ein Stats-Sensor und `stats_cache` ist noch nie befüllt worden (Backfill läuft noch)
- ODER: Sensor ist `care_*age_days` und der entsprechende eventType hat keinen Treatment-Record

### 8.3 Retry- und Backoff-Regime

- JWT-Refresh: 1s, 2s, 4s, 8s, 16s, 32s, 64s, max 5 Versuche
- Fast-Cycle: Coordinator macht normalen `UpdateFailed`; HA retry via `async_request_refresh`
- Backfill: bei Fehler pausiert, retry nach 60s, max 10 Versuche; danach log + Sensor `unavailable` bis manueller Options-Flow-Reset

### 8.4 Logging-Regeln

- `_LOGGER.debug` darf BG/IOB/COB-Werte enthalten (Diag)
- `_LOGGER.info/warning/error` **niemals** medizinische Werte
- **Niemals** URL oder Token in Log-Zeilen (ein `RedactingLogger`-Filter ergänzt diese Disziplin)
- `_LOGGER.exception` darf Tracebacks; aber kein `repr(response.text)` das Werte enthielte

## 9. Diagnostik (Silver-Requirement)

`diagnostics.async_get_config_entry_diagnostics(hass, entry)` liefert einen redacted-Dump. `TO_REDACT = {"url", "access_token", "api_secret", "identifier"}`. Enthält:

- Entry-Metadaten (ohne Secrets)
- JWT-Manager-Status (exp_in, letzter Refresh, fehlende Refreshes)
- Coordinator-Status (tick_count, cycle timings, last_update_success)
- HistoryStore-Status (entries_count, oldest/newest, DB-Size)
- Live-Snapshot (aktueller Coordinator-Data nach Redaction)
- Capabilities (letzter Probe-Stand)

## 10. Dashboard

`dashboards/nightscout.yaml` liefert ein Dashboard mit einem Tab pro Config-Entry (User). Platzhalter für User-IDs, nicht hart-codiert.

### 10.1 Pro-Tab-Layout (Skizze)

```
┌─────────────────────────────────────┐
│  Current BG    │  Trend-Arrow       │
│   183 mg/dl    │       ↗            │
│   +5 delta     │   4 min ago        │
├─────────────────────────────────────┤
│ IOB: 2.5 U    COB: 23.8 g          │
│ Loop: Closed  eventualBG: 104      │
│ Sensitivity: 1.0   Active: Normal  │
├─────────────────────────────────────┤
│   [BG Chart — 24h line + forecast] │ ← apexcharts-card
│                                     │
├─────────────────────────────────────┤
│ Pump   │ Sensor │ Insulin │ Phone  │
│ 97U    │  13.0d │  6.7d   │  39%   │
│ 25%    │        │         │        │
├─────────────────────────────────────┤
│  eHbA1c 14d: 6.57%                 │
│  TIR 87%  | Low 0%  | High 13%     │
│  CV 34%   | Mean 136 mg/dl         │
├─────────────────────────────────────┤
│   [AGP-Perzentile-Chart 14d]        │
│   5/25/50/75/95 bands, hourly       │
└─────────────────────────────────────┘
```

### 10.2 Cards-Setup

- `apexcharts-card` für BG-Verlauf + Forecast (aus `loop_pred_bgs`-Attribut via `data_generator`)
- `apexcharts-card` für AGP (aus `stat_agp_14d`-Attribut)
- `mini-graph-card` für die einzelnen Stats-Trends
- `mushroom-template-card` für die Kacheln (Pump/Sensor/Insulin/Phone)
- `markdown` für die Live-Zeile (IOB/COB/Loop/Target)

Tabs via `views`-Array mit einem View pro Config-Entry (Title = DeviceInfo-Name).

## 11. Testing-Strategie

### 11.1 Test-Pyramide

| Ebene | Umfang | Werkzeuge |
|---|---|---|
| Unit | `api/*`, `coordinator`, `history_store`, `statistics`, `feature_registry`, `auth` | pytest + pytest-asyncio + aioresponses |
| Integration HA | `config_flow`, `options_flow`, `async_setup_entry`/unload/reload, reauth, diagnostics | pytest-homeassistant-custom-component |
| Regression Statistics | eA1c/TIR/Perzentile gegen publizierte Referenzdatensätze | bekannte AGP-Beispiele aus ATTD-Konsensus |
| Live-Smoketest (manuell) | nur gegen DevInstance, NICHT in CI | `scripts/smoke_test.py` |

### 11.2 Fixtures

Alle Test-Fixtures unter `tests/fixtures/` sind **anonymisierte Roh-Responses**. Sanitizer-Regel: Identifier durch UUID-Platzhalter ersetzt, `device` auf `"aaps-android-test"` normalisiert, Uploader-Namen entfernt.

Fixtures werden mit `scripts/capture_fixtures.py` (nur Dev) erzeugt — erwartet `TEST_INSTANCE_URL` und `TEST_INSTANCE_TOKEN` als Umgebungsvariablen, der User ruft das manuell gegen DevInstance auf. Die generierten Files werden vor Commit durch `scripts/anonymize_fixtures.py` gepushte, das Identifier-Felder regeneriert.

### 11.3 Coverage-Ziele

- Überall >=90%
- `config_flow.py`, `auth.py`: 100% (Silver-Pflichtfelder)

## 12. HA Quality Scale Silver — Checkliste

Die Silver-Level-Regeln aus `developers.home-assistant.io/docs/core/integration-quality-scale/rules/` werden in `docs/quality-scale-silver.md` geführt und per Subagent verifiziert.

**Bronze-Vorraussetzungen** (müssen erfüllt sein):

- [ ] `action-setup`: n/a (keine Services in v1)
- [ ] `appropriate-polling`: fast=60s, change-detect=5min, stats=60min, alle begründet
- [ ] `brands`: PR gegen home-assistant/brands (non-blocker für lokale Dev)
- [ ] `common-modules`: `coordinator.py` und `entity.py` als Basis
- [ ] `config-flow`: mit `data_description`, Validation pro Step
- [ ] `config-flow-test-coverage`: 100% der Flow-Pfade
- [ ] `dependency-transparency`: `manifest.json` mit gepinnten Versions
- [ ] `docs-actions`: n/a (v1)
- [ ] `docs-high-level-description`: README mit Zweck der Integration
- [ ] `docs-installation-parameters`: README mit Config-Parametern
- [ ] `docs-installation-instructions`: README + HACS-Anweisungen
- [ ] `docs-removal-instructions`: README
- [ ] `entity-event-setup`: Keine Event-Listener-Leaks (alles mit `async_on_unload`)
- [ ] `entity-unique-id`: `{entry_id}_{feature_key}`
- [ ] `has-entity-name`: `_attr_has_entity_name = True`
- [ ] `runtime-data`: `entry.runtime_data` statt `hass.data`
- [ ] `test-before-configure`: Config-Flow testet Auth
- [ ] `test-before-setup`: Setup macht Probe und wirft `ConfigEntryNotReady` bei transienten Fehlern
- [ ] `unique-config-entry`: `_abort_if_unique_id_configured()`

**Silver-spezifisch**:

- [ ] `action-exceptions`: n/a (keine Services)
- [ ] `config-entry-unloading`: `async_unload_entry` komplett implementiert
- [ ] `docs-configuration-parameters`: alle Options dokumentiert
- [ ] `docs-installation-parameters`: dito
- [ ] `entity-unavailable`: Available-Semantik sauber (siehe 8.2)
- [ ] `integration-owner`: `codeowners` in `manifest.json` gesetzt
- [ ] `log-when-unavailable`: Log auf `warning` einmalig, nicht repetitiv
- [ ] `parallel-updates`: `PARALLEL_UPDATES = 0` in sensor.py/binary_sensor.py (Coordinator übernimmt)
- [ ] `reauthentication-flow`: `async_step_reauth` implementiert
- [ ] `test-coverage`: >=95% für neue Module

Verifikation: Nach jedem Implementations-Abschnitt startet ein Subagent mit der Silver-Regel-Liste und prüft die aktuellen Files gegen den Erwartungswert.

## 13. Entwicklungsprozess

### 13.1 Entwicklungsphase — offline-first

Solange die Live-Instanzen nicht verfügbar sind, wird gegen folgende Autoritäten entwickelt:

1. **Offizielle Nightscout-API-Dokumentation** — `nightscout.github.io/accessing-information/rest-api/`
2. **cgm-remote-monitor Source** — `github.com/nightscout/cgm-remote-monitor/lib/api3/` (Route-Definitionen, JWT-Middleware, Filter-Syntax)
3. **Swagger-YAML** — `cgm-remote-monitor/swagger.yaml` (wenn vorhanden) oder `lib/api3/swagger.yaml`
4. **AAPS-Payload-Code** — `github.com/nightscout/AndroidAPS/.../NSDeviceStatus.kt` für devicestatus-Struktur
5. **Bereits gesammelte Response-Samples** — aus unserer Gesprächsvorarbeit, als anonymisierte Fixtures in `tests/fixtures/`

### 13.2 Git-Hygiene

- Branch-Modell: `main` (default), feature-branches nicht nötig für Solo-Dev
- Commits: kleine, atomare Schritte; Conventional Commits Präfix (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`)
- Pre-Commit-Hooks: `ruff check`, `ruff format`, `hassfest` (wenn lokal installiert), optional `mypy`
- Keine Pushes zu Remote bis v1 Silver-verifiziert
- Kein Push wenn irgendein Test-File Live-Tokens oder konkrete URLs enthält

### 13.3 CI (`.github/workflows/ci.yml`)

Vorbereitet für späteren Push:

```yaml
- pytest mit Coverage-Report
- ruff check + format
- hassfest
- HACS action (manifest-Struktur)
```

Läuft nur remote; lokal keine Wirkung.

### 13.4 Subagent-Driven Workflow

Folgende Rollen werden von Subagents übernommen:

- **Explorer**: Holt NS-v3-Doku und cgm-remote-monitor-Referenzen, cached relevante Snippets in `docs/references/`
- **Planner**: Aus writing-plans-Skill
- **Code-Reviewer**: Nach jedem Modul-Abschnitt gegen Silver-Checkliste verifizieren
- **Test-Runner**: pytest-Durchläufe, Coverage-Auswertung

## 14. Nicht-funktionale Anforderungen

- **Performance**: Fast-Cycle <500ms im Normalfall; Stats-Compute <2s für 14d, <10s für 90d
- **Ressourcen**: HistoryStore für 90d max ~5 MB SQLite-File
- **Verträglichkeit**: Funktioniert ab HA 2025.1 (pytest-homeassistant-custom-component minimum)
- **Privatheit**: Keine Telemetrie, keine Third-Party-Calls außer zur konfigurierten NS-Instanz
- **Sicherheit**: TLS-Verify an (default), kein `verify_ssl: False`-Backdoor
- **Internationalisierung**: Strings via `strings.json` + `translations/`; de.json + en.json initial

## 15. Offene Punkte zur Implementationszeit

Werden im writing-plans-Schritt aufgelöst:

- Genaue Swagger-Endpoint-Signaturen für `/api/v3/entries`-Pagination (Filter-Operator-Form `$gte` vs `$gt` vs `date`)
- Ob `pytest-homeassistant-custom-component` aktuelle Version alle unsere Fixtures abdeckt (oder ob wir eigene Utility-Fixtures brauchen)
- Exakter Algorithmus für `loop_mode`-Ableitung (drei Quellen möglich: `pump.status.status`, `openaps.enacted` vs `suggested`, `pump.extended.Status`)
- Ob `brands`-PR Teil von v1-Release oder post-Silver ist

## 16. Akzeptanzkriterien v1

- Zwei Config-Entries (anonymer Mock + ggf. Live-DevInstance) laufen stabil >= 48h
- Alle sechs Kategorien liefern Sensoren, wenn Capabilities erfüllt
- Config-Flow-Gruppierung funktioniert: "alle aktivieren" und "Subset anpassen" beide getestet
- Statistik-Fenster 14d ist immer da; 7d und 30d zusätzlich aktivierbar
- AGP-Attribut-Struktur ist von `apexcharts-card` verwendbar (Beispiel-Dashboard lädt und rendert)
- Diagnostics-Dump ist redacted und interpretable
- Reauth funktioniert (Token-Rotation ohne Entry-Neuanlage)
- Alle Silver-Checks gegen HA-Quality-Scale-Skript grün
- Coverage >=90%, Config-Flow und Auth 100%
- Keine personenbezogenen Daten in Git-History
