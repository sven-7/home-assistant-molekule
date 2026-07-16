# Mini Plus / Original Molekule Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the forked HACS Molekule integration so Mini Plus, Mini Plus 2, and original Molekule get correct Auto/preset modes and the richest sensors their cloud API actually returns.

**Architecture:** Introduce a shared `capabilities.py` module as the single source of truth for model → fan presets, speed range, and sensors. Fan and sensor platforms stop maintaining duplicate `MODEL_CAPABILITIES` tables. A one-time discovery dump locks exact API `subProduct.name` strings, mode values, and filter field names before hardcoding aliases.

**Tech Stack:** Home Assistant custom component (Python 3.12+), `aiohttp`, `warrant` Cognito auth (existing), `pytest` for pure unit tests, Molekule cloud API (`https://api.molekule.com/users/me/devices/`).

**Spec:** `docs/superpowers/specs/2026-07-16-molekule-mini-original-support-design.md`

## Global Constraints

- Keep HA domain `molekule` (existing config entries must survive HACS repo swap).
- Cloud polling only — no LAN control.
- Create sensors only for fields the API actually returns (capabilities ∩ payload).
- Do not invent particle sensors for original Molekule.
- Mini Plus / Mini Plus 2: speeds 1–5 + Auto Protect; PECO only (no pre-filter).
- Original: presets Silent / Auto / Boost; PECO + Pre-filter; expose any other useful device fields.
- Air Pro behavior must remain unchanged.
- Prefer small focused files; extract shared capability logic rather than growing duplicate tables in `fan.py` / `sensor.py`.

## File Structure

| File | Responsibility |
|------|----------------|
| `custom_components/molekule/capabilities.py` | Model resolution, capability dataclasses, alias map, inference for unknown models |
| `custom_components/molekule/const.py` | Shared constants / capability key names / preset string constants |
| `custom_components/molekule/api.py` | HTTP client; add original-mode actions if discovery requires them |
| `custom_components/molekule/__init__.py` | Coordinator: use capabilities for `sensordata` fetch gating |
| `custom_components/molekule/fan.py` | Fan entity driven by capabilities (Mini speed+preset vs original presets-only) |
| `custom_components/molekule/sensor.py` | Sensor creation from capabilities; add pre-filter sensor |
| `scripts/dump_molekule_devices.py` | One-shot discovery script (email/password → redacted JSON fixtures) |
| `tests/fixtures/*.json` | Captured (redacted) device payloads for tests |
| `tests/test_capabilities.py` | Unit tests for model resolution and capability selection |
| `tests/test_fan_presets.py` | Unit tests for preset↔API mode mapping helpers |
| `README.md` | Document supported models after changes |
| `custom_components/molekule/manifest.json` | Bump version |

---

### Task 1: Capture live API payloads (discovery)

**Files:**
- Create: `scripts/dump_molekule_devices.py`
- Create: `tests/fixtures/.gitkeep`
- Create (after run): `tests/fixtures/devices_redacted.json` (committed only after secrets stripped)

**Interfaces:**
- Consumes: Molekule email/password via env `MOLEKULE_EMAIL` / `MOLEKULE_PASSWORD`
- Produces: JSON dump of each device’s `subProduct`, `mode`, `fanspeed`, filter keys, and optional `sensordata` keys — used to fill alias maps in Task 2

- [ ] **Step 1: Add discovery script**

```python
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
```

- [ ] **Step 2: Ensure fixtures directory exists**

```bash
mkdir -p tests/fixtures
touch tests/fixtures/.gitkeep
```

- [ ] **Step 3: Run discovery (user credentials required)**

Run:

```bash
cd /Users/stephen/src/home-assistant-molekule
python3 -m pip install warrant aiohttp --quiet
MOLEKULE_EMAIL='...' MOLEKULE_PASSWORD='...' python3 scripts/dump_molekule_devices.py
```

Expected: console lines for Mini Plus, Mini Plus 2, and original with `model=...`, `mode=...`, and a written `tests/fixtures/devices_redacted.json`.

If credentials cannot be used in this environment, pause and ask the user to either run the script and paste the **redacted** JSON, or export device attributes from HA Developer Tools. Do not invent model strings.

- [ ] **Step 4: Record discovery findings in a short note at top of fixtures file comment is not valid JSON — instead add `tests/fixtures/DISCOVERY.md`**

```markdown
# Discovery notes

Fill after running dump_molekule_devices.py:

| Friendly | API subProduct.name | Observed mode values | Filter keys | sensordata keys |
|----------|---------------------|----------------------|-------------|-----------------|
| Mini Plus | | | | |
| Mini Plus 2 | | | | |
| Original | | | | |

Provisional original preset mapping (confirm/replace from dump):
- silent → record observed `mode` / action path from dump
- auto → likely `smart` / `enable-smart-mode` (confirm)
- boost → likely `burst` field or max fanspeed action (confirm)
```

- [ ] **Step 5: Commit**

```bash
git add scripts/dump_molekule_devices.py tests/fixtures/.gitkeep tests/fixtures/DISCOVERY.md tests/fixtures/devices_redacted.json
git commit -m "Add Molekule API discovery script and fixtures"
```

Only commit `devices_redacted.json` if it contains no real serials, emails, or tokens.

---

### Task 2: Shared capabilities module (TDD)

**Files:**
- Create: `custom_components/molekule/capabilities.py`
- Modify: `custom_components/molekule/const.py`
- Create: `tests/test_capabilities.py`
- Create: `tests/conftest.py` (path setup)
- Update: `tests/fixtures/DISCOVERY.md` aliases into code after Task 1

**Interfaces:**
- Consumes: discovery model strings from Task 1
- Produces:
  - `@dataclass DeviceCapabilities` with fields: `max_fan_speed: int | None`, `preset_modes: list[str]`, `fan_control: Literal["speed","presets"]`, `has_sensor_data: bool`, `supported_sensors: frozenset[str]`, `auto_api_mode: str`
  - `resolve_model_name(raw: str) -> str`
  - `get_capabilities(model_name: str) -> DeviceCapabilities`
  - `infer_capabilities(device: dict) -> DeviceCapabilities` (unknown models)

- [ ] **Step 1: Add pytest path bootstrap**

```python
# tests/conftest.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "molekule"))
```

- [ ] **Step 2: Write failing tests**

Use **exact** model strings from Task 1 discovery. Below uses provisional names — replace with discovered values before committing.

```python
# tests/test_capabilities.py
from capabilities import get_capabilities, resolve_model_name, infer_capabilities
from const import (
    PRESET_AUTO_PROTECT,
    PRESET_MANUAL,
    PRESET_SILENT,
    PRESET_AUTO,
    PRESET_BOOST,
)


def test_resolve_mini_plus_aliases():
    # Replace aliases with discovered subProduct.name values
    assert resolve_model_name("Molekule Air Mini+") == "mini_plus"
    assert resolve_model_name("Molekule Air Mini+ 2") == "mini_plus"


def test_mini_plus_capabilities():
    caps = get_capabilities("mini_plus")
    assert caps.fan_control == "speed"
    assert caps.max_fan_speed == 5
    assert PRESET_AUTO_PROTECT in caps.preset_modes
    assert PRESET_MANUAL in caps.preset_modes
    assert "peco_filter" in caps.supported_sensors
    assert "pre_filter" not in caps.supported_sensors
    assert caps.has_sensor_data is True  # flip False if discovery shows no sensordata


def test_original_capabilities():
    caps = get_capabilities("original")
    assert caps.fan_control == "presets"
    assert caps.max_fan_speed is None
    assert caps.preset_modes == [PRESET_SILENT, PRESET_AUTO, PRESET_BOOST]
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
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
cd /Users/stephen/src/home-assistant-molekule
python3 -m pip install pytest --quiet
python3 -m pytest tests/test_capabilities.py -v
```

Expected: FAIL with `ModuleNotFoundError: capabilities` or import errors from `const`.

- [ ] **Step 4: Extend const.py with preset constants (dedupe capability keys)**

Replace duplicate `CAPABILITY_*` definitions and add:

```python
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
)

DOMAIN = "molekule"
MANUFACTURER = "Molekule"

API_CLIENT_ID = "1ec4fa3oriciupg94ugoi84kkk"
API_POOL_ID = "us-west-2_KqrEZKC6r"
API_URL = "https://api.molekule.com/users/me/devices/"
API_REGION = "us-west-2"

CAPABILITY_AUTO = "AutoFunctionality"
CAPABILITY_AQI = "AirQualityMonitor"
CAPABILITY_MAX_FAN_SPEED = "MaxFanSpeed"

KEY_AIR_QUALITY = "air_quality"
KEY_HUMIDITY = "humidity"
KEY_FAN = "fan"
KEY_MODE = "mode"

CONF_REFRESH_RATE = "conf_refresh_rate"
CONF_REFRESH_RATE_DEFAULT = 300
CONF_SILENT_AUTO = "conf_silent_auto"

# HA preset mode identifiers
PRESET_AUTO_PROTECT = "auto_protect"
PRESET_MANUAL = "manual"
PRESET_SILENT = "silent"
PRESET_AUTO = "auto"
PRESET_BOOST = "boost"

# API mode strings commonly returned by devices endpoint
API_MODE_SMART = "smart"
API_MODE_MANUAL = "manual"
API_MODE_OFF = "off"
```

- [ ] **Step 5: Implement capabilities.py**

```python
"""Model capability resolution for Molekule devices."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .const import (
    API_MODE_SMART,
    PRESET_AUTO,
    PRESET_AUTO_PROTECT,
    PRESET_BOOST,
    PRESET_MANUAL,
    PRESET_SILENT,
)

FanControl = Literal["speed", "presets"]


@dataclass(frozen=True)
class DeviceCapabilities:
    family: str
    fan_control: FanControl
    max_fan_speed: int | None
    preset_modes: tuple[str, ...]
    has_sensor_data: bool
    supported_sensors: frozenset[str]
    auto_api_mode: str = API_MODE_SMART


# Canonical families
FAMILY_MINI_PLUS = "mini_plus"
FAMILY_ORIGINAL = "original"
FAMILY_AIR_PRO = "air_pro"
FAMILY_UNKNOWN = "unknown"

# Map exact API subProduct.name values → family.
# UPDATE THESE from tests/fixtures/DISCOVERY.md after Task 1.
MODEL_ALIASES: dict[str, str] = {
    "Molekule Air Mini+": FAMILY_MINI_PLUS,
    "Molekule Air Mini+ 2": FAMILY_MINI_PLUS,
    "Molekule Air Mini Plus": FAMILY_MINI_PLUS,
    "Molekule Air Mini Plus 2": FAMILY_MINI_PLUS,
    "Molekule Air": FAMILY_ORIGINAL,
    "Molekule Air Pro": FAMILY_AIR_PRO,
}

_CAPABILITIES: dict[str, DeviceCapabilities] = {
    FAMILY_MINI_PLUS: DeviceCapabilities(
        family=FAMILY_MINI_PLUS,
        fan_control="speed",
        max_fan_speed=5,
        preset_modes=(PRESET_AUTO_PROTECT, PRESET_MANUAL),
        has_sensor_data=True,
        supported_sensors=frozenset(
            {"air_quality", "peco_filter", "humidity", "pm25", "pm10", "voc", "co2"}
        ),
    ),
    FAMILY_ORIGINAL: DeviceCapabilities(
        family=FAMILY_ORIGINAL,
        fan_control="presets",
        max_fan_speed=None,
        preset_modes=(PRESET_SILENT, PRESET_AUTO, PRESET_BOOST),
        has_sensor_data=False,
        supported_sensors=frozenset({"air_quality", "peco_filter", "pre_filter"}),
    ),
    FAMILY_AIR_PRO: DeviceCapabilities(
        family=FAMILY_AIR_PRO,
        fan_control="speed",
        max_fan_speed=6,
        preset_modes=(PRESET_AUTO_PROTECT, PRESET_MANUAL),
        has_sensor_data=True,
        supported_sensors=frozenset(
            {"air_quality", "peco_filter", "humidity", "pm25", "pm10", "voc", "co2"}
        ),
    ),
}

_DEFAULT = DeviceCapabilities(
    family=FAMILY_UNKNOWN,
    fan_control="speed",
    max_fan_speed=3,
    preset_modes=(PRESET_MANUAL,),
    has_sensor_data=False,
    supported_sensors=frozenset({"air_quality", "peco_filter"}),
)


def resolve_model_name(raw: str | None) -> str:
    if not raw:
        return FAMILY_UNKNOWN
    if raw in MODEL_ALIASES:
        return MODEL_ALIASES[raw]
    lowered = raw.lower()
    if "mini" in lowered:
        return FAMILY_MINI_PLUS
    if "pro" in lowered:
        return FAMILY_AIR_PRO
    if raw == "Molekule Air" or lowered.strip() == "molekule air":
        return FAMILY_ORIGINAL
    return FAMILY_UNKNOWN


def get_capabilities(model_or_family: str) -> DeviceCapabilities:
    family = model_or_family
    if family not in _CAPABILITIES:
        family = resolve_model_name(model_or_family)
    return _CAPABILITIES.get(family, _DEFAULT)


def infer_capabilities(device: dict[str, Any]) -> DeviceCapabilities:
    """Best-effort caps for unknown models from a live payload."""
    raw = (device.get("subProduct") or {}).get("name")
    family = resolve_model_name(raw)
    if family != FAMILY_UNKNOWN:
        return get_capabilities(family)

    sensors = {"peco_filter"}
    if device.get("aqi") is not None:
        sensors.add("air_quality")
    if "preFilter" in device or "prefilter" in {k.lower() for k in device}:
        sensors.add("pre_filter")

    mode = str(device.get("mode", "")).lower()
    presets: list[str] = [PRESET_MANUAL]
    if mode == API_MODE_SMART or "smart" in device:
        presets = [PRESET_AUTO_PROTECT, PRESET_MANUAL]

    try:
        speed = int(device.get("fanspeed") or 1)
    except (TypeError, ValueError):
        speed = 1

    return DeviceCapabilities(
        family=FAMILY_UNKNOWN,
        fan_control="speed",
        max_fan_speed=max(speed, 3),
        preset_modes=tuple(presets),
        has_sensor_data=False,
        supported_sensors=frozenset(sensors),
    )


def capabilities_for_device(device: dict[str, Any]) -> DeviceCapabilities:
    raw = (device.get("subProduct") or {}).get("name")
    family = resolve_model_name(raw)
    if family == FAMILY_UNKNOWN:
        return infer_capabilities(device)
    return get_capabilities(family)
```

After Task 1, edit `MODEL_ALIASES` and `has_sensor_data` for Mini to match discovery. If Mini `sensordata` fails, set `has_sensor_data=False` and drop particle sensors from `supported_sensors`, keeping `air_quality` + `peco_filter`.

- [ ] **Step 6: Run tests — expect PASS**

```bash
python3 -m pytest tests/test_capabilities.py -v
```

Expected: all PASS (update alias strings if discovery differed).

- [ ] **Step 7: Commit**

```bash
git add custom_components/molekule/capabilities.py custom_components/molekule/const.py tests/
git commit -m "Add shared Molekule model capabilities"
```

---

### Task 3: Wire coordinator to capabilities

**Files:**
- Modify: `custom_components/molekule/__init__.py`
- Modify: `custom_components/molekule/api.py` (only if missing `import` / logging issues)

**Interfaces:**
- Consumes: `capabilities_for_device(device) -> DeviceCapabilities`
- Produces: coordinator data where `sensordata` is fetched iff `caps.has_sensor_data`; logs unknown models once

- [ ] **Step 1: Fix missing asyncio import and gate sensordata**

In `__init__.py`, ensure `import asyncio` exists (file references `asyncio.CancelledError`).

Replace the hard-coded model check:

```python
# OLD
if device_model not in ["Molekule Air", "Unknown Model"]:
    sensor_data = await api.get_sensor_data(serial)

# NEW
from .capabilities import capabilities_for_device

caps = capabilities_for_device(device)
if caps.family == "unknown":
    _LOGGER.warning(
        "Unknown Molekule model %r for %s; keys=%s",
        device_model,
        serial,
        sorted(device.keys()),
    )
sensor_data = None
if caps.has_sensor_data:
    try:
        sensor_data = await api.get_sensor_data(serial)
    except Exception as err:
        _LOGGER.warning("Failed to get sensor data for %s: %s", serial, err)
```

Also stop inventing empty particle dicts when `has_sensor_data` is False — store `processed_data[serial] = {"device_info": ...}` only, or keep empty particle keys solely for Pro/Mini that request them:

```python
processed_data[serial] = sensor_data or {}
# device_info attached afterward as today
```

- [ ] **Step 2: Smoke-check import**

```bash
python3 -c "from custom_components.molekule.capabilities import capabilities_for_device; print(capabilities_for_device({'subProduct':{'name':'Molekule Air Pro'}}))"
```

Expected: prints a `DeviceCapabilities(... family='air_pro' ...)`.

- [ ] **Step 3: Commit**

```bash
git add custom_components/molekule/__init__.py
git commit -m "Gate sensordata fetch using model capabilities"
```

---

### Task 4: Fan support for Mini Plus / Mini Plus 2 + Pro rename

**Files:**
- Modify: `custom_components/molekule/fan.py`
- Create: `tests/test_fan_presets.py`
- Modify: `custom_components/molekule/api.py` if `set_auto_mode` needs a disable path that posts `manual` instead of forcing speed 1

**Interfaces:**
- Consumes: `capabilities_for_device`, `PRESET_AUTO_PROTECT`, `PRESET_MANUAL`
- Produces: fan entities with speed 1–5 and presets `auto_protect` / `manual` for Mini; Pro uses same preset ids (rename from `auto`)

- [ ] **Step 1: Write failing preset helper tests**

```python
# tests/test_fan_presets.py
from fan_helpers import preset_from_device_mode, api_auto_requested


def test_smart_mode_maps_to_auto_protect():
    assert preset_from_device_mode("smart", ("auto_protect", "manual")) == "auto_protect"


def test_manual_mode_maps_to_manual():
    assert preset_from_device_mode("manual", ("auto_protect", "manual")) == "manual"


def test_auto_protect_requests_auto():
    assert api_auto_requested("auto_protect") is True
    assert api_auto_requested("manual") is False
```

- [ ] **Step 2: Run — expect FAIL**

```bash
python3 -m pytest tests/test_fan_presets.py -v
```

Expected: FAIL `ModuleNotFoundError: fan_helpers`

- [ ] **Step 3: Add `custom_components/molekule/fan_helpers.py`**

```python
"""Pure helpers for fan preset mapping (unit-tested without Home Assistant)."""
from __future__ import annotations

from .const import API_MODE_SMART, PRESET_AUTO_PROTECT, PRESET_MANUAL


def preset_from_device_mode(mode: str | None, preset_modes: tuple[str, ...]) -> str | None:
    if not preset_modes:
        return None
    if mode == API_MODE_SMART and PRESET_AUTO_PROTECT in preset_modes:
        return PRESET_AUTO_PROTECT
    if PRESET_MANUAL in preset_modes:
        return PRESET_MANUAL
    return None


def api_auto_requested(preset_mode: str) -> bool:
    return preset_mode == PRESET_AUTO_PROTECT
```

- [ ] **Step 4: Run helper tests — expect PASS**

```bash
python3 -m pytest tests/test_fan_presets.py -v
```

- [ ] **Step 5: Rewrite `fan.py` to use capabilities**

Key behaviors:

```python
from .capabilities import capabilities_for_device
from .fan_helpers import api_auto_requested, preset_from_device_mode
from .const import CONF_SILENT_AUTO, PRESET_AUTO_PROTECT

class MolekuleFan(CoordinatorEntity, FanEntity):
    def __init__(...):
        caps = capabilities_for_device(self._device or {})
        self._caps = caps
        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if caps.fan_control == "speed" and caps.max_fan_speed:
            features |= FanEntityFeature.SET_SPEED
        if caps.preset_modes:
            features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = list(caps.preset_modes)
        self._attr_supported_features = features

    @property
    def _speed_range(self):
        max_speed = self._caps.max_fan_speed or 3
        return (1, max_speed)

    @property
    def percentage(self):
        if self._caps.fan_control != "speed":
            return None  # presets-only models
        ...

    @property
    def preset_mode(self):
        return preset_from_device_mode(
            self._device.get("mode") if self._device else None,
            self._caps.preset_modes,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in self._caps.preset_modes:
            raise ValueError(f"Unsupported preset: {preset_mode}")
        silent_auto = self.coordinator.config_entry.options.get(CONF_SILENT_AUTO, False)
        if preset_mode in (PRESET_AUTO_PROTECT,) or api_auto_requested(preset_mode):
            ok = await self._api.set_auto_mode(self._device_id, True, silent_auto)
        else:
            ok = await self._api.set_auto_mode(self._device_id, False, silent_auto)
        if not ok:
            raise HomeAssistantError("Failed to set Molekule preset mode")
        await self.coordinator.async_request_refresh()
```

Leave original (`fan_control == "presets"`) path for Task 5 — for now if `fan_control == "presets"`, still create the entity but only implement Mini/Pro preset ids; original presets wired next task.

Improve `api.set_auto_mode(..., auto=False)` to request manual mode explicitly if discovery shows a `manual` action works better than `set_fan_speed(..., 1)`:

```python
async def set_auto_mode(self, serial: str, auto: bool, silent: bool = False) -> bool:
    if auto:
        url = f"{API_URL}{serial}/actions/enable-smart-mode"
        await self._make_request("POST", url, json={"silent": str(int(silent))})
        return True
    # Prefer explicit manual action when available
    url = f"{API_URL}{serial}/actions/manual"
    result = await self._make_request("POST", url)
    if result is None:
        # fallback: keep previous behavior
        return await self.set_fan_speed(serial, 1)
    return True
```

Verify against live devices in Task 8; if `manual` 404s, keep fan-speed fallback only.

- [ ] **Step 6: Commit**

```bash
git add custom_components/molekule/fan.py custom_components/molekule/fan_helpers.py custom_components/molekule/api.py tests/test_fan_presets.py
git commit -m "Enable Auto Protect and 1-5 speeds for Mini Plus fans"
```

---

### Task 5: Original Molekule Silent / Auto / Boost presets

**Files:**
- Modify: `custom_components/molekule/fan.py`
- Modify: `custom_components/molekule/fan_helpers.py`
- Modify: `custom_components/molekule/api.py`
- Modify: `tests/test_fan_presets.py`

**Interfaces:**
- Consumes: discovery mode/action names from Task 1 (`DISCOVERY.md`)
- Produces: `set_original_preset(serial, preset)`; mapping helpers for silent/auto/boost

- [ ] **Step 1: Extend failing tests with discovery-backed mappings**

Replace placeholders with real API values from discovery. Example provisional mapping:

```python
from fan_helpers import original_preset_from_device, original_preset_to_action


def test_original_boost_from_burst_flag():
    assert original_preset_from_device({"mode": "manual", "burst": "true", "fanspeed": "3"}) == "boost"


def test_original_silent():
    # Adjust to discovered shape — e.g. mode=="silent" or fanspeed==1 + silent flag
    assert original_preset_from_device({"mode": "silent"}) == "silent"


def test_original_auto_smart():
    assert original_preset_from_device({"mode": "smart"}) == "auto"


def test_original_actions():
    assert original_preset_to_action("silent") == ("set-fan-speed", {"fanSpeed": 1})  # or discovered
    assert original_preset_to_action("auto") == ("enable-smart-mode", {"silent": "0"})
    assert original_preset_to_action("boost") == ("set-fan-speed", {"fanSpeed": 3})  # or burst action
```

- [ ] **Step 2: Implement helpers + `api.set_mode_action`**

```python
async def set_mode_action(self, serial: str, action: str, body: dict | None = None) -> bool:
    url = f"{API_URL}{serial}/actions/{action}"
    try:
        await self._make_request("POST", url, json=body or {})
        return True
    except Exception as err:
        _LOGGER.error("Failed action %s: %s", action, err)
        return False
```

Update `async_set_preset_mode` in `fan.py`:

```python
if self._caps.fan_control == "presets":
    action, body = original_preset_to_action(preset_mode)
    ok = await self._api.set_mode_action(self._device_id, action, body)
else:
    ...
```

For presets-only fans: do **not** advertise `SET_SPEED` (already gated in Task 4).

- [ ] **Step 3: Run unit tests**

```bash
python3 -m pytest tests/test_fan_presets.py tests/test_capabilities.py -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add custom_components/molekule/fan.py custom_components/molekule/fan_helpers.py custom_components/molekule/api.py tests/test_fan_presets.py
git commit -m "Add Silent/Auto/Boost presets for original Molekule"
```

---

### Task 6: Sensors — Mini sensordata + original pre-filter

**Files:**
- Modify: `custom_components/molekule/sensor.py`
- Create: `tests/test_sensor_selection.py` (pure selection helper)

**Interfaces:**
- Consumes: `capabilities_for_device`
- Produces: entity list builder `sensors_for_device(device, caps, coordinator, api)`; `MolekulePreFilterSensor`

- [ ] **Step 1: Failing test for sensor selection**

```python
# tests/test_sensor_selection.py
from capabilities import get_capabilities
from sensor_helpers import sensor_keys_for_capabilities


def test_mini_sensor_keys_include_aqi_peco():
    caps = get_capabilities("mini_plus")
    keys = sensor_keys_for_capabilities(caps, available_fields={"aqi", "pecoFilter", "PM2_5"})
    assert "air_quality" in keys
    assert "peco_filter" in keys
    # PM only if has_sensor_data and field present
    if caps.has_sensor_data:
        assert "pm25" in keys


def test_original_includes_pre_filter():
    caps = get_capabilities("original")
    keys = sensor_keys_for_capabilities(caps, available_fields={"pecoFilter", "preFilter", "aqi"})
    assert "pre_filter" in keys
    assert "peco_filter" in keys
    assert "pm25" not in keys
```

- [ ] **Step 2: Implement `sensor_helpers.py` + pre-filter sensor; rewrite setup to use capabilities**

```python
def sensor_keys_for_capabilities(caps, available_fields: set[str]) -> list[str]:
    keys = []
    mapping = {
        "air_quality": {"aqi"},
        "peco_filter": {"pecoFilter"},
        "pre_filter": {"preFilter", "prefilter", "pre_filter"},
        "humidity": {"RH"},
        "pm25": {"PM2_5"},
        "pm10": {"PM10"},
        "voc": {"TVOC"},
        "co2": {"CO2"},
    }
    for sensor_key in caps.supported_sensors:
        needed = mapping[sensor_key]
        if sensor_key in {"humidity", "pm25", "pm10", "voc", "co2"} and not caps.has_sensor_data:
            continue
        if available_fields & needed or sensor_key in {"air_quality", "peco_filter", "pre_filter"}:
            # For particle sensors require intersection with available_fields
            if sensor_key in {"humidity", "pm25", "pm10", "voc", "co2"} and not (available_fields & needed):
                continue
            keys.append(sensor_key)
    return keys
```

Add class:

```python
class MolekulePreFilterSensor(MolekuleSensorBase):
    def __init__(self, coordinator, device_id, api):
        super().__init__(coordinator, device_id, api, "pre_filter")
        self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self):
        if not self._device:
            return None
        raw = self._device.get("preFilter") or self._device.get("prefilter")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
```

In `async_setup_entry`, delete local `MODEL_CAPABILITIES` / `DEFAULT_CAPABILITIES` and build sensors via `sensor_keys_for_capabilities` + a small factory map.

For Mini particle sensors: available fields come from `coordinator.data[serial]` after sensordata fetch.

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest tests/ -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add custom_components/molekule/sensor.py custom_components/molekule/sensor_helpers.py tests/test_sensor_selection.py
git commit -m "Add capability-based sensors including pre-filter"
```

---

### Task 7: Docs + version bump

**Files:**
- Modify: `README.md`
- Modify: `custom_components/molekule/manifest.json`

- [ ] **Step 1: Bump version**

In `manifest.json`, set `"version": "0.2.0"`.

- [ ] **Step 2: Update README supported models**

Document:

- Molekule Air Pro (existing)
- Molekule Air Mini+ / Mini Plus 2 — Auto Protect, speeds 1–5, AQI/PECO (+ sensordata if available)
- Molekule Air (original) — Silent/Auto/Boost, PECO + Pre-filter

Note fork install: HACS custom repository `sven-7/home-assistant-molekule`.

- [ ] **Step 3: Commit**

```bash
git add README.md custom_components/molekule/manifest.json
git commit -m "Document Mini/original support and bump to 0.2.0"
```

---

### Task 8: Install on HA and verify checklist

**Files:** none (manual / ops)

- [ ] **Step 1: Push fork branch if needed**

```bash
git push -u origin HEAD
```

- [ ] **Step 2: Point HACS at `sven-7/home-assistant-molekule`, update, restart HA**

- [ ] **Step 3: Verify against design checklist**

- [ ] Mini Plus: Auto Protect works
- [ ] Mini Plus 2: Auto Protect works
- [ ] Minis: fan speeds 1–5
- [ ] Original: Silent / Auto / Boost
- [ ] Original: PECO + Pre-filter (and any other returned fields)
- [ ] Minis: AQI + PECO; richer sensors if API returns them
- [ ] Existing config entry still loads (domain unchanged)

- [ ] **Step 4: Fix any discovery mismatches found in HA logs** (`Unknown Molekule model ...`) and commit follow-ups

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Shared capability table / aliases | Task 2 |
| Mini 1–5 + Auto Protect | Task 4 |
| Original Silent/Auto/Boost | Task 5 |
| Mini sensors AQI/PECO + sensordata ∩ payload | Tasks 3, 6 |
| Original PECO + Pre-filter + other fields | Task 6 |
| Unknown model inference + log | Tasks 2–3 |
| Discovery-first exact names | Task 1 |
| Keep domain `molekule` / HACS fork | Tasks 7–8 |
| Air Pro unchanged | Task 2 tests + Task 8 |
| No invented original particle sensors | Task 6 |

## Placeholder / consistency notes

- Task 1 **must** replace provisional `MODEL_ALIASES` and original action mappings before Tasks 4–5 are considered done.
- Preset id for Mini/Pro is `auto_protect` (not legacy `auto`) per design.
- `set_auto_mode(False)` may use `/actions/manual` with fan-speed fallback.
