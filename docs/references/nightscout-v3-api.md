# Nightscout v3 REST API — Developer Reference

**Status:** Compiled offline from official sources; cross-verified with live-captured samples from our test instance (before outage).
**Nightscout Version Targeted:** 15.0.0 / API 3.0.3-alpha
**Sources:** See Section 9

---

## 1. Authentication

### 1.1 JWT Token Exchange (Bootstrap)

**Endpoint:** `POST /api/v2/authorization/request/<access_token>`

**Auth:** None (bootstrap only). The access token itself is the credential.

**Example:**
```bash
curl -X POST "https://ns.example.com/api/v2/authorization/request/homeassist-abc123def456"
```

**Response (HTTP 200):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<payload>.<sig>",
  "sub": "homeassistant",
  "permissionGroups": [
    ["api:treatments:create"],
    ["*:*:read"],
    []
  ],
  "iat": 1776809063,
  "exp": 1776837863
}
```

**Notes verified against live sample from our test instance:**
- JWT lifetime on the tested server: 8h (28800 s, iat→exp delta).
- `sub` on our HA-created token was `"homeassistant"`, not the raw access-token string (the Explore-agent claim of "access token as sub" is incorrect for HA tokens).
- `permissionGroups` is an array of arrays (groups of scope strings). `*:*:read` is a valid wildcard meaning "read everything".
- Access token format used by HA scope in Admin Tools: `homeassist-<16-hex>`.

### 1.2 Sending JWT on Subsequent Requests

**Header:** `Authorization: Bearer <jwt_token>`

The `?token=<access_token>` query-param shortcut from v1/v2 **does NOT work** for v3 data endpoints — only the bootstrap endpoint and the v1/v2 data endpoints accept it. v3 returns `{"status":401,"message":"Missing or bad access token or JWT"}` for query-param auth.

### 1.3 Permission Scopes

Scope format: `<resource>:<collection>:<operation>`.

| Scope | Meaning |
|---|---|
| `*:*:read` | Read everything |
| `*:*:admin` | Full admin |
| `api:entries:read` | Read entries only |
| `api:entries:create` | Create entries |
| `api:treatments:read` | Read treatments |
| `api:treatments:create` | Create treatments |
| `api:devicestatus:read` | Read devicestatus |
| `api:devicestatus:create` | Create devicestatus (for uploaders) |
| `api:profile:read` | Read profile |

**Operations:** `read` (r), `create` (c), `update` (u), `delete` (d), `admin`.

### 1.4 Refresh Strategy

- Proactive refresh when `exp - now < 3600` s (1h headroom).
- Plus a background timer (every 7h) as second line.
- On network failure: exponential backoff 1s, 2s, 4s, 8s, 16s, 32s, 64s, max 5 tries, then `ConfigEntryAuthFailed`.

---

## 2. Public / Bootstrap Endpoints

### 2.1 `GET /api/v3/version`

Auth: **None**. Use for health checks and capability detection.

```json
{
  "status": 200,
  "result": {
    "version": "15.0.0",
    "apiVersion": "3.0.3-alpha",
    "srvDate": 1776808630705,
    "storage": { "storage": "mongodb", "version": "8.2.3" }
  }
}
```

---

## 3. Data Endpoints (all require `Authorization: Bearer <jwt>`)

### 3.1 `GET /api/v3/status`

Server settings, plugin list, permissions.

Important fields:
- `settings.units`: `"mg/dl"` or `"mmol/L"` — drives display conversion
- `plugins`: string list — e.g. `["delta","direction","upbat","iob","cob","pump","openaps"]`
- `permissions.<collection>`: permission string like `"cru"`

### 3.2 `GET /api/v3/lastModified`

Incremental-sync pivot.

```json
{
  "status": 200,
  "result": {
    "srvDate": 1776809794509,
    "collections": {
      "devicestatus": 1776809726217,
      "entries": 1776809721315,
      "treatments": 1776807978105,
      "profile": 1756154690568,
      "food": 1560273313821
    }
  }
}
```

All timestamps in **milliseconds epoch**. Cache per-collection; next sync only if `collections[x]` > cached value.

### 3.3 `GET /api/v3/entries`

| Query param | Example | Meaning |
|---|---|---|
| `limit` | `limit=1000` | Max 1000 per request |
| `skip` | `skip=1000` | Pagination offset |
| `sort$desc` | `sort$desc=date` | Sort descending |
| `sort` | `sort=date` | Sort ascending |
| `date$gte` | `date$gte=1776800000000` | ms epoch filter |
| `date$lt` | `date$lt=1776900000000` | exclusive upper bound |
| `srvModified$gt` | `srvModified$gt=1776800000000` | Incremental sync cursor |
| `type$eq` | `type$eq=sgv` | Filter by type |
| `fields` | `fields=sgv,date,direction` | Projection (bandwidth saver) |

**SGV record (verified against live capture):**

```json
{
  "identifier": "5930f5c2ecd6d38a25393b03",
  "type": "sgv",
  "sgv": 195,
  "date": 1483251415972,
  "dateString": "2017-01-01T07:16:55.972+0100",
  "direction": "Flat",
  "noise": 1,
  "filtered": 246304,
  "unfiltered": 243520,
  "rssi": 100,
  "delta": -6.752,
  "device": "xDrip-DexbridgeWixel",
  "sysTime": "2017-01-01T07:16:55.972+0100",
  "srvCreated": 1483251415972,
  "srvModified": 1483251415972
}
```

Direction values: `Flat`, `SingleUp`, `DoubleUp`, `SingleDown`, `DoubleDown`, `FortyFiveUp`, `FortyFiveDown`, `NONE`, `NOT COMPUTABLE`, `RATE OUT OF RANGE`.

### 3.4 `GET /api/v3/treatments`

Same query syntax as entries. Common filters:

```bash
# Latest Sensor Change
?eventType$eq=Sensor+Change&limit=1&sort$desc=date

# Multiple event types in one query
?eventType$in=[Meal+Bolus,Correction+Bolus]&limit=50&sort$desc=date

# Modified since
?srvModified$gt=1776800000000&limit=1000
```

**Standard eventTypes observed in cgm-remote-monitor source + AAPS upload paths:**

| eventType | Typical fields |
|---|---|
| `Meal Bolus` | `insulin`, `carbs`, `notes` |
| `Correction Bolus` | `insulin`, `notes` |
| `Combo Bolus` | `insulin`, `splitNow`, `splitExt`, `carbs`, `duration` |
| `Temp Basal` | `absolute` or `percent`, `rate`, `duration`, `durationInMilliseconds` |
| `Carbs` | `carbs`, `absorptionTime` |
| `Note`, `Announcement`, `Exercise` | `notes`, optional `duration`, `intensity` |
| `Sensor Start`, `Sensor Change` | `date` only (age tracking) |
| `Insulin Change` | `date` only |
| `Site Change` | `date` only |
| `Pump Battery Change` | `date` only |
| `Snack Bolus` (legacy) | like Meal Bolus |
| `Profile Switch` | `profile`, `duration`, `percentage`, `timeshift` |
| `OpenAPS Offline` | `date`, `reason`, `duration` |

**Treatment record (verified live — AAPS Temp Basal):**

```json
{
  "identifier": "69e7f031f8b17a8ccd52cf8d",
  "type": "treatment",
  "eventType": "Temp Basal",
  "isValid": true,
  "created_at": "2026-04-21T21:46:18.105Z",
  "enteredBy": "openaps://AndroidAPS",
  "duration": 120,
  "durationInMilliseconds": 7200000,
  "rate": 0,
  "percent": -100,
  "pumpId": 1776807978105,
  "pumpType": "ACCU_CHEK_COMBO",
  "pumpSerial": "PUMP_10154415",
  "srvCreated": 1775684572000,
  "srvModified": 1775684572000
}
```

### 3.5 `GET /api/v3/devicestatus`

The big one for AAPS. Typical record top-level keys: `created_at`, `device`, `pump`, `openaps`, `uploaderBattery`, `isCharging`, `configuration`, `identifier`, `srvModified`, `srvCreated`.

**openaps sub-structure (live AAPS 3.4.0.0-dev capture):**

```json
{
  "openaps": {
    "iob": {
      "iob": 2.05,
      "basaliob": -0.28,
      "activity": 0.042,
      "time": "2026-04-21T22:06:06.553Z"
    },
    "suggested": {
      "algorithm": "SMB",
      "runningDynamicIsf": false,
      "timestamp": "2026-04-21T22:06:01.540Z",
      "bg": 179,
      "tick": "-3",
      "eventualBG": 58,
      "targetBG": 95,
      "insulinReq": 0,
      "deliverAt": "2026-04-21T22:05:57.922Z",
      "sensitivityRatio": 1,
      "reason": "COB: 14,5, Dev: 114, ISF: 120, CR: 12, Target: 95 ...",
      "predBGs": {
        "IOB": [ 179, 174, 170, ... (30 values) ],
        "ZT":  [ 179, 157, 136, ... (≈48 values) ],
        "COB": [ 179, 175, 171, ... (≈48 values) ]
      },
      "COB": 14.547,
      "IOB": 2.051,
      "variable_sens": 0,
      "consoleLog": ["Autosens ratio: 1.0; ", ...],
      "consoleError": ["CR:12.0", ...],
      "isfMgdlForCarbs": true
    },
    "enacted": {
      /* optional: similar to suggested, but represents actually-applied decision */
    }
  }
}
```

**pump sub-structure (AAPS + Accu-Chek Combo live capture):**

```json
{
  "pump": {
    "reservoir": 97,
    "clock": "2026-04-21T22:06:06.567Z",
    "battery": { "percent": 25 },
    "status": {
      "status": "Closed Loop",
      "timestamp": "2026-04-21T21:46:26.348Z"
    },
    "extended": {
      "Version": "3.4.0.0-dev-e7de99043a-2026.01.10",
      "LastBolus": "21.04.26 21:26",
      "LastBolusAmount": 0.1,
      "TempBasalStart": "21.04.26 23:46",
      "TempBasalRemaining": 100,
      "BaseBasalRate": 0.28,
      "ActiveProfile": "200U Normal"
    }
  }
}
```

`pump.battery` can have EITHER `percent` (Accu-Chek) OR `voltage`+`status` (Medtronic) depending on pump. Client must handle both.

**uploaderBattery**: integer (0–100), % of uploader phone.

**isCharging**: boolean.

### 3.6 `GET /api/v3/profile`

Latest profile record. Key fields:
- `defaultProfile`: name of active profile ("Normal", "Sport", etc.)
- `store[<name>]`: profile content with `basal`, `carbratio`, `sens` (ISF), `target_low`, `target_high` (each as time-of-day arrays)
- `store[<name>].units`: `"mg/dl"` or `"mmol/L"`
- `store[<name>].timezone`

Not normally needed for live monitoring; useful for context (active profile name is already in `devicestatus.pump.extended.ActiveProfile`).

---

## 4. Filter Operator Reference

All list endpoints support these MongoDB-style operators:

| Operator | Syntax | Example |
|---|---|---|
| `$eq` | `field$eq=value` | `eventType$eq=Sensor+Change` |
| `$ne` | `field$ne=value` | `isValid$ne=false` |
| `$gt` / `$gte` | `field$gt=value` | `date$gte=1776800000000` |
| `$lt` / `$lte` | `field$lt=value` | `date$lt=1776900000000` |
| `$in` | `field$in=[a,b,c]` | `eventType$in=[Meal+Bolus,Carbs]` |
| `$nin` | `field$nin=[a,b]` | `type$nin=[mbg,cal]` |
| `$exists` | `field$exists=true` | `carbs$exists=true` |
| `$re` | `field$re=regex` | `device$re=^openaps` |

Sort: `sort=field` (asc) or `sort$desc=field` (desc).

URL-encode spaces as `+` or `%20`. Array values go literally `[a,b,c]` without JSON-quotes.

---

## 5. Envelope & Error Handling

**Success:** `{"status": 200, "result": <array or object>}`

**Error:** `{"status": <code>, "message": "<text>"}` — HTTP status matches envelope.

Common error codes:

| Code | Meaning | Client action |
|---|---|---|
| 400 | Malformed query | Don't retry; log + alert |
| 401 | Missing/invalid JWT | Refresh JWT, then retry once; if still 401 → `ConfigEntryAuthFailed` |
| 403 | Insufficient permissions | Don't retry; surface to user |
| 404 | Unknown path | Don't retry |
| 500+ | Server-side | Exponential backoff retry |

---

## 6. Pagination Strategy

Max `limit=1000`. For backfill:

```python
async def paginate_entries(client, since_ms):
    oldest_needed = since_ms
    cursor = int(time.time() * 1000)
    all_entries = []
    while True:
        batch = await client.get_entries(
            params={"sort$desc": "date", "date$lt": cursor, "limit": 1000}
        )
        if not batch:
            break
        all_entries.extend(batch)
        oldest_in_batch = min(e["date"] for e in batch)
        if oldest_in_batch <= oldest_needed or len(batch) < 1000:
            break
        cursor = oldest_in_batch
        await asyncio.sleep(0.5)  # be nice to the server
    return all_entries
```

For incremental sync: use `srvModified$gt=<cached_last_modified>`, no pagination issue since deltas are small.

---

## 7. Integration Patterns

### 7.1 Capability Probe (Setup)

```python
async def probe(client):
    status = await client.get("/api/v3/status")   # units, plugins
    ds = await client.get("/api/v3/devicestatus?limit=1")
    entries_check = await client.get("/api/v3/entries?limit=1")
    
    return {
        "units": status["settings"]["units"],
        "has_openaps": "openaps" in status.get("plugins", []),
        "has_pump": bool(ds and ds[0].get("pump")),
        "has_uploader": bool(ds and ds[0].get("uploaderBattery") is not None),
        "has_entries": bool(entries_check),
    }
```

### 7.2 Live Polling (60s)

```python
async def fast_cycle(client):
    ds, entries = await asyncio.gather(
        client.get("/api/v3/devicestatus?limit=1&sort$desc=date"),
        client.get("/api/v3/entries?limit=2&sort$desc=date"),
    )
    return {"devicestatus": ds[0] if ds else None, "entries": entries}
```

### 7.3 Change-Detect (5 min)

```python
async def change_detect_cycle(client, cached_lm):
    lm = await client.get("/api/v3/lastModified")
    if lm["collections"]["entries"] > cached_lm["entries"]:
        await sync_entries_since(cached_lm["entries"])
    if lm["collections"]["treatments"] > cached_lm["treatments"]:
        await refresh_age_treatments()
    return lm
```

### 7.4 Age Computation

```python
async def get_age_days(client, event_type):
    result = await client.get(
        f"/api/v3/treatments",
        params={"eventType$eq": event_type, "limit": 1, "sort$desc": "date"}
    )
    if not result:
        return None
    t = result[0]
    # Use 'date' (ms epoch) if present, else parse created_at ISO
    t_ms = t.get("date") or datetime.fromisoformat(
        t["created_at"].replace("Z", "+00:00")
    ).timestamp() * 1000
    return (now_ms() - t_ms) / 86400000
```

---

## 8. Gotchas & Diffs vs v1/v2

1. **Timestamps in milliseconds, not seconds.** `date`, `srvCreated`, `srvModified` all in ms epoch.

2. **Auth header only** on v3 data endpoints. Query-param `?token=...` works on v1/v2 and on the bootstrap exchange, but NOT on v3 data endpoints.

3. **Envelope required:** responses wrapped in `{status, result}`. v1 returns raw arrays. Client must unwrap.

4. **`identifier` field** is the canonical ID for dedup, not `_id` (Mongo ObjectId still exists under the hood but `identifier` is what v3 exposes).

5. **`srvModified` vs `date`:**
   - `date` = when the event happened (user-facing timestamp)
   - `srvModified` = when the server changed the record
   - Use `srvModified$gt=<cursor>` for incremental sync; using `date$gt=` misses backdated corrections.

6. **Filter operator syntax:** `field$op=value` (NOT `find[field][$op]=value` as in v1).

7. **`/api/v2/properties`** (the IOB/COB/SAGE aggregator) has **no v3 equivalent** (`/api/v3/properties` → 404). Integration must either use `/api/v2/properties` OR compute the values client-side from raw collections. This integration chose client-side computation because `devicestatus.openaps.iob.iob` and `.suggested.COB` are already available in `devicestatus`.

8. **`isValid: false`** marks soft-deleted records. Filter on client or with `isValid$ne=false`.

9. **`pump.battery` varies by pump:** some pumps upload `percent`, others `voltage`+`status`. Client must handle both.

10. **Loop state detection** is not a single flag. Combine:
    - `devicestatus.pump.status.status` ("Closed Loop", "Open Loop", "Suspended", …)
    - age of latest `devicestatus.created_at` (older than 15 min → stale)
    - presence of `openaps.enacted` (actively enacting = closed loop)

11. **`predBGs` array lengths differ**: `IOB` is usually ~30 points (150 min), `COB` and `ZT` up to 48 (4h). Don't assume uniform length.

12. **Access-token prefix** `homeassist-` is a convention set by the "Admin Tools → Subjects" UI; any name can be used. Don't hard-assume this prefix.

---

## 9. Sources

- Official docs: https://nightscout.github.io/nightscout/nightscout_api/
- API v3 docs: https://nightscout.github.io/accessing-information/rest-api/
- Swagger YAML: https://github.com/nightscout/cgm-remote-monitor/blob/master/lib/api3/swagger.yaml
- API3 implementation: https://github.com/nightscout/cgm-remote-monitor/tree/master/lib/api3
- Security/JWT: https://github.com/nightscout/cgm-remote-monitor/blob/master/lib/security.js
- Storage: https://github.com/nightscout/cgm-remote-monitor/tree/master/lib/storage
- AAPS upload: https://github.com/nightscout/AndroidAPS — look for `NSDeviceStatus`, `NSUpload`, `plugins/general/nsclient`
- Plus our own live-captured response samples (anonymized in `tests/fixtures/`) which serve as the ground-truth reference for AAPS payload layout.
