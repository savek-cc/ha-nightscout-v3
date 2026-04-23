"""DataUpdateCoordinator with staggered fast / change-detect / stats cycles."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api.capabilities import ServerCapabilities
from .api.client import NightscoutV3Client
from .api.exceptions import ApiError, AuthError
from .const import (
    ALLOWED_STATS_WINDOWS,
    COORDINATOR_TICK_SECONDS,
    DEFAULT_POLL_CHANGE_DETECT_MINUTES,
    DEFAULT_POLL_FAST_SECONDS,
    DEFAULT_POLL_STATS_MINUTES,
    DEFAULT_TIR_HIGH,
    DEFAULT_TIR_LOW,
    DEFAULT_TIR_VERY_HIGH,
    DEFAULT_TIR_VERY_LOW,
    DOMAIN,
    MANDATORY_STATS_WINDOW,
    OPT_POLL_CHANGE_DETECT_MINUTES,
    OPT_POLL_FAST_SECONDS,
    OPT_POLL_STATS_MINUTES,
    OPT_STATS_WINDOWS,
    OPT_TIR_HIGH,
    OPT_TIR_LOW,
    OPT_TIR_VERY_HIGH,
    OPT_TIR_VERY_LOW,
    STATS_HISTORY_MAX_DAYS,
)
from .history_store import HistoryStore
from .statistics import compute_all

_LOGGER = logging.getLogger(__name__)

_TREATMENT_AGE_EVENTS = {
    "sensor": "Sensor Change",
    "site": "Site Change",
    "insulin": "Insulin Change",
    "battery": "Pump Battery Change",
}

_DIRECTION_TO_ARROW = {
    "DoubleUp": "⇈",
    "SingleUp": "↑",
    "FortyFiveUp": "↗",
    "Flat": "→",
    "FortyFiveDown": "↘",
    "SingleDown": "↓",
    "DoubleDown": "⇊",
    "NOT COMPUTABLE": "?",
    "NONE": "-",
}


class NightscoutCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single coordinator with staggered update cycles."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: NightscoutV3Client,
        capabilities: ServerCapabilities,
        store: HistoryStore,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Nightscout coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{entry.entry_id}",
            update_interval=timedelta(seconds=COORDINATOR_TICK_SECONDS),
            config_entry=entry,
        )
        self._client = client
        self._capabilities = capabilities
        self._store = store
        self._tick = 0
        self._stats_dirty = True
        self._last_tick_summary: dict[str, int] = {}
        self._last_modified_cache: dict[str, int] = {}
        self._treatment_age_cache: dict[str, datetime | None] = {}
        self._last_meal: dict[str, Any] | None = None
        self._recent_treatments: list[dict[str, Any]] = []
        self._last_note: str | None = None
        # explicit defaults for data populated in cycle methods —
        # previously these were read via `getattr(self, ..., default)`
        # fallbacks that hid attribute-lifecycle bugs.
        self._latest_entries: list[dict[str, Any]] = []
        self._latest_devicestatus: dict[str, Any] | None = None
        self._stats: dict[int, dict[str, Any]] = {}

    @property
    def capabilities(self) -> ServerCapabilities:
        """Return the cached server capabilities."""
        return self._capabilities

    @property
    def client(self) -> NightscoutV3Client:
        """Return the Nightscout v3 API client."""
        return self._client

    @property
    def store(self) -> HistoryStore:
        """Return the history store backing this coordinator."""
        return self._store

    @property
    def last_tick_summary(self) -> dict[str, int]:
        """Return a copy of the last tick's timing summary."""
        return dict(self._last_tick_summary)

    async def _async_update_data(self) -> dict[str, Any]:
        """Run the appropriate cycles for this tick."""
        self._tick += 1
        started = time.monotonic()
        opts = self.config_entry.options
        fast_secs = opts.get(OPT_POLL_FAST_SECONDS, DEFAULT_POLL_FAST_SECONDS)
        change_mins = opts.get(OPT_POLL_CHANGE_DETECT_MINUTES, DEFAULT_POLL_CHANGE_DETECT_MINUTES)
        stats_mins = opts.get(OPT_POLL_STATS_MINUTES, DEFAULT_POLL_STATS_MINUTES)

        fast_every = max(1, round(fast_secs / COORDINATOR_TICK_SECONDS))
        change_every = max(1, round(change_mins * 60 / COORDINATOR_TICK_SECONDS))
        stats_every = max(1, round(stats_mins * 60 / COORDINATOR_TICK_SECONDS))

        try:
            if self._tick % fast_every == 0 or self._tick == 1:
                await self._fast_cycle()
            if self._tick % change_every == 0 or self._tick == 1:
                await self._change_detect_cycle()
            if self._stats_dirty or self._tick % stats_every == 0 or self._tick == 1:
                await self._stats_cycle()
        except AuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except ApiError as exc:
            raise UpdateFailed(str(exc)) from exc
        except (TimeoutError, OSError) as exc:
            raise UpdateFailed(f"Network error: {exc}") from exc

        self._last_tick_summary = {
            "tick": self._tick,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        return self._build_payload()

    async def _fast_cycle(self) -> None:
        entries = await self._client.get_entries(limit=2, since_date=_day_ago_ms(1))
        ds = await self._client.get_devicestatus(limit=1)
        self._latest_entries = entries
        self._latest_devicestatus = ds[0] if ds else None
        if entries:
            inserted = await self._store.insert_batch(entries)
            if inserted:
                self._stats_dirty = True

    async def _change_detect_cycle(self) -> None:
        lm = await self._client.get_last_modified()
        collections = (lm.get("collections") or {}) if isinstance(lm, dict) else {}
        entries_lm = int(collections.get("entries") or 0)
        treatments_lm = int(collections.get("treatments") or 0)

        if entries_lm > self._last_modified_cache.get("entries", 0):
            newest = await self._store.get_sync_state("entries")
            if newest is None:
                await self._backfill_entries(entries_lm)
            else:
                await self._incremental_entries(entries_lm, newest)
            self._last_modified_cache["entries"] = entries_lm

        if treatments_lm > self._last_modified_cache.get("treatments", 0):
            await self._refresh_treatment_aware_features()
            self._last_modified_cache["treatments"] = treatments_lm

    async def _backfill_entries(self, entries_lm: int) -> None:
        """Paginate backwards until we cover STATS_HISTORY_MAX_DAYS (initial sync).

        Two v3-API quirks shaped this loop:

        1. `srvModified` is absent on legacy (pre-v3-write) entries, so a
           `srvModified$gt=0` filter rejects the entire history. Not sent here.

        2. v3's parseFilter builds `{date: {$lt}, date: {$gte}}` as a plain
           object — the second key silently overwrites the first. Sending
           both `date$lt` *and* `date$gte` on the same request yields only
           the `$gte` half; the server returns the newest 1000 docs every
           time and the loop runs away. So the 90d cutoff is enforced
           client-side, not via `since_date` on the wire.

        A hard iteration cap and a "before_date is not advancing" guard
        are belt-and-braces against future server changes that could
        re-introduce a runaway loop.
        """
        cutoff = _day_ago_ms(STATS_HISTORY_MAX_DAYS)
        before: int | None = None
        overall_oldest: int | None = None
        overall_newest: int | None = None
        max_iters = 200
        for _iter_n in range(1, max_iters + 1):
            batch = await self._client.get_entries(limit=1000, before_date=before)
            if not batch:
                break
            server_min = min(int(e["date"]) for e in batch)
            in_window = [e for e in batch if int(e["date"]) >= cutoff]
            if in_window:
                await self._store.insert_batch(in_window)
                dates = [int(e["date"]) for e in in_window]
                b_min, b_max = min(dates), max(dates)
                overall_oldest = b_min if overall_oldest is None else min(overall_oldest, b_min)
                overall_newest = b_max if overall_newest is None else max(overall_newest, b_max)
            if len(batch) < 1000 or server_min <= cutoff:
                break
            if before is not None and server_min >= before:
                _LOGGER.error(
                    "nightscout_v3 backfill: server's before_date filter not "
                    "advancing (got min=%d, expected <%d). Stopping to prevent "
                    "runaway loop.",
                    server_min,
                    before,
                )
                break
            before = server_min
        else:
            _LOGGER.warning(
                "nightscout_v3 backfill reached max_iters=%d without short batch; stopping anyway.",
                max_iters,
            )
        if overall_oldest is not None and overall_newest is not None:
            await self._store.update_sync_state(
                "entries",
                last_modified=entries_lm,
                oldest_date=overall_oldest,
                newest_date=overall_newest,
            )
            self._stats_dirty = True

    async def _incremental_entries(self, entries_lm: int, newest: Any) -> None:
        """Fetch entries newer than our last-seen newest_date."""
        fresh = await self._client.get_entries(limit=1000, since_date=newest.newest_date)
        if fresh:
            await self._store.insert_batch(fresh)
            dates = [int(e["date"]) for e in fresh]
            await self._store.update_sync_state(
                "entries",
                last_modified=entries_lm,
                oldest_date=min(newest.oldest_date, min(dates)),
                newest_date=max(newest.newest_date, max(dates)),
            )
            self._stats_dirty = True

    async def _refresh_treatment_aware_features(self) -> None:
        for slot, event in _TREATMENT_AGE_EVENTS.items():
            t = await self._client.get_treatments(event_type=event, limit=1)
            self._treatment_age_cache[slot] = _parse_created(t[0]) if t else None

        meals = await self._client.get_treatments(event_type="Meal Bolus", limit=1)
        if not meals:
            meals = await self._client.get_treatments(event_type="Carbs", limit=1)
        self._last_meal = meals[0] if meals else None

        # 48h window: covers "since local midnight" even far from UTC,
        # and lets carbs_today stay correct across day boundaries without a
        # refresh (re-filter happens at _build_payload time).
        since = _day_ago_ms(2)
        self._recent_treatments = await self._client.get_treatments(
            since_date=since,
            limit=500,
        )

        note_candidates = await self._client.get_treatments(event_type="Note", limit=1)
        if not note_candidates:
            note_candidates = await self._client.get_treatments(event_type="Announcement", limit=1)
        self._last_note = note_candidates[0].get("notes") if note_candidates else None

    async def _stats_cycle(self) -> None:
        enabled = sorted(
            set(self.config_entry.options.get(OPT_STATS_WINDOWS, [MANDATORY_STATS_WINDOW]))
            | {MANDATORY_STATS_WINDOW}
        )
        low = self.config_entry.options.get(OPT_TIR_LOW, DEFAULT_TIR_LOW)
        high = self.config_entry.options.get(OPT_TIR_HIGH, DEFAULT_TIR_HIGH)
        vlow = self.config_entry.options.get(OPT_TIR_VERY_LOW, DEFAULT_TIR_VERY_LOW)
        vhigh = self.config_entry.options.get(OPT_TIR_VERY_HIGH, DEFAULT_TIR_VERY_HIGH)

        self._stats = {}
        for w in enabled:
            if w not in ALLOWED_STATS_WINDOWS:
                continue
            entries = await self._store.entries_in_window(days=w)
            payload = compute_all(
                entries,
                window_days=w,
                tir_low=low,
                tir_high=high,
                tir_very_low=vlow,
                tir_very_high=vhigh,
            )
            payload["hourly_profile_summary"] = payload["hourly_profile"]
            agp_rows = payload["agp_percentiles"]
            payload["agp_summary"] = {
                "sample_count": sum(int(row.get("n", 0)) for row in agp_rows),
                "items": agp_rows,
                "p5_by_hour": [row["p5"] for row in agp_rows],
                "p25_by_hour": [row["p25"] for row in agp_rows],
                "p50_by_hour": [row["p50"] for row in agp_rows],
                "p75_by_hour": [row["p75"] for row in agp_rows],
                "p95_by_hour": [row["p95"] for row in agp_rows],
            }
            self._stats[w] = payload
            await self._store.set_stats_cache(w, payload)
        self._stats_dirty = False

    def _build_payload(self) -> dict[str, Any]:
        entries = self._latest_entries
        ds = self._latest_devicestatus or {}
        stats = self._stats
        now = datetime.now(UTC)
        carbs_today = _carbs_since_local_midnight(self._recent_treatments, self.hass)

        bg = _bg_block(entries, now)
        pump = _pump_block(ds, self._recent_treatments, now)
        loop = _loop_block(ds, now)
        uploader = _uploader_block(ds, now)
        care = _care_block(
            self._treatment_age_cache, now, self._last_meal, carbs_today, self._last_note
        )

        return {
            "bg": bg,
            "pump": pump,
            "loop": loop,
            "uploader": uploader,
            "care": care,
            "stats": {f"{w}d": payload for w, payload in stats.items()},
        }


# ---------- extractor helpers (pure) ----------


def _day_ago_ms(days: int) -> int:
    return int((time.time() - days * 86_400) * 1000)


def _parse_created(t: dict[str, Any]) -> datetime | None:
    raw = t.get("created_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _carbs_since_local_midnight(
    treatments: list[dict[str, Any]],
    hass: HomeAssistant,
) -> float:
    """Sum `carbs` from treatments with `created_at` >= today's local midnight.

    Recomputed on every build so the value stays correct across day
    rollovers and even when no new treatments come in.
    """
    now_local = dt_util.now()
    midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    total = 0.0
    for t in treatments:
        carbs = t.get("carbs")
        if not carbs:
            continue
        created = _parse_created(t)
        if created is None:
            continue
        if created >= midnight:
            total += float(carbs)
    return total


def _bg_block(entries: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    if not entries:
        return {
            "current_sgv": None,
            "delta_mgdl": None,
            "direction": None,
            "trend_arrow": None,
            "stale_minutes": None,
        }
    latest = entries[0]
    prev = entries[1] if len(entries) > 1 else None
    stale_minutes = int((now.timestamp() * 1000 - int(latest["date"])) / 60000)
    return {
        "current_sgv": int(latest["sgv"]),
        "delta_mgdl": int(latest["sgv"] - prev["sgv"]) if prev else 0,
        "direction": latest.get("direction"),
        "trend_arrow": _DIRECTION_TO_ARROW.get(latest.get("direction", ""), "?"),
        "stale_minutes": stale_minutes,
    }


def _pump_block(
    ds: dict[str, Any],
    recent_treatments: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    pump = ds.get("pump") or {}
    extended = pump.get("extended") or {}
    battery = (pump.get("battery") or {}).get("percent")
    status_text = (pump.get("status") or {}).get("status")
    last_bolus_time = _parse_last_bolus(extended.get("LastBolus"))
    return {
        "reservoir": pump.get("reservoir"),
        "battery_percent": battery,
        "status_text": status_text,
        "base_basal": extended.get("BaseBasalRate"),
        "temp_basal_rate": _temp_basal_rate(ds, recent_treatments, now),
        "temp_basal_remaining": extended.get("TempBasalRemaining"),
        "active_profile": extended.get("ActiveProfile"),
        "last_bolus_time": last_bolus_time,
        "last_bolus_amount": extended.get("LastBolusAmount"),
    }


def _temp_basal_rate(
    ds: dict[str, Any],
    recent_treatments: list[dict[str, Any]],
    now: datetime,
) -> float | None:
    """Return the currently-running temp basal rate in U/h, or None.

    AAPS does not reliably put the rate in the devicestatus document
    (observed: 10 successive snapshots during an active temp basal, all
    with `TempBasalAbsoluteRate=None` and `openaps.enacted=None`). The
    authoritative source is the latest `eventType=Temp Basal` treatment
    — it has `rate` (U/h) and `duration` (min). Filter out treatments
    whose window has already elapsed.

    Fall back to devicestatus fields only if no active treatment is
    found — useful on servers that *do* populate them.
    """
    for t in recent_treatments:
        if t.get("eventType") != "Temp Basal":
            continue
        created = _parse_created(t)
        if created is None:
            continue
        duration_min = t.get("duration")
        if duration_min is None:
            continue
        end = created + timedelta(minutes=float(duration_min))
        if end < now:
            continue
        rate = t.get("rate")
        return float(rate) if rate is not None else None
    ext = (ds.get("pump") or {}).get("extended") or {}
    if (rate := ext.get("TempBasalAbsoluteRate")) is not None:
        return float(rate)
    enacted = (ds.get("openaps") or {}).get("enacted") or {}
    rate = enacted.get("rate")
    if rate is None or rate < 0:
        return None
    return float(rate)


def _parse_last_bolus(raw: Any) -> datetime | None:
    """Parse AAPS' `pump.extended.LastBolus` free-text timestamp.

    AAPS emits `DD.MM.YY HH:MM` (with the 2-digit year) or the older
    `DD.MM. HH:MM` (no year — assumed current). Anything else returns
    None so HA surfaces the sensor as unavailable rather than blowing
    up the timestamp device class.
    """
    if raw in (None, "", "null"):
        return None
    s = str(raw).strip()
    now = dt_util.now()
    for fmt in ("%d.%m.%y %H:%M", "%d.%m. %H:%M"):
        try:
            parsed = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if fmt == "%d.%m. %H:%M":
            parsed = parsed.replace(year=now.year)
        return parsed.replace(tzinfo=now.tzinfo)
    return None


def _loop_block(ds: dict[str, Any], now: datetime) -> dict[str, Any]:
    if not ds:
        return {
            "mode": None,
            "active": False,
            "eventual_bg": None,
            "target_bg": None,
            "iob": None,
            "basaliob": None,
            "activity": None,
            "cob": None,
            "sensitivity_ratio": None,
            "reason": None,
            "pred_bgs": None,
            "last_enacted_age_minutes": None,
        }
    openaps = ds.get("openaps") or {}
    iob = openaps.get("iob") or {}
    suggested = openaps.get("suggested") or {}
    created = _parse_created(ds)
    age_min = int((now - created).total_seconds() / 60) if created else None
    active = age_min is not None and age_min <= 10 and bool(openaps)
    pump_status = ((ds.get("pump") or {}).get("status") or {}).get("status", "")
    if "suspend" in pump_status.lower():
        mode = "Suspended"
    elif active:
        mode = "Closed"
    else:
        mode = "Open"
    return {
        "mode": mode,
        "active": active,
        "eventual_bg": suggested.get("eventualBG"),
        "target_bg": suggested.get("targetBG"),
        "iob": iob.get("iob"),
        "basaliob": iob.get("basaliob"),
        "activity": iob.get("activity"),
        "cob": suggested.get("COB"),
        "sensitivity_ratio": suggested.get("sensitivityRatio"),
        "reason": suggested.get("reason"),
        "pred_bgs": suggested.get("predBGs"),
        "last_enacted_age_minutes": age_min,
    }


def _uploader_block(ds: dict[str, Any], now: datetime) -> dict[str, Any]:
    if not ds:
        return {"battery_percent": None, "online": False, "charging": None}
    created = _parse_created(ds)
    age_min = int((now - created).total_seconds() / 60) if created else None
    # `uploaderBattery` is the phone/receiver battery. Never fall back
    # to pump.battery — that's a different device and would mislabel
    # the reading on the uploader sensor.
    return {
        "battery_percent": ds.get("uploaderBattery"),
        "online": age_min is not None and age_min < 15,
        "charging": ds.get("isCharging"),
    }


def _care_block(
    ages: dict[str, datetime | None],
    now: datetime,
    last_meal: dict[str, Any] | None,
    carbs_today: float,
    last_note: str | None,
) -> dict[str, Any]:
    def _age_days(slot: str) -> float | None:
        d = ages.get(slot)
        return round((now - d).total_seconds() / 86_400, 2) if d else None

    return {
        "sage_days": _age_days("sensor"),
        "cage_days": _age_days("site"),
        "iage_days": _age_days("insulin"),
        "bage_days": _age_days("battery"),
        "last_meal_carbs": (last_meal or {}).get("carbs"),
        "carbs_today": round(carbs_today, 2),
        "last_note": last_note,
    }
