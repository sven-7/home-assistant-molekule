#!/usr/bin/env python3
"""Dump Molekule device payloads for capability discovery.

Usage:
  MOLEKULE_EMAIL=you@example.com MOLEKULE_PASSWORD='...' \\
    python3 scripts/dump_molekule_devices.py

Writes tests/fixtures/devices_redacted.json with serials/macs/tokens stripped.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Allow importing the integration package without Home Assistant installed.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "molekule"))

from api import MolekuleApi  # noqa: E402


REDACT_KEYS = {"serialNumber", "macAddress", "id", "ownerId", "email"}


def redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in REDACT_KEYS:
                out[k] = "<redacted>"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


async def main() -> int:
    email = os.environ.get("MOLEKULE_EMAIL")
    password = os.environ.get("MOLEKULE_PASSWORD")
    if not email or not password:
        print("Set MOLEKULE_EMAIL and MOLEKULE_PASSWORD", file=sys.stderr)
        return 1

    api = MolekuleApi(email, password)
    try:
        await api.authenticate()
        devices = await api.get_devices()
        content = (devices or {}).get("content", [])
        dump = {"devices": []}
        for device in content:
            serial = device.get("serialNumber")
            entry = {
                "model": (device.get("subProduct") or {}).get("name"),
                "name": device.get("name"),
                "mode": device.get("mode"),
                "fanspeed": device.get("fanspeed"),
                "aqi": device.get("aqi"),
                "keys": sorted(device.keys()),
                "device": redact(device),
                "sensordata": None,
            }
            if serial:
                try:
                    entry["sensordata"] = await api.get_sensor_data(serial)
                except Exception as err:  # noqa: BLE001
                    entry["sensordata_error"] = str(err)
            dump["devices"].append(entry)
            print(
                f"- {entry['name']}: model={entry['model']!r} "
                f"mode={entry['mode']!r} fanspeed={entry['fanspeed']!r} "
                f"keys={entry['keys']}"
            )

        out = ROOT / "tests" / "fixtures" / "devices_redacted.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(dump, indent=2) + "\n")
        print(f"Wrote {out}")
        return 0
    finally:
        await api.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
