from capabilities import get_capabilities
from sensor_helpers import sensor_keys_for_capabilities


def test_mini_sensor_keys_include_aqi_peco_and_available_pm25():
    caps = get_capabilities("mini_plus")

    keys = sensor_keys_for_capabilities(
        caps, available_fields={"aqi", "pecoFilter", "PM2_5"}
    )

    assert keys == ["air_quality", "peco_filter", "pm25"]


def test_mini_skips_unavailable_particle_sensors():
    caps = get_capabilities("mini_plus")

    keys = sensor_keys_for_capabilities(caps, available_fields={"aqi", "pecoFilter"})

    assert keys == ["air_quality", "peco_filter"]


def test_original_includes_pre_filter_and_skips_sensor_data():
    caps = get_capabilities("original")

    keys = sensor_keys_for_capabilities(
        caps, available_fields={"pecoFilter", "preFilter", "aqi"}
    )

    assert keys == ["air_quality", "peco_filter", "pre_filter"]
