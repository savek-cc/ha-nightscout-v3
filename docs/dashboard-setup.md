# Dashboard setup

The integration ships a ready-to-use 5-view Lovelace dashboard under
`dashboards/nightscout.yaml`, plus three copy-paste snippets under
`dashboards/examples/`. This doc walks you through getting them on screen.

## Prerequisites

Install these HACS frontend plugins before importing the dashboard.
Without them the cards render blank.

| Plugin               | Used for                                                            |
| -------------------- | ------------------------------------------------------------------- |
| `apexcharts-card`    | BG trend, AGP ribbon, any time-series with custom styling           |
| `mini-graph-card`    | IOB / COB 24 h mini-charts on the Trend view                        |
| `mushroom`           | Headline BG card, IOB/COB/Temp tiles, Loop status tile              |
| `card-mod`           | Conditional styling (colored BG halo below 70 / above 180)          |

In HACS → **Frontend** → **Explore & download repositories**, search for each
and install. Reload HA's frontend resources after.

## Import the shipped dashboard

1. Copy the content of `dashboards/nightscout.yaml` into your HA config dir,
   e.g. `config/dashboards/nightscout.yaml`.
2. In `configuration.yaml` (or via the UI under **Settings → Dashboards →
   Add dashboard → From YAML file**):

    ```yaml
    lovelace:
      dashboards:
        nightscout:
          mode: yaml
          title: Nightscout
          icon: mdi:diabetes
          show_in_sidebar: true
          filename: dashboards/nightscout.yaml
    ```

3. Restart HA or reload dashboards.

## Entity prefix

The shipped YAML assumes the integration's device slug is **`nightscout_v3`**,
so entity IDs look like `sensor.nightscout_v3_bg_current`. If you named your
config entry something else, the slug changes too. For example, a config entry
named `Child A` will normally produce entity IDs such as
`sensor.child_a_bg_current`.

Search and replace `nightscout_v3` in the dashboard YAML with your actual
entity slug, for both `sensor.` and `binary_sensor.` references.

## Multiple instances side by side

Two instances can coexist on the same HA installation.

- Copy `dashboards/nightscout.yaml` to a second filename.
- Replace the entity slug in each copy so it matches the correct config entry.

Register both under `lovelace.dashboards` with distinct `filename` entries.

## Example snippets

For users who just want one or two cards instead of the whole dashboard,
see `dashboards/examples/`:

- **`bg_card.yaml`** — single headline BG card with color-coded halo.
  Drop into any existing view.
- **`agp_card.yaml`** — standalone AGP ribbon (p5/p25/median/p75/p95
  overlayed from the `stat_agp_14d` sensor's per-hour attributes).
  **Requires** the `stat_agp_14d` sensor to be enabled in HA's entity
  registry — it is disabled by default in the integration.
- **`loop_card.yaml`** — Loop + Pump status entities list.

Each snippet is a single YAML document — paste it as a new card in any
view.

## AGP-specific notes

The AGP chart reads from the `stat_agp_14d` sensor's `p5_by_hour`,
`p25_by_hour`, `p50_by_hour`, `p75_by_hour`, `p95_by_hour` attributes —
each a 24-entry list indexed by hour of day. The integration computes
these from 14 days of `/entries` history pulled through the
`HistoryStore`. For this to populate you need at least a few days of
data in the store; brand-new instances will show zeroed percentiles
until the backfill completes.

## Troubleshooting

- **Cards show `Custom element doesn't exist`** — HACS frontend plugins
  missing. See Prerequisites above.
- **All entities show `unavailable`** — the integration itself is not
  loaded or is in reauth state. Check **Settings → Devices & Services**.
- **AGP view is empty** — the `stat_agp_14d` sensor is disabled by
  default. Enable it in **Settings → Devices & Services → Nightscout v3 →
  Entities** (disabled-by-default tab). Wait one stats cycle (~60 min or
  reload the integration) to populate.
- **BG Card shows stale Δ** — your Nightscout server stopped uploading;
  check the uploader entity (`sensor.nightscout_v3_uploader_battery` /
  `binary_sensor.nightscout_v3_uploader_online`).
