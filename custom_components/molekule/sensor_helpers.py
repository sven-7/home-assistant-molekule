"""Sensor selection derived from device capabilities and available fields."""
from __future__ import annotations

try:
    from .capabilities import DeviceCapabilities
except ImportError:
    from capabilities import DeviceCapabilities

_SENSOR_FIELDS: dict[str, set[str]] = {
    "air_quality": {"aqi"},
    "peco_filter": {"pecoFilter"},
    "pre_filter": {"preFilter", "prefilter", "pre_filter"},
    "humidity": {"RH"},
    "pm25": {"PM2_5"},
    "pm10": {"PM10"},
    "voc": {"TVOC"},
    "co2": {"CO2"},
}

_SENSOR_DATA_SENSORS = {"humidity", "pm25", "pm10", "voc", "co2"}


def sensor_keys_for_capabilities(
    caps: DeviceCapabilities, available_fields: set[str]
) -> list[str]:
    """Return the supported sensor keys for a device."""
    keys: list[str] = []
    for sensor_key in (
        "air_quality",
        "peco_filter",
        "pre_filter",
        "humidity",
        "pm25",
        "pm10",
        "voc",
        "co2",
    ):
        if sensor_key not in caps.supported_sensors:
            continue
        if sensor_key in _SENSOR_DATA_SENSORS:
            if caps.has_sensor_data:
                keys.append(sensor_key)
            continue
        if available_fields & _SENSOR_FIELDS[sensor_key]:
            keys.append(sensor_key)
    return keys
