#!/usr/bin/env python3
"""Dump Molekule device payloads for capability discovery.

Uses pycognito (works on Python 3.14). Does not import the HA integration.

Usage:
  cd /path/to/worktree
  source .venv/bin/activate
  MOLEKULE_EMAIL=you@example.com MOLEKULE_PASSWORD='...' \\
    python scripts/dump_molekule_devices.py

Writes tests/fixtures/devices_redacted.json with serials/macs/tokens stripped.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import aiohttp
from pycognito import Cognito

ROOT = Path(__file__).resolve().parents[1]

API_CLIENT_ID = "1ec4fa3oriciupg94ugoi84kkk"
API_POOL_ID = "us-west-2_KqrEZKC6r"
API_URL = "https://api.molekule.com/users/me/devices/"

REDACT_KEYS = {
    "serialNumber",
    "macAddress",
    "id",
    "ownerId",
    "email",
    "firstConnectedUser",
    "mainFilterSerialNumber",
}


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


def login(email: str, password: str) -> Cognito:
    cog = Cognito(API_POOL_ID, API_CLIENT_ID, username=email)
    cog.authenticate(password=password)
    return cog


def process_sensor_data(data: dict) -> dict | None:
    if not data or "sensorData" not in data:
        return None
    processed = {
        "PM2_5": None,
        "PM10": None,
        "RH": None,
        "TVOC": None,
        "CO2": None,
    }
    for pollutant in data["sensorData"]:
        pollutant_type = pollutant.get("type")
        if pollutant_type not in processed:
            continue
        values = pollutant.get("sensorDataValue", [])
        valid = [v["v"] for v in values if v.get("v") != -1]
        if valid:
            processed[pollutant_type] = valid[-1]
    return processed


async def api_get(session: aiohttp.ClientSession, token: str, url: str) -> dict | None:
    headers = {
        "Authorization": token,
        "x-api-version": "1.0",
        "Content-Type": "application/json",
        "User-Agent": "MolekuleDump/1.0",
    }
    async with session.get(url, headers=headers) as response:
        if response.status != 200:
            text = await response.text()
            raise RuntimeError(f"GET {url} -> {response.status}: {text[:200]}")
        return await response.json()


async def main() -> int:
    email = os.environ.get("MOLEKULE_EMAIL")
    password = os.environ.get("MOLEKULE_PASSWORD")
    if not email or not password:
        print("Set MOLEKULE_EMAIL and MOLEKULE_PASSWORD", file=sys.stderr)
        return 1

    print("Authenticating...")
    cognito = await asyncio.to_thread(login, email, password)
    token = cognito.id_token

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        devices = await api_get(session, token, API_URL)
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
                end_time = int(time.time() * 1000)
                start_time = end_time - 3600000
                sensor_url = (
                    f"{API_URL}{serial}/sensordata"
                    f"?aggregation=false&fromDate={start_time}"
                    f"&resolution=5&toDate={end_time}"
                )
                try:
                    raw = await api_get(session, token, sensor_url)
                    entry["sensordata"] = process_sensor_data(raw) if raw else None
                    if raw and entry["sensordata"] is None:
                        entry["sensordata_raw_keys"] = list(raw.keys())
                except Exception as err:  # noqa: BLE001
                    msg = str(err)
                    if serial and serial in msg:
                        msg = msg.replace(serial, "<redacted>")
                    entry["sensordata_error"] = msg
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


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
