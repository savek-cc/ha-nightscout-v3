"""Probe a Nightscout server to detect which feature families are available."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .client import NightscoutV3Client
from .exceptions import ApiError

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ServerCapabilities:
    """Snapshot of what this server can provide."""

    units: Literal["mg/dl", "mmol/L"]
    has_openaps: bool
    has_pump: bool
    has_uploader_battery: bool
    has_entries: bool
    has_treatments_sensor_change: bool
    has_treatments_site_change: bool
    has_treatments_insulin_change: bool
    has_treatments_pump_battery_change: bool
    last_probed_at_ms: int

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation for persistence."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerCapabilities:
        """Reconstruct a ServerCapabilities from its dict representation."""
        return cls(**data)


_SENSOR_CHANGE = "Sensor Change"
_SITE_CHANGE = "Site Change"
_INSULIN_CHANGE = "Insulin Change"
_PUMP_BATTERY_CHANGE = "Pump Battery Change"


async def _optional(label: str, coro: Any, default: Any) -> Any:
    try:
        return await coro
    except (TimeoutError, ApiError) as exc:
        _LOGGER.debug("Optional capability probe %s degraded: %s", label, exc)
        return default


async def probe_capabilities(client: NightscoutV3Client) -> ServerCapabilities:
    """Probe the server sequentially.

    Runs probes one at a time to avoid thundering-herd I/O against a cold
    Mongo cache on servers with years of data. Mandatory probes (status,
    entries) propagate errors; best-effort probes degrade to "feature not
    available" on transient failure instead of failing the whole flow.
    """
    status = await client.get_status()
    entries = await client.get_entries(limit=1)
    if not entries:
        raise ApiError("Server exposes no entries; cannot proceed")

    devicestatus = await _optional("devicestatus", client.get_devicestatus(limit=1), [])
    sensor = await _optional(
        "sensor_change",
        client.get_treatments(event_type=_SENSOR_CHANGE, limit=1),
        [],
    )
    site = await _optional(
        "site_change",
        client.get_treatments(event_type=_SITE_CHANGE, limit=1),
        [],
    )
    insulin = await _optional(
        "insulin_change",
        client.get_treatments(event_type=_INSULIN_CHANGE, limit=1),
        [],
    )
    battery = await _optional(
        "pump_battery_change",
        client.get_treatments(event_type=_PUMP_BATTERY_CHANGE, limit=1),
        [],
    )

    units_raw = (status.get("settings") or {}).get("units", "mg/dl")
    units: Literal["mg/dl", "mmol/L"] = "mmol/L" if units_raw == "mmol/L" else "mg/dl"

    latest_ds = devicestatus[0] if devicestatus else {}
    has_openaps = bool(latest_ds.get("openaps"))
    has_pump = bool(latest_ds.get("pump"))
    has_uploader_battery = "uploaderBattery" in latest_ds or bool(
        (latest_ds.get("pump") or {}).get("battery")
    )

    return ServerCapabilities(
        units=units,
        has_openaps=has_openaps,
        has_pump=has_pump,
        has_uploader_battery=has_uploader_battery,
        has_entries=bool(entries),
        has_treatments_sensor_change=bool(sensor),
        has_treatments_site_change=bool(site),
        has_treatments_insulin_change=bool(insulin),
        has_treatments_pump_battery_change=bool(battery),
        last_probed_at_ms=int(time.time() * 1000),
    )
