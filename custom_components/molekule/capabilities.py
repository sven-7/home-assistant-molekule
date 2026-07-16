"""Model capability resolution for Molekule devices."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

try:
    from .const import (
        API_MODE_SMART,
        PRESET_AUTO,
        PRESET_AUTO_PROTECT,
        PRESET_BOOST,
        PRESET_MANUAL,
        PRESET_SILENT,
    )
except ImportError:
    from const import (
        API_MODE_SMART,
        PRESET_AUTO,
        PRESET_AUTO_PROTECT,
        PRESET_BOOST,
        PRESET_MANUAL,
        PRESET_SILENT,
    )

FanControl = Literal["speed", "presets"]


@dataclass(frozen=True)
class DeviceCapabilities:
    family: str
    fan_control: FanControl
    max_fan_speed: int | None
    preset_modes: tuple[str, ...]
    has_sensor_data: bool
    supported_sensors: frozenset[str]
    auto_api_mode: str = API_MODE_SMART


# Canonical families
FAMILY_MINI_PLUS = "mini_plus"
FAMILY_ORIGINAL = "original"
FAMILY_AIR_PRO = "air_pro"
FAMILY_UNKNOWN = "unknown"

# Map exact API subProduct.name values → family.
MODEL_ALIASES: dict[str, str] = {
    "Air Mini Plus": FAMILY_MINI_PLUS,
    "Molekule Air": FAMILY_ORIGINAL,
    "Molekule Air Pro": FAMILY_AIR_PRO,
}

_CAPABILITIES: dict[str, DeviceCapabilities] = {
    FAMILY_MINI_PLUS: DeviceCapabilities(
        family=FAMILY_MINI_PLUS,
        fan_control="speed",
        max_fan_speed=5,
        preset_modes=(PRESET_AUTO_PROTECT, PRESET_MANUAL),
        has_sensor_data=True,
        supported_sensors=frozenset(
            {"air_quality", "peco_filter", "humidity", "pm25", "pm10", "voc", "co2"}
        ),
    ),
    FAMILY_ORIGINAL: DeviceCapabilities(
        family=FAMILY_ORIGINAL,
        fan_control="presets",
        max_fan_speed=None,
        preset_modes=(PRESET_SILENT, PRESET_AUTO, PRESET_BOOST),
        has_sensor_data=False,
        supported_sensors=frozenset({"air_quality", "peco_filter", "pre_filter"}),
    ),
    FAMILY_AIR_PRO: DeviceCapabilities(
        family=FAMILY_AIR_PRO,
        fan_control="speed",
        max_fan_speed=6,
        preset_modes=(PRESET_AUTO_PROTECT, PRESET_MANUAL),
        has_sensor_data=True,
        supported_sensors=frozenset(
            {"air_quality", "peco_filter", "humidity", "pm25", "pm10", "voc", "co2"}
        ),
    ),
}

_DEFAULT = DeviceCapabilities(
    family=FAMILY_UNKNOWN,
    fan_control="speed",
    max_fan_speed=3,
    preset_modes=(PRESET_MANUAL,),
    has_sensor_data=False,
    supported_sensors=frozenset({"air_quality", "peco_filter"}),
)


def resolve_model_name(raw: str | None) -> str:
    if not raw:
        return FAMILY_UNKNOWN
    if raw in MODEL_ALIASES:
        return MODEL_ALIASES[raw]
    lowered = raw.lower()
    if "mini" in lowered:
        return FAMILY_MINI_PLUS
    if "pro" in lowered:
        return FAMILY_AIR_PRO
    if raw == "Molekule Air" or lowered.strip() == "molekule air":
        return FAMILY_ORIGINAL
    return FAMILY_UNKNOWN


def get_capabilities(model_or_family: str) -> DeviceCapabilities:
    family = model_or_family
    if family not in _CAPABILITIES:
        family = resolve_model_name(model_or_family)
    return _CAPABILITIES.get(family, _DEFAULT)


def infer_capabilities(device: dict[str, Any]) -> DeviceCapabilities:
    """Best-effort caps for unknown models from a live payload."""
    raw = (device.get("subProduct") or {}).get("name")
    family = resolve_model_name(raw)
    if family != FAMILY_UNKNOWN:
        return get_capabilities(family)

    sensors = {"peco_filter"}
    if device.get("aqi") is not None:
        sensors.add("air_quality")
    if "preFilter" in device or "prefilter" in {k.lower() for k in device}:
        sensors.add("pre_filter")

    mode = str(device.get("mode", "")).lower()
    presets: list[str] = [PRESET_MANUAL]
    if mode == API_MODE_SMART or "smart" in device:
        presets = [PRESET_AUTO_PROTECT, PRESET_MANUAL]

    try:
        speed = int(device.get("fanspeed") or 1)
    except (TypeError, ValueError):
        speed = 1

    return DeviceCapabilities(
        family=FAMILY_UNKNOWN,
        fan_control="speed",
        max_fan_speed=max(speed, 3),
        preset_modes=tuple(presets),
        has_sensor_data=False,
        supported_sensors=frozenset(sensors),
    )


def capabilities_for_device(device: dict[str, Any]) -> DeviceCapabilities:
    raw = (device.get("subProduct") or {}).get("name")
    family = resolve_model_name(raw)
    if family == FAMILY_UNKNOWN:
        return infer_capabilities(device)
    return get_capabilities(family)
