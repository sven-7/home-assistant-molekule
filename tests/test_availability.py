from availability import device_available


def test_online_device_is_available():
    assert device_available({"serialNumber": "A", "online": "true"}) is True


def test_cloud_reporting_offline_makes_device_unavailable():
    assert device_available({"serialNumber": "A", "online": "false"}) is False


def test_boolean_false_is_offline():
    assert device_available({"serialNumber": "A", "online": False}) is False


def test_missing_online_field_counts_as_available():
    # A model that never sends the field must not be stuck unavailable.
    assert device_available({"serialNumber": "A"}) is True


def test_device_missing_from_account_is_unavailable():
    assert device_available(None) is False
