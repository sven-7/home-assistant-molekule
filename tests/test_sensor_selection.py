from capabilities import get_capabilities
from sensor_helpers import sensor_keys_for_capabilities


def test_mini_only_exposes_aqi_peco_and_pm25():
    caps = get_capabilities("mini_plus")

    keys = sensor_keys_for_capabilities(
        caps, available_fields={"aqi", "pecoFilter", "PM2_5"}
    )

    assert keys == ["air_quality", "peco_filter", "pm25"]
    assert "humidity" not in keys
    assert "co2" not in keys


def test_air_pro_includes_particle_sensors_with_empty_sensor_data():
    caps = get_capabilities("air_pro")

    keys = sensor_keys_for_capabilities(caps, available_fields={"aqi", "pecoFilter"})

    assert keys == [
        "air_quality",
        "peco_filter",
        "humidity",
        "pm25",
        "pm10",
        "voc",
        "co2",
    ]


def test_original_includes_pre_filter_and_skips_sensor_data():
    caps = get_capabilities("original")

    keys = sensor_keys_for_capabilities(
        caps, available_fields={"pecoFilter", "preFilter", "aqi"}
    )

    assert keys == ["air_quality", "peco_filter", "pre_filter"]
