# Dashboard setup

The integration ships two ready-to-use Lovelace dashboards plus small
copy-paste snippets under `dashboards/examples/`:

| File                                | Purpose                                                                    |
| ----------------------------------- | -------------------------------------------------------------------------- |
| `dashboards/nightscout.yaml`        | 5-view daily dashboard (BG live, Trend, AGP, Stats, Loop).                 |
| `dashboards/quarterly_review.yaml`  | Single-view ADA/Consensus-style **quarterly report** for diabetology visits. |

Both assume the integration's device slug is `nightscout_v3`. If your
config-entry title produces different entity IDs, search-and-replace
`nightscout_v3` with your actual slug.

## Prerequisites

The dashboards differ in their HACS dependencies:

| Dashboard                          | Required HACS frontend plugins                                           |
| ---------------------------------- | ------------------------------------------------------------------------ |
| `quarterly_review.yaml`            | `apexcharts-card` only                                                   |
| `nightscout.yaml`                  | `apexcharts-card`, `mini-graph-card`, `mushroom`, `card-mod`             |

`quarterly_review.yaml` is intentionally built on HA built-ins (`gauge`,
`tile`, `glance`, `markdown`, `grid`) plus `apexcharts-card` for the donut
and AGP ribbon — so it renders on any 2024.6+ HA install without pulling
in the full mushroom/card-mod stack.

### Home Assistant version

`quarterly_review.yaml` uses `type: sections` (HA 2024.6+). On older HA
the dashboard will fall back to the legacy masonry layout — it still works,
just without the grid alignment.

## Integration options to enable before first use

- **Statistics windows**: Options flow → Statistics → tick `30` and `90` days
  in addition to the mandatory `14`.
- **Disabled-by-default features**: `stat_agp_14d`, `stat_lbgi_90d`,
  `stat_hbgi_90d` are created with `entity_registry_enabled_default=False`.
  Enable them via **Settings → Devices & Services → Nightscout v3 → Entities
  → "Show disabled"**, tick the three sensors, hit *Enable*. One stats cycle
  later (~60 min, or reload the integration) the AGP chart and LBGI/HBGI
  gauges populate.

## Register the dashboard

1. Copy the YAML file into your HA config dir, e.g.
   `config/dashboards/quarterly_review.yaml`.
2. In `configuration.yaml`:

    ```yaml
    lovelace:
      dashboards:
        nightscout-quarterly:
          mode: yaml
          title: Nightscout Quartal
          icon: mdi:file-chart-outline
          show_in_sidebar: true
          filename: dashboards/quarterly_review.yaml
    ```

3. Restart HA (dashboard-file changes don't need a restart afterwards —
   just Ctrl-F5 the dashboard).

## Multiple instances side by side

Two Nightscout config entries can coexist in one HA.

- Copy the dashboard file for each instance.
- Replace the entity slug (e.g. `nightscout_v3` → `nightscout_child_a`) so
  each copy points at the correct config entry.
- Register both under `lovelace.dashboards` with distinct filenames.

## Example snippets

For users who just want one or two cards instead of the whole dashboard,
see `dashboards/examples/`:

| File                   | What it renders                                                        | Dependency        |
| ---------------------- | ---------------------------------------------------------------------- | ----------------- |
| `bg_card.yaml`         | Single headline current-BG card.                                       | mushroom          |
| `loop_card.yaml`       | Loop + pump status entities list.                                      | none              |
| `agp_card.yaml`        | AGP perzentile ribbon (p5/p25/median/p75/p95) over 24 h.               | apexcharts-card   |
| `tir_donut.yaml`       | TIR-Verteilung 90 Tage als Donut mit TIR-in-Range in der Mitte.        | apexcharts-card   |
| `kpi_gauges.yaml`      | Drei Gauges (GMI/TIR/CV) mit Consensus-Ampelsegmenten.                 | none              |
| `text_report.yaml`     | Plain-Markdown-Bericht für Copy-Paste / PDF-Export.                    | none              |

Each snippet is a single YAML document — paste it as a new card in any
view.

## Why `data_generator` instead of `attribute:` for the AGP chart

The integration exposes `p5_by_hour` … `p95_by_hour` as 24-entry lists on
the `stat_agp_*d` sensor. apexcharts-card v2.x treats `attribute:` payloads
as time series — 24 unlabelled numbers get rendered as a constant line at
the current attribute "average" rather than a 24-point curve. The AGP card
therefore uses `data_generator` to map each hour index to a real UTC
millisecond timestamp (`today 00:00 UTC + i × 1 h`) and sets
`xaxis.type: datetime`. See `dashboards/examples/agp_card.yaml` for the
exact pattern if you want to build your own.

## Printing to PDF

Open any dashboard → browser print preview → landscape → save as PDF.
All cards in `quarterly_review.yaml` are plain HA built-ins or
apexcharts-card SVG, both of which render cleanly via the browser print
pipeline. No card-mod print styles required.

## Troubleshooting

- **Cards show `Custom element doesn't exist: ...`** — HACS frontend
  plugin missing. Check the Prerequisites table above.
- **All entities show `unavailable`** — the integration itself is not
  loaded or in reauth state. Check **Settings → Devices & Services**.
- **AGP chart is empty or shows flat lines** — `stat_agp_14d` disabled or
  the stats cycle has not run yet. Enable the sensor in the entity
  registry, reload the integration, wait one stats cycle.
- **Donut total reads ~99–103 %** — the integration returns each TIR
  bucket rounded to 2 decimals; separately-rounded buckets rarely sum to
  exactly 100. The shipped donut displays the TIR-in-range value in the
  center instead of the sum; if you build your own, use a
  `total.formatter` that returns `w.globals.seriesTotals[2]` rather than
  the default sum.
- **BG card shows a very old `Δ`** — your Nightscout server stopped
  uploading. Check `binary_sensor.nightscout_v3_uploader_online` and the
  `stale_minutes` diagnostic sensor.
