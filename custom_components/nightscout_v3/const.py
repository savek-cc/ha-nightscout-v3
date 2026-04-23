"""Constants for nightscout_v3."""

from __future__ import annotations

from typing import Final

from homeassistant.const import (
    CONF_ACCESS_TOKEN as HA_CONF_ACCESS_TOKEN,
)
from homeassistant.const import (
    CONF_URL as HA_CONF_URL,
)

DOMAIN: Final = "nightscout_v3"
MANUFACTURER: Final = "Nightscout"
MODEL: Final = "v3 API"

CONF_URL: Final = HA_CONF_URL
CONF_ACCESS_TOKEN: Final = HA_CONF_ACCESS_TOKEN
CONF_CAPABILITIES: Final = "capabilities"
CONF_CAPABILITIES_PROBED_AT: Final = "capabilities_probed_at"

OPT_ENABLED_FEATURES: Final = "enabled_features"
OPT_STATS_WINDOWS: Final = "stats_windows"
OPT_TIR_LOW: Final = "tir_low_threshold_mgdl"
OPT_TIR_HIGH: Final = "tir_high_threshold_mgdl"
OPT_TIR_VERY_LOW: Final = "tir_very_low_threshold_mgdl"
OPT_TIR_VERY_HIGH: Final = "tir_very_high_threshold_mgdl"
OPT_POLL_FAST_SECONDS: Final = "poll_fast_seconds"
OPT_POLL_CHANGE_DETECT_MINUTES: Final = "poll_change_detect_minutes"
OPT_POLL_STATS_MINUTES: Final = "poll_stats_minutes"

DEFAULT_POLL_FAST_SECONDS: Final = 60
DEFAULT_POLL_CHANGE_DETECT_MINUTES: Final = 5
DEFAULT_POLL_STATS_MINUTES: Final = 60
DEFAULT_TIR_LOW: Final = 70
DEFAULT_TIR_HIGH: Final = 180
DEFAULT_TIR_VERY_LOW: Final = 54
DEFAULT_TIR_VERY_HIGH: Final = 250

ALLOWED_STATS_WINDOWS: Final = (1, 7, 14, 30, 90)
MANDATORY_STATS_WINDOW: Final = 14
STATS_HISTORY_MAX_DAYS: Final = 90

COORDINATOR_TICK_SECONDS: Final = 30
JWT_BACKGROUND_REFRESH_HOURS: Final = 7
