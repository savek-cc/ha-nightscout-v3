"""DataUpdateCoordinator with staggered fast / change-detect / stats cycles."""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
        self._carbs_today: float = 0.0
        self._last_note: str | None = None

    @property
    def capabilities(self) -> ServerCapabilities:
        return self._capabilities

    @property
    def client(self) -> NightscoutV3Client:
        return self._client

    @property
    def store(self) -> HistoryStore:
        return self._store

    @property
    def last_tick_summary(self) -> dict[str, int]:
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
            since = newest.newest_date if newest else _day_ago_ms(STATS_HISTORY_MAX_DAYS)
            fresh = await self._client.get_entries(limit=1000, since_date=since, last_modified=self._last_modified_cache.get("entries", 0))
            if fresh:
                await self._store.insert_batch(fresh)
                await self._store.update_sync_state(
                    "entries",
                    last_modified=entries_lm,
                    oldest_date=min(int(e["date"]) for e in fresh),
                    newest_date=max(int(e["date"]) for e in fresh),
                )
                self._stats_dirty = True
            self._last_modified_cache["entries"] = entries_lm

        if treatments_lm > self._last_modified_cache.get("treatments", 0):
            await self._refresh_treatment_aware_features()
            self._last_modified_cache["treatments"] = treatments_lm

    async def _refresh_treatment_aware_features(self) -> None:
        for slot, event in _TREATMENT_AGE_EVENTS.items():
            t = await self._client.get_treatments(event_type=event, limit=1)
            self._treatment_age_cache[slot] = _parse_created(t[0]) if t else None

        meals = await self._client.get_treatments(event_type="Meal Bolus", limit=1)
        if not meals:
            meals = await self._client.get_treatments(event_type="Carbs", limit=1)
        self._last_meal = meals[0] if meals else None

        since = _day_ago_ms(1)
        today = await self._client.get_treatments(since_date=since, limit=200)
        self._carbs_today = sum(float(t.get("carbs") or 0) for t in today)

        note_candidates = await self._client.get_treatments(event_type="Note", limit=1)
        if not note_candidates:
            note_candidates = await self._client.get_treatments(event_type="Announcement", limit=1)
        self._last_note = (note_candidates[0].get("notes") if note_candidates else None)

    async def _stats_cycle(self) -> None:
        enabled = sorted(set(self.config_entry.options.get(OPT_STATS_WINDOWS, [MANDATORY_STATS_WINDOW])) |
                         {MANDATORY_STATS_WINDOW})
        low = self.config_entry.options.get(OPT_TIR_LOW, DEFAULT_TIR_LOW)
        high = self.config_entry.options.get(OPT_TIR_HIGH, DEFAULT_TIR_HIGH)
        vlow = self.config_entry.options.get(OPT_TIR_VERY_LOW, DEFAULT_TIR_VERY_LOW)
        vhigh = self.config_entry.options.get(OPT_TIR_VERY_HIGH, DEFAULT_TIR_VERY_HIGH)

        self._stats: dict[int, dict[str, Any]] = {}
        for w in enabled:
            if w not in ALLOWED_STATS_WINDOWS:
                continue
            entries = await self._store.entries_in_window(days=w)
            payload = compute_all(entries, window_days=w,
                                  tir_low=low, tir_high=high,
                                  tir_very_low=vlow, tir_very_high=vhigh)
            payload["hourly_profile_summary"] = payload["hourly_profile"]
            payload["agp_summary"] = payload["agp_percentiles"]
            self._stats[w] = payload
            await self._store.set_stats_cache(w, payload)
        self._stats_dirty = False

    def _build_payload(self) -> dict[str, Any]:
        entries = getattr(self, "_latest_entries", [])
        ds = getattr(self, "_latest_devicestatus", None) or {}
        stats = getattr(self, "_stats", {})
        now = datetime.now(timezone.utc)

        bg = _bg_block(entries, now)
        pump = _pump_block(ds)
        loop = _loop_block(ds, now)
        uploader = _uploader_block(ds, now)
        care = _care_block(self._treatment_age_cache, now, self._last_meal, self._carbs_today, self._last_note)

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


def _bg_block(entries: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    if not entries:
        return {"current_sgv": None, "delta_mgdl": None, "direction": None,
                "trend_arrow": None, "stale_minutes": None}
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


def _pump_block(ds: dict[str, Any]) -> dict[str, Any]:
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
        "temp_basal_rate": _temp_basal_rate(ds),
        "temp_basal_remaining": extended.get("TempBasalRemaining"),
        "active_profile": extended.get("ActiveProfile"),
        "last_bolus_time": last_bolus_time,
        "last_bolus_amount": extended.get("LastBolusAmount"),
    }


def _temp_basal_rate(ds: dict[str, Any]) -> float | None:
    """Primary: openaps.enacted.rate; fallback None (treatments lookup is in change-detect)."""
    openaps = ds.get("openaps") or {}
    enacted = openaps.get("enacted") or {}
    return enacted.get("rate")


def _parse_last_bolus(raw: Any) -> str | None:
    """AAPS emits strings like '21.04. 19:15' — surface as-is; consumers can render."""
    if raw in (None, "", "null"):
        return None
    return str(raw)


def _loop_block(ds: dict[str, Any], now: datetime) -> dict[str, Any]:
    if not ds:
        return {"mode": None, "active": False, "eventual_bg": None, "target_bg": None,
                "iob": None, "basaliob": None, "activity": None, "cob": None,
                "sensitivity_ratio": None, "reason": None, "pred_bgs": None,
                "last_enacted_age_minutes": None}
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
    return {
        "battery_percent": ds.get("uploaderBattery") or (((ds.get("pump") or {}).get("battery") or {}).get("percent")),
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
