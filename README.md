# Nightscout v3 for Home Assistant

Nightscout v3 is a custom Home Assistant integration that reads data from a
[Nightscout](https://nightscout.github.io/) server through the `/api/v3` API
and exposes it as native Home Assistant entities.

It is built for people who want Nightscout data inside Home Assistant without
manually wiring REST sensors, statistics helpers, or custom templates.
Because HACS renders the repository README on the integration page, this file
is intentionally written as end-user documentation first.

## Requirements

- Home Assistant `2026.3` or newer
- Nightscout `15.0` or newer with the v3 API available
- A Nightscout URL reachable from your Home Assistant instance
- A Nightscout access token with at least `*:*:read`

## Installation

### HACS

If this repository is not in the default HACS catalog yet, add it as a custom
repository first.

1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Open the three-dot menu and select **Custom repositories**.
4. Add this GitHub repository URL and choose **Integration** as the category.
5. Download **Nightscout v3**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration** and search for
   **Nightscout v3**.

### Manual installation

1. Copy `custom_components/nightscout_v3` into
   `<config>/custom_components/nightscout_v3`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for
   **Nightscout v3**.

## Configuration

The integration is configured entirely from the Home Assistant UI.

During setup you will be asked for:

- **Server URL**: the base URL of your Nightscout server, for example
  `https://nightscout.example.com`
- **Access token**: the raw Nightscout token string with read access

After setup, open **Configure** on the integration to adjust:

- enabled features
- rolling statistics windows (`1`, `7`, `14`, `30`, and `90` days; `14` is
  always enabled)
- time-in-range thresholds
- polling intervals
- capability re-discovery if your Nightscout instance starts exposing new data

If the token stops working, Home Assistant will raise a repair flow so you can
reauthenticate from the UI without deleting the integration.

You can add multiple Nightscout servers to the same Home Assistant instance as
separate config entries.

## Supported devices

This integration connects to **Nightscout**, not directly to CGMs, pumps, or
loop apps.

Known supported inputs:

- Nightscout servers exposing `/api/v3`
- entries-only Nightscout setups
- Nightscout instances populated by AndroidAPS/AAPS
- Nightscout instances populated by Loop/iAPS/OpenAPS-style status data
- Care Portal treatment data
- uploader battery and online status data when present

Not supported:

- Nightscout `14.x` and older
- direct CGM or pump connections without Nightscout in the middle
- write-back actions to Nightscout in `0.1.x`

## Supported functionality

| Area | What Home Assistant gets |
| --- | --- |
| BG | current glucose, delta, direction, trend arrow, staleness |
| Pump | reservoir, battery, status, basal data, active profile, last bolus |
| Loop | active state, mode, IOB, COB, eventual BG, target BG, sensitivity ratio, predictions, last enacted age |
| Care Portal | sensor/site/insulin/battery age, last meal carbs, carbs today, last note |
| Uploader | battery percentage, online state, charging state |
| Statistics | mean, SD, CV, GMI, HbA1c estimate, TIR buckets, LBGI, HBGI, hourly profile, AGP percentiles |

Entity availability depends on what your Nightscout server actually stores.
For example, an entries-only server will not create pump or loop entities.
Some advanced or noisy entities are disabled by default and can be enabled from
the options flow.

Platforms provided:

- `sensor`
- `binary_sensor`

The integration is currently read-only and does not register any custom Home
Assistant actions or services.

## Data updates

This is a polling integration.

- Current entries and device status are refreshed every `60` seconds by default
- Change detection runs every `5` minutes by default
- Rolling statistics are recomputed every `60` minutes by default
- All three intervals can be changed from the options flow
- Statistics backfill up to `90` days of Nightscout history on first setup

On large Nightscout databases, the first statistics backfill can take a while.
It is normal for statistics entities to start out empty and fill in after the
initial history sync completes.

## Use cases

- Build a caregiver dashboard with current glucose, trend, IOB, COB, and loop
  state on one screen
- Notify when looping stops for longer than expected
- Track sensor, site, insulin, or pump battery age with Home Assistant
  reminders
- Add rolling TIR, CV, GMI, or HbA1c estimate tiles to a Home Assistant mobile
  dashboard

## Examples

This repository includes ready-to-adapt dashboard files:

- `dashboards/nightscout.yaml`: a full daily Lovelace dashboard (requires
  `apexcharts-card`, `mini-graph-card`, `mushroom`, `card-mod`)
- `dashboards/quarterly_review.yaml`: an ADA/Consensus-style report for
  the diabetologist's visit (requires `apexcharts-card` only — built on
  HA built-ins otherwise)
- `dashboards/examples/bg_card.yaml`: a compact glucose card (mushroom)
- `dashboards/examples/loop_card.yaml`: loop and pump status card
- `dashboards/examples/agp_card.yaml`: AGP percentile ribbon (apexcharts-card)
- `dashboards/examples/tir_donut.yaml`: TIR donut with target value in the
  center (apexcharts-card)
- `dashboards/examples/kpi_gauges.yaml`: three GMI / TIR / CV gauges with
  Consensus target bands (no HACS needed)
- `dashboards/examples/text_report.yaml`: a plain-Markdown 90-day report
  suitable for screenshotting or printing to PDF (no HACS needed)

See `docs/dashboard-setup.md` for wiring, HACS install, entity-slug
search-and-replace, and notes on the disabled-by-default AGP / LBGI / HBGI
sensors.

## Troubleshooting

### Setup fails with `Cannot reach the Nightscout server`

- Confirm the URL is correct and reachable from Home Assistant
- Confirm your Nightscout server is running and exposes `/api/v3`
- Confirm you are using Nightscout `15.0` or newer

### Setup fails with `Token rejected by the server`

- Confirm the token is still valid
- Confirm the token has at least `*:*:read`
- If you recently rotated the token, start the integration again with the new
  value

### The integration does not appear after installing through HACS

- Restart Home Assistant after the download finishes
- If **Add integration** still does not show the integration, refresh or clear
  the browser cache and try again

### Some entities are missing

- Pump, loop, care portal, and uploader entities are capability- and
  data-dependent
- Open **Configure** and run the capability re-discovery step if your
  Nightscout instance started exposing new data after the integration was set
  up
- Check whether the entity is disabled by default in Home Assistant

### Home Assistant asks for reauthentication

Your Nightscout token is no longer accepted. Open the repair flow for
**Nightscout v3**, enter a new token, and reload the integration.

### Reporting an issue

When opening an issue, include:

- your Home Assistant version
- the integration version
- your Nightscout version
- a short description of the problem
- a redacted diagnostics download from the integration, if possible

Diagnostics are redacted before export so URLs, tokens, notes, and related
sensitive values are not included verbatim.

## Known limitations

- `0.1.x` is read-only
- There is no migration from Home Assistant's core `nightscout` integration
- Some entities only exist when the upstream Nightscout data model includes the
  required fields
- Nightscout versions older than `15.0` are not supported
- Statistics depend on the local history cache and may need time to populate on
  first setup

## Removing the integration

1. Go to **Settings → Devices & services** and remove **Nightscout v3**.
2. If you installed it through HACS, remove the repository there as well.
3. Restart Home Assistant.
4. If you also want to remove the local history cache, delete the
   `<config>/nightscout_v3/` directory after the integration has been removed.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for local
setup, test commands, fixture handling, and pull request expectations.
