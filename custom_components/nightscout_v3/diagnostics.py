"""Redacted diagnostics dump."""
from __future__ import annotations

import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .models import NightscoutConfigEntry

_TO_REDACT = {
    "url",
    "access_token",
    "api_secret",
    "identifier",
    "sub",
    "token",
    "reason",
    "notes",
    "note",
    "last_note",
    "enteredBy",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NightscoutConfigEntry
) -> dict[str, Any]:
    runtime = _collect_runtime(entry)
    return {
        "entry": {
            "entry_id": entry.entry_id,
            "data": async_redact_data(dict(entry.data), _TO_REDACT),
            "options": dict(entry.options),
            "title": entry.title,
            "unique_id": entry.unique_id,
        },
        "runtime": async_redact_data(runtime, _TO_REDACT),
    }


def _collect_runtime(entry: NightscoutConfigEntry) -> dict[str, Any]:
    data = getattr(entry, "runtime_data", None)
    if data is None:
        return {}
    jwt_state = data.jwt_manager.state
    jwt_info: dict[str, Any] = {}
    if jwt_state is not None:
        jwt_info = {
            "exp_in_seconds": max(0, int(jwt_state.exp - time.time())),
            "iat": jwt_state.iat,
            "exp": jwt_state.exp,
        }
    return {
        "coordinator": {
            "last_update_success": data.coordinator.last_update_success,
            **data.coordinator.last_tick_summary,
        },
        "jwt": jwt_info,
        "capabilities": data.capabilities.to_dict(),
        "snapshot": data.coordinator.data,
    }
