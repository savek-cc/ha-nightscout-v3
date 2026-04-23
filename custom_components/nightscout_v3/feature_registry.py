"""Single source of truth mapping features -> category, capability, extractor, platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, Platform, UnitOfTime

from .api.capabilities import ServerCapabilities


class Category(StrEnum):
    """Feature category grouping for the options flow."""

    BG = "bg"
    PUMP = "pump"
    LOOP = "loop"
    CAREPORTAL = "careportal"
    STATISTICS = "statistics"
    UPLOADER = "uploader"


@dataclass(frozen=True, slots=True)
class FeatureDef:
    """One feature that can become an entity."""

    key: str
    category: Category
    platform: Platform
    capability: Callable[[ServerCapabilities], bool]
    default_enabled: bool
    translation_key: str
    extractor: str  # dotted path into coordinator data (documented in coordinator.py)
    device_class: str | None = None
    state_class: str | None = None
    unit: str | None = None
    icon: str | None = None
    translation_placeholders: dict[str, str] | None = None


def _always(_c: ServerCapabilities) -> bool:
    return True


def _has_openaps(c: ServerCapabilities) -> bool:
    return c.has_openaps


def _has_pump(c: ServerCapabilities) -> bool:
    return c.has_pump


def _has_uploader(c: ServerCapabilities) -> bool:
    return c.has_uploader_battery


FEATURE_REGISTRY: list[FeatureDef] = [
    # -------- BG (spec §4.1) --------
    FeatureDef(
        "bg_current",
        Category.BG,
        Platform.SENSOR,
        _always,
        True,
        "bg_current",
        "bg.current_sgv",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
    ),
    FeatureDef(
        "bg_delta",
        Category.BG,
        Platform.SENSOR,
        _always,
        True,
        "bg_delta",
        "bg.delta_mgdl",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:plus-minus-variant",
    ),
    FeatureDef(
        "bg_direction",
        Category.BG,
        Platform.SENSOR,
        _always,
        True,
        "bg_direction",
        "bg.direction",
        icon="mdi:arrow-right",
    ),
    FeatureDef(
        "bg_trend_arrow",
        Category.BG,
        Platform.SENSOR,
        _always,
        True,
        "bg_trend_arrow",
        "bg.trend_arrow",
        icon="mdi:arrow-top-right",
    ),
    FeatureDef(
        "bg_stale_minutes",
        Category.BG,
        Platform.SENSOR,
        _always,
        True,
        "bg_stale_minutes",
        "bg.stale_minutes",
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfTime.MINUTES,
        icon="mdi:clock-alert-outline",
    ),
    # -------- PUMP (spec §4.2) --------
    FeatureDef(
        "pump_reservoir",
        Category.PUMP,
        Platform.SENSOR,
        _has_pump,
        True,
        "pump_reservoir",
        "pump.reservoir",
        state_class=SensorStateClass.MEASUREMENT,
        unit="U",
        icon="mdi:water-pump",
    ),
    FeatureDef(
        "pump_battery",
        Category.PUMP,
        Platform.SENSOR,
        _has_pump,
        True,
        "pump_battery",
        "pump.battery_percent",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        unit=PERCENTAGE,
        icon="mdi:battery",
    ),
    FeatureDef(
        "pump_status",
        Category.PUMP,
        Platform.SENSOR,
        _has_pump,
        True,
        "pump_status",
        "pump.status_text",
        icon="mdi:information-outline",
    ),
    FeatureDef(
        "pump_base_basal",
        Category.PUMP,
        Platform.SENSOR,
        _has_pump,
        True,
        "pump_base_basal",
        "pump.base_basal",
        state_class=SensorStateClass.MEASUREMENT,
        unit="U/h",
        icon="mdi:chart-line",
    ),
    FeatureDef(
        "pump_temp_basal_rate",
        Category.PUMP,
        Platform.SENSOR,
        _has_pump,
        True,
        "pump_temp_basal_rate",
        "pump.temp_basal_rate",
        state_class=SensorStateClass.MEASUREMENT,
        unit="U/h",
        icon="mdi:chart-line-variant",
    ),
    FeatureDef(
        "pump_temp_basal_remaining",
        Category.PUMP,
        Platform.SENSOR,
        _has_pump,
        True,
        "pump_temp_basal_remaining",
        "pump.temp_basal_remaining",
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfTime.MINUTES,
        icon="mdi:timer-sand",
    ),
    FeatureDef(
        "pump_active_profile",
        Category.PUMP,
        Platform.SENSOR,
        _has_pump,
        True,
        "pump_active_profile",
        "pump.active_profile",
        icon="mdi:account-cog",
    ),
    FeatureDef(
        "pump_last_bolus_time",
        Category.PUMP,
        Platform.SENSOR,
        _has_pump,
        True,
        "pump_last_bolus_time",
        "pump.last_bolus_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
    ),
    FeatureDef(
        "pump_last_bolus_amount",
        Category.PUMP,
        Platform.SENSOR,
        _has_pump,
        True,
        "pump_last_bolus_amount",
        "pump.last_bolus_amount",
        state_class=SensorStateClass.MEASUREMENT,
        unit="U",
        icon="mdi:needle",
    ),
    # -------- LOOP (spec §4.3) --------
    FeatureDef(
        "loop_mode",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        True,
        "loop_mode",
        "loop.mode",
        icon="mdi:refresh-auto",
    ),
    FeatureDef(
        "loop_active",
        Category.LOOP,
        Platform.BINARY_SENSOR,
        _has_openaps,
        True,
        "loop_active",
        "loop.active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    FeatureDef(
        "loop_eventual_bg",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        True,
        "loop_eventual_bg",
        "loop.eventual_bg",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:crystal-ball",
    ),
    FeatureDef(
        "loop_target_bg",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        True,
        "loop_target_bg",
        "loop.target_bg",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:target",
    ),
    FeatureDef(
        "loop_iob",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        True,
        "loop_iob",
        "loop.iob",
        state_class=SensorStateClass.MEASUREMENT,
        unit="U",
        icon="mdi:needle",
    ),
    FeatureDef(
        "loop_basaliob",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        True,
        "loop_basaliob",
        "loop.basaliob",
        state_class=SensorStateClass.MEASUREMENT,
        unit="U",
        icon="mdi:chart-line",
    ),
    FeatureDef(
        "loop_activity",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        True,
        "loop_activity",
        "loop.activity",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:pulse",
    ),
    FeatureDef(
        "loop_cob",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        True,
        "loop_cob",
        "loop.cob",
        state_class=SensorStateClass.MEASUREMENT,
        unit="g",
        icon="mdi:food-apple",
    ),
    FeatureDef(
        "loop_sensitivity_ratio",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        True,
        "loop_sensitivity_ratio",
        "loop.sensitivity_ratio",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:scale-balance",
    ),
    FeatureDef(
        "loop_reason",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        False,
        "loop_reason",
        "loop.reason",
        icon="mdi:message-text-outline",
    ),
    # Off by default: the state is always "unknown" (pred_bgs is a dict
    # surfaced via extra_state_attributes for apexcharts-card consumers).
    # On a plain sensor view it looks broken next to loop_eventual_bg.
    FeatureDef(
        "loop_pred_bgs",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        False,
        "loop_pred_bgs",
        "loop.pred_bgs",
        icon="mdi:chart-timeline-variant",
    ),
    FeatureDef(
        "loop_last_enacted_age_minutes",
        Category.LOOP,
        Platform.SENSOR,
        _has_openaps,
        True,
        "loop_last_enacted_age_minutes",
        "loop.last_enacted_age_minutes",
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfTime.MINUTES,
        icon="mdi:clock-outline",
    ),
    # -------- CAREPORTAL read-only (spec §4.4) --------
    FeatureDef(
        "care_sage_days",
        Category.CAREPORTAL,
        Platform.SENSOR,
        lambda c: c.has_treatments_sensor_change,
        True,
        "care_sage_days",
        "care.sage_days",
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfTime.DAYS,
        icon="mdi:radar",
    ),
    FeatureDef(
        "care_iage_days",
        Category.CAREPORTAL,
        Platform.SENSOR,
        lambda c: c.has_treatments_insulin_change,
        True,
        "care_iage_days",
        "care.iage_days",
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfTime.DAYS,
        icon="mdi:needle",
    ),
    FeatureDef(
        "care_cage_days",
        Category.CAREPORTAL,
        Platform.SENSOR,
        lambda c: c.has_treatments_site_change,
        True,
        "care_cage_days",
        "care.cage_days",
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfTime.DAYS,
        icon="mdi:bandage",
    ),
    FeatureDef(
        "care_bage_days",
        Category.CAREPORTAL,
        Platform.SENSOR,
        lambda c: c.has_treatments_pump_battery_change,
        True,
        "care_bage_days",
        "care.bage_days",
        state_class=SensorStateClass.MEASUREMENT,
        unit=UnitOfTime.DAYS,
        icon="mdi:battery",
    ),
    FeatureDef(
        "care_last_meal_carbs",
        Category.CAREPORTAL,
        Platform.SENSOR,
        _always,
        True,
        "care_last_meal_carbs",
        "care.last_meal_carbs",
        state_class=SensorStateClass.MEASUREMENT,
        unit="g",
        icon="mdi:food-apple",
    ),
    FeatureDef(
        "care_carbs_today",
        Category.CAREPORTAL,
        Platform.SENSOR,
        _always,
        True,
        "care_carbs_today",
        "care.carbs_today",
        state_class=SensorStateClass.TOTAL,
        unit="g",
        icon="mdi:food-apple-outline",
    ),
    FeatureDef(
        "care_last_note",
        Category.CAREPORTAL,
        Platform.SENSOR,
        _always,
        False,
        "care_last_note",
        "care.last_note",
        icon="mdi:note-outline",
    ),
    # -------- UPLOADER (spec §4.6) --------
    FeatureDef(
        "uploader_battery",
        Category.UPLOADER,
        Platform.SENSOR,
        _has_uploader,
        True,
        "uploader_battery",
        "uploader.battery_percent",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        unit=PERCENTAGE,
        icon="mdi:cellphone",
    ),
    FeatureDef(
        "uploader_online",
        Category.UPLOADER,
        Platform.BINARY_SENSOR,
        _has_uploader,
        True,
        "uploader_online",
        "uploader.online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    FeatureDef(
        "uploader_charging",
        Category.UPLOADER,
        Platform.BINARY_SENSOR,
        _has_uploader,
        True,
        "uploader_charging",
        "uploader.charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
]


def features_for_capabilities(caps: ServerCapabilities) -> list[FeatureDef]:
    """Return features whose capability is satisfied by `caps`."""
    return [f for f in FEATURE_REGISTRY if f.capability(caps)]


def stats_feature_defs(window_days: int) -> list[FeatureDef]:
    """Expand the 13-sensor stats bundle for one window (spec §4.5)."""
    w = window_days
    placeholders = {"window": str(w)}
    return [
        FeatureDef(
            f"stat_gmi_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_gmi",
            f"stats.{w}d.gmi_percent",
            state_class=SensorStateClass.MEASUREMENT,
            unit=PERCENTAGE,
            icon="mdi:diabetes",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_hba1c_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_hba1c",
            f"stats.{w}d.hba1c_dcct_percent",
            state_class=SensorStateClass.MEASUREMENT,
            unit=PERCENTAGE,
            icon="mdi:diabetes",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_tir_in_range_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_tir_in_range",
            f"stats.{w}d.tir_in_range_percent",
            state_class=SensorStateClass.MEASUREMENT,
            unit=PERCENTAGE,
            icon="mdi:timer-check",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_tir_low_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_tir_low",
            f"stats.{w}d.tir_low_percent",
            state_class=SensorStateClass.MEASUREMENT,
            unit=PERCENTAGE,
            icon="mdi:arrow-down-bold",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_tir_very_low_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_tir_very_low",
            f"stats.{w}d.tir_very_low_percent",
            state_class=SensorStateClass.MEASUREMENT,
            unit=PERCENTAGE,
            icon="mdi:alert-circle",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_tir_high_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_tir_high",
            f"stats.{w}d.tir_high_percent",
            state_class=SensorStateClass.MEASUREMENT,
            unit=PERCENTAGE,
            icon="mdi:arrow-up-bold",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_tir_very_high_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_tir_very_high",
            f"stats.{w}d.tir_very_high_percent",
            state_class=SensorStateClass.MEASUREMENT,
            unit=PERCENTAGE,
            icon="mdi:alert-decagram",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_mean_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_mean",
            f"stats.{w}d.mean_mgdl",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:sigma",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_sd_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_sd",
            f"stats.{w}d.sd_mgdl",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:chart-bell-curve",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_cv_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            True,
            "stat_cv",
            f"stats.{w}d.cv_percent",
            state_class=SensorStateClass.MEASUREMENT,
            unit=PERCENTAGE,
            icon="mdi:variable",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_lbgi_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            False,
            "stat_lbgi",
            f"stats.{w}d.lbgi",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:arrow-down-thin-circle-outline",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_hbgi_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            False,
            "stat_hbgi",
            f"stats.{w}d.hbgi",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:arrow-up-thin-circle-outline",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_hourly_profile_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            False,
            "stat_hourly_profile",
            f"stats.{w}d.hourly_profile_summary",
            icon="mdi:chart-line",
            translation_placeholders=placeholders,
        ),
        FeatureDef(
            f"stat_agp_{w}d",
            Category.STATISTICS,
            Platform.SENSOR,
            _always,
            False,
            "stat_agp",
            f"stats.{w}d.agp_summary",
            icon="mdi:chart-areaspline",
            translation_placeholders=placeholders,
        ),
    ]
