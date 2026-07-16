from fan_helpers import (
    api_auto_requested,
    original_preset_from_device,
    original_preset_to_action,
    preset_from_device_mode,
)


def test_smart_mode_maps_to_auto_protect():
    assert preset_from_device_mode("smart", ("auto_protect", "manual")) == "auto_protect"


def test_manual_mode_maps_to_manual():
    assert preset_from_device_mode("manual", ("auto_protect", "manual")) == "manual"


def test_auto_protect_requests_auto():
    assert api_auto_requested("auto_protect") is True
    assert api_auto_requested("manual") is False


def test_original_off_has_no_preset():
    assert original_preset_from_device({"mode": "off"}) is None


def test_original_smart_mode_maps_to_auto():
    assert original_preset_from_device({"mode": "smart"}) == "auto"


def test_original_burst_flag_maps_to_boost():
    assert (
        original_preset_from_device(
            {"mode": "on", "burst": "true", "fanspeed": "3"}
        )
        == "boost"
    )


def test_original_silent_flag_maps_to_silent():
    assert original_preset_from_device({"mode": "on", "silent": "true"}) == "silent"


def test_original_low_speed_maps_to_silent():
    assert original_preset_from_device({"mode": "on", "fanspeed": "1"}) == "silent"


def test_original_high_speed_maps_to_boost():
    assert original_preset_from_device({"mode": "on", "fanspeed": "3"}) == "boost"


def test_original_on_at_mid_speed_maps_to_auto():
    assert original_preset_from_device({"mode": "on", "fanspeed": "2"}) == "auto"


def test_original_silent_action():
    assert original_preset_to_action("silent") == (
        "set-fan-speed",
        {"fanSpeed": 1},
    )


def test_original_auto_action():
    assert original_preset_to_action("auto") == (
        "enable-smart-mode",
        {"silent": "0"},
    )


def test_original_boost_action():
    assert original_preset_to_action("boost") == (
        "set-fan-speed",
        {"fanSpeed": 3},
    )
