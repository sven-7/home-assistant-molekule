"""Entity availability from the Molekule cloud's per-device ``online`` flag.

Without this, an unplugged purifier keeps its last state forever: the account
still lists it, so every entity stays available.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional


def device_available(device: Optional[Mapping[str, Any]]) -> bool:
    """True unless the device is gone from the account or the cloud says offline.

    Only an explicit offline value counts, so a model that never sends the
    field stays available.
    """
    if device is None:
        return False
    online = device.get("online")
    if online is None:
        return True
    return str(online).strip().lower() not in ("false", "0")
