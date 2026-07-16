from capabilities import get_capabilities, resolve_model_name, infer_capabilities
from const import (
    PRESET_AUTO_PROTECT,
    PRESET_MANUAL,
    PRESET_SILENT,
    PRESET_AUTO,
    PRESET_BOOST,
)


def test_resolve_mini_plus_aliases():
    assert resolve_model_name("Air Mini Plus") == "mini_plus"


def test_mini_plus_capabilities():
    caps = get_capabilities("mini_plus")
    assert caps.fan_control == "speed"
    assert caps.max_fan_speed == 5
    assert PRESET_AUTO_PROTECT in caps.preset_modes
    assert PRESET_MANUAL in caps.preset_modes
    assert "peco_filter" in caps.supported_sensors
    assert "pre_filter" not in caps.supported_sensors
    assert caps.has_sensor_data is True


def test_original_capabilities():
    caps = get_capabilities("original")
    assert caps.fan_control == "presets"
    assert caps.max_fan_speed is None
    assert caps.preset_modes == (PRESET_SILENT, PRESET_AUTO, PRESET_BOOST)
    assert "peco_filter" in caps.supported_sensors
    assert "pre_filter" in caps.supported_sensors
    assert caps.has_sensor_data is False


def test_air_pro_unchanged():
    caps = get_capabilities(resolve_model_name("Molekule Air Pro"))
    assert caps.max_fan_speed == 6
    assert caps.has_sensor_data is True
    assert "co2" in caps.supported_sensors


def test_infer_unknown_with_smart_mode():
    caps = infer_capabilities({"mode": "smart", "fanspeed": "4", "aqi": "good"})
    assert PRESET_AUTO_PROTECT in caps.preset_modes or PRESET_AUTO in caps.preset_modes
