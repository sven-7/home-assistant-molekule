from fan_helpers import (
    api_auto_requested,
    original_preset_from_device,
    original_preset_to_action,
    preset_from_device_mode,
)


def test_smart_mode_maps_to_auto():
    assert preset_from_device_mode("smart", ("auto", "manual")) == "auto"


def test_manual_mode_maps_to_manual():
    assert preset_from_device_mode("manual", ("auto", "manual")) == "manual"


def test_auto_requests_auto_protect_api():
    assert api_auto_requested("auto") is True
    assert api_auto_requested("auto_protect") is True
    assert api_auto_requested("manual") is False


def test_original_off_has_no_preset():
    assert original_preset_from_device({"mode": "off"}) is None


def test_original_speed_1_is_silent():
    assert original_preset_from_device({"mode": "on", "fanspeed": "1"}) == "silent"


def test_original_speed_2_is_auto():
    assert original_preset_from_device({"mode": "on", "fanspeed": "2"}) == "auto"


def test_original_speed_3_is_boost():
    assert original_preset_from_device({"mode": "on", "fanspeed": "3"}) == "boost"


def test_original_silent_action_is_speed_1():
    assert original_preset_to_action("silent") == (
        "set-fan-speed",
        {"fanSpeed": 1},
    )


def test_original_auto_action_is_speed_2():
    # Original has no cloud smart mode — Auto is the middle speed label.
    assert original_preset_to_action("auto") == (
        "set-fan-speed",
        {"fanSpeed": 2},
    )


def test_original_boost_action_is_speed_3():
    assert original_preset_to_action("boost") == (
        "set-fan-speed",
        {"fanSpeed": 3},
    )
