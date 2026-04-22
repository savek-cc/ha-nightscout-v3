# Nightscout v3 for Home Assistant

A Home Assistant custom integration that surfaces a Nightscout instance as
first-class sensors, binary sensors, a device, a diagnostics export, and a
ready-to-install Lovelace dashboard. Written for the v3 Nightscout API
(JWT auth, subjects, capability probing) and tested against AAPS-fed
instances used by Type 1 diabetics.

## What it does

- **BG**: current SGV, Δ, direction, trend arrow, staleness.
- **Pump**: reservoir, battery, base/temp basal, active profile, last bolus.
- **Loop** (AAPS/OpenAPS): mode, active, IOB, COB, predictions, eventual/target
  BG, sensitivity ratio, last-enacted age.
- **Careportal read-only**: sensor/cannula/insulin/pump-battery age, last meal
  carbs, carbs today.
- **Statistics** (per configurable window, 14 d always on): mean, SD, CV, GMI,
  eHbA1c DCCT, TIR (5 buckets), LBGI/HBGI, hourly profile, AGP percentiles.
- **Uploader**: battery %, online, charging.
- **Diagnostics export**: redacted JSON snapshot for bug reports.

## Requirements

- Home Assistant ≥ 2025.1 (uses `runtime_data` and the current quality-scale gates).
- A Nightscout server with the v3 API enabled (Nightscout ≥ 15.0).
- An access token with at least `*:*:read`. Write scopes
  (`api:treatments:create` etc.) are not needed — v0.1.0 is read-only.

## Installation via HACS

1. In HACS, **Integrations → ⋯ → Custom repositories**.
2. Add this repository's Git URL as category **Integration**.
3. Install **Nightscout v3**. Restart Home Assistant.
4. **Settings → Devices & Services → Add Integration → Nightscout v3**.

## Configuration

### User step

- **URL** — base URL of your Nightscout server, e.g. `https://my.nightscout.example`.
  The integration normalizes trailing slashes and rejects non-HTTPS hosts.
- **Access token** — paste the raw token string. The integration exchanges it
  for a JWT on setup and refreshes every ~7 h in the background.

### Options flow

Open **Configure** on the instance to walk through:

1. **Features** — toggle individual sensors on/off. Disabled features are
   hidden from the UI.
2. **Statistics windows** — the mandatory 14 d window plus any combination of
   1 d / 7 d / 30 d / 90 d.
3. **TIR thresholds** — override the default 70–180 mg/dL (and very-low /
   very-high buckets).
4. **Polling intervals** — fast cycle (default 60 s), change-detect cycle
   (5 min), stats cycle (60 min or on upstream change).
5. **Rediscover capabilities** — re-probes the server (re-runs
   `GET /api/v3/status`) to pick up newly-enabled features.

## Features overview

| Category    | Count | Default enabled                                         |
| ----------- | ----- | ------------------------------------------------------- |
| BG          | 5     | all                                                     |
| Pump        | 9     | all (gated by `pump` capability)                        |
| Loop        | 11+1  | all except `loop_reason` (gated by `openaps`)           |
| Careportal  | 7     | all except `care_last_note`                             |
| Uploader    | 3     | all (gated by `uploader_battery`)                       |
| Statistics  | 14/w  | core 10 enabled per window; profile/LBGI/HBGI/AGP opt-in|

See `custom_components/nightscout_v3/feature_registry.py` for the canonical
list.

## Dashboard setup

A 5-view dashboard (Übersicht, Trend, AGP, Statistik, Loop) ships under
`dashboards/nightscout.yaml`. It depends on these HACS frontend plugins:

- `apexcharts-card`, `mini-graph-card`, `mushroom`, `card-mod`.

Full setup walkthrough: **[docs/dashboard-setup.md](docs/dashboard-setup.md)**.

Three copy-paste snippets live under `dashboards/examples/`.

## Removing the integration

1. **Settings → Devices & Services → Nightscout v3 → ⋯ → Delete**. All
   config entries, entities, and the device go away.
2. If you used the shipped dashboard, remove the
   `lovelace.dashboards.nightscout` block from `configuration.yaml` (or
   un-register it from **Settings → Dashboards**).
3. In HACS → **Integrations → Nightscout v3 → ⋯ → Remove** to uninstall
   the integration files. Restart HA.

No external state is left behind; the SQLite history store lives under the
integration's own `.storage` dir and is removed with the config entry.

## Reauthentication

If your token is rotated or the server rejects the JWT, the integration
surfaces a Home Assistant reauthentication (**"Repair"**) prompt. Click it,
paste the new token, and the integration resumes without reconfiguring.

## Multiple instances

Two instances coexist cleanly — one per family member is the expected case.
Example used in this project: **DevInstance** at `dev-nightscout.example.invalid` (dev / test
target) and **ProdInstance** at `prod-nightscout.example.invalid` (production, never written
against). Each gets its own config entry, device, and entity prefix.

## Quality Scale

Targeting **Silver** (`custom_components/nightscout_v3/quality_scale.yaml`).
`scripts/verify_silver.py` is the static gate that checks every Silver rule
is `done` or explicitly `exempt` with a comment. The `docs-*` and `brands`
rules depend on the upstream Home Assistant docs / brands repositories and
flip to `done` once the corresponding PRs are merged; see `quality_scale.yaml`
for the current state.

## Privacy & safety

- No URLs, tokens, patient notes, or free-text pump strings are logged.
- Diagnostics exports are redacted (`async_redact_data` over URL, token,
  `reason`, `notes`).
- Test fixtures are captured against **DevInstance only** and run through
  `scripts/anonymize_fixtures.py` (device IDs, pump serials, free-text
  reasons all scrubbed; timestamps rebased; carbs bucketed) before landing
  in `tests/fixtures/`.
- `scripts/capture_fixtures.py` and `scripts/smoke_test.py` refuse to run
  against ProdInstance via a hard-coded hostname block.

## Server-side tuning

On Nightscout instances with long history, this integration's capability
probe and regular polling issue API v3 search queries against
`treatments`, `entries`, and `devicestatus`. Nightscout's v3 layer
(`lib/api3/generic/search/input.js#parseSort`) unconditionally appends
three tiebreaker fields (`identifier`, `created_at`, `date`) to **every**
sort — so the Mongo sort is always three-field, and none of the default
indexes cover that shape. The result: COLLSCAN + in-memory SORT on every
v3 search, including simple "latest 1" lookups.

Measured against a real instance (Nightscout 15.0.6):

| Collection   | Docs  | Plan before                              | Time    |
| ------------ | ----- | ---------------------------------------- | ------- |
| treatments   | 574k  | `IXSCAN(eventType_1)` + SORT, 214 keys  | ~2 s    |
| entries      | 961k  | **COLLSCAN** + SORT, 961k docs examined | ~5.8 s  |
| devicestatus | 1.9M  | **COLLSCAN** + SORT, 1.9M docs examined | ~28 s   |

The devicestatus case alone can OOM-kill Mongo on small-RAM hosts.

One-shot fix: add three compound indexes matching the real sort shapes.

```bash
docker exec <mongo-container> mongosh <db> --eval '
  db.treatments.createIndex(
    {eventType: 1, created_at: -1, identifier: -1, date: -1},
    {name: "v3_treatments_by_eventtype", background: true});
  db.entries.createIndex(
    {date: -1, identifier: -1, created_at: -1},
    {name: "v3_entries_sort", background: true});
  db.devicestatus.createIndex(
    {created_at: -1, identifier: -1, date: -1},
    {name: "v3_devicestatus_sort", background: true});
'
```

After the indexes: each query drops to `IXSCAN → FETCH → LIMIT`,
`totalKeysExamined: 1`, sub-millisecond execution. Index builds take a
few seconds even on multi-million-doc collections, and the indexes
themselves are compact.

Upstream tracking:
[nightscout/cgm-remote-monitor#8477](https://github.com/nightscout/cgm-remote-monitor/issues/8477)
(issue) and
[#8478](https://github.com/nightscout/cgm-remote-monitor/pull/8478)
(PR) — both cover all three collections.
Related: PR
[#5463](https://github.com/nightscout/cgm-remote-monitor/pull/5463)
introduced the existing `{eventType, duration, created_at}` index (the
one predating v3's parseSort tiebreakers); issue
[#7898](https://github.com/nightscout/cgm-remote-monitor/issues/7898)
reports the correctness symptom (sort direction ignored on
`/api/v3/treatments?eventType$eq=…&sort$desc=created_at`) that the
missing compound index likely causes.

## Troubleshooting

- **JWT refresh loop in logs** — your token was rotated; use the reauth
  prompt (Settings → Devices & Services → Nightscout v3 → Repair).
- **Sensor shows `unavailable` but BG card is fresh** — capability mismatch;
  run Options → Rediscover capabilities.
- **"Carbs today" stuck at 0** — Nightscout's `/treatments` returned no Meal
  Bolus or Carbs entries in the last 24 h; not an integration bug.
- **Dashboard cards render blank** — HACS frontend plugins missing; see
  `docs/dashboard-setup.md`.
- **Config flow "Connecting…" hangs 30+ seconds / server memory spikes on
  Add Integration** — missing compound indexes on `treatments`, `entries`,
  and `devicestatus`; see **Server-side tuning** above.

## Links

- **Specification**: `docs/specs/2026-04-22-ha-nightscout-v3-design.md`
- **Implementation plan**: `docs/plans/2026-04-22-ha-nightscout-v3-plan.md`
- **Architecture**: `docs/architecture.md`
- **Contributing**: `CONTRIBUTING.md`
- **Roadmap**: `docs/roadmap.md`
- **HACS**: https://hacs.xyz
