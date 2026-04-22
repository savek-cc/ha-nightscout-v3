# Roadmap

What's explicitly **not** in v0.1.0 / Silver — and what might land later.

## Post-Silver candidates

### Gold Quality Scale

Silver is the release target; Gold is a non-goal for v0.1.0. Gold adds:

- **`devices`** — a real hardware model / firmware / serial identifier
  surfaced via `DeviceInfo.hw_version` / `.sw_version`. Requires pulling
  from Nightscout's `devicestatus.pump` in a structured way and picking a
  representative pump model when a user switches devices mid-window.
- **`entity-category`** — the disabled-by-default diagnostic sensors
  (`loop_reason`, `care_last_note`, stats profile/LBGI/HBGI/AGP) need
  `EntityCategory.DIAGNOSTIC`.
- **`entity-device-class`** — audit pass to assign device classes where
  HA has a fitting one (today we only use `BATTERY`, `CONNECTIVITY`,
  `TIMESTAMP`, `BATTERY_CHARGING`, `RUNNING`).
- **Stricter typing** — enable `strict = true` in pyright across the
  whole integration. Today the API/coordinator modules are strict but
  `config_flow.py` has a few `Any`-typed returns where HA's types are
  imprecise.

### Full AAPS write-back

Right now Careportal is read-only. A future release can:

- Create Meal Bolus / Carbs / Note entries via
  `POST /api/v3/treatments`.
- Adjust the active profile via `POST /api/v3/profile`.
- Add an `action: create_treatment` service with a schema that mirrors
  the Careportal form.

This needs the integration's token to carry `api:treatments:create`
scope and needs a deliberate UX for confirming writes (HA service calls
that create insulin boluses deserve a sanity check).

### Loop predictions overlayed on the BG chart

The `loop_pred_bgs` sensor already ships the raw prediction arrays
(IOB / ZT / UAM / COB). Drawing them as thin overlay series on the
6 h BG chart in `apexcharts-card` requires either:

- A `data_generator` card per prediction series iterating
  `hass.states['sensor.nightscout_v3_loop_pred_bgs'].attributes.*`, or
- A pre-processed flat list the coordinator emits as per-series
  attributes (analogous to the `p5_by_hour` restructuring done for AGP).

The second is cleaner and matches how AGP works today. It's a
~50 LOC coordinator change plus dashboard-side glue.

### xDrip+ upload-only bridge

A read-only companion that accepts xDrip+'s upload format and relays
it to the configured Nightscout instance. Would live outside this
integration as a separate HACS package, but mentioned here because the
architecture (HTTP edge → capability probe → coordinator) is reusable.

## Things that will never land here

- **Proprietary-cloud pump integration** (Medtronic CareLink, Tandem
  t:connect, Dexcom Clarity direct). Those belong in their own
  integrations; Nightscout is the abstraction layer we already have.
- **Closed-loop control surface** from HA. Do not. Full stop.

## Contributing a roadmap item

Open an issue referencing this doc before starting work, so we can
scope against the Silver/Gold gates and the test-only-against-DevInstance
rule early. See `CONTRIBUTING.md`.
