from fan_helpers import api_auto_requested, preset_from_device_mode


def test_smart_mode_maps_to_auto_protect():
    assert preset_from_device_mode("smart", ("auto_protect", "manual")) == "auto_protect"


def test_manual_mode_maps_to_manual():
    assert preset_from_device_mode("manual", ("auto_protect", "manual")) == "manual"


def test_auto_protect_requests_auto():
    assert api_auto_requested("auto_protect") is True
    assert api_auto_requested("manual") is False
