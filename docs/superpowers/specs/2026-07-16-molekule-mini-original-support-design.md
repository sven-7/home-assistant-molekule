# Molekule Mini / Original Support Design

**Date:** 2026-07-16  
**Status:** Approved for planning  
**Base:** Fork of [cowboyrushforth/home-assistant-molekule](https://github.com/cowboyrushforth/home-assistant-molekule) → `sven-7/home-assistant-molekule`  
**Approach:** Extend existing integration (domain `molekule`) rather than rewrite

## Problem

The current integration only fully supports **Molekule Air Pro** (and partially original Air). Unknown models fall through to weak defaults:

- Fan: max speed 3, **no Auto**
- Sensors: air quality + PECO only

The user has:

1. **Molekule Mini Plus**
2. **Molekule Mini Plus 2** (same app behavior as Mini Plus)
3. **Original Molekule** (different mode model; fewer sensors)

All three connect today, but Auto / Auto Protect and richer sensors do not work correctly.

## Goals

1. **Auto / Smart / Auto Protect** control for Mini Plus and Mini Plus 2
2. **Richer sensors** wherever the Molekule cloud API returns them
3. Correct control model for the **original** unit (Silent / Auto / Boost; PECO + Pre-filter; whatever else the API exposes)
4. Keep HA domain `molekule` so existing config entries can survive a HACS repo swap

## Non-goals (this iteration)

- Local/LAN control (cloud polling stays)
- Full rewrite onto `jpcaldwell30/molekule-air`
- Guaranteeing sensors the API never returns for a given model

## Capability model

Centralize device behavior in one shared capability table used by fan + sensor platforms, keyed by API `subProduct.name` with aliases for naming variants.

| Model family | Fan | Modes | Sensors |
|---|---|---|---|
| **Mini Plus / Mini Plus 2** | Speeds **1–5** | **Auto Protect** (`smart`) + manual | AQI, PECO; plus any `sensordata` metrics present (PM2.5, PM10, humidity, VOC, CO2) |
| **Original Molekule Air** | Not a 1–N primary slider | **Silent / Auto / Boost** presets | PECO + **Pre-filter**; AQI and any other fields the API returns; no inventing particle sensors the app lacks |
| **Air Pro** (keep existing) | 1–6 | Auto + manual | Full sensor suite as today |

**Unknown models:** infer from the live device payload (available mode values, sensor fields, max fan speed hints) instead of silently using “max 3, no Auto.” Log the unknown model and observed fields once.

Upstream `non_pro` branch exists as historical reference only; implementation builds on current `main`.

## Fan / mode control

### Mini Plus / Mini Plus 2

- Features: `SET_SPEED` + `PRESET_MODE` + on/off
- Speed range maps to API fan speed **1–5**
- HA presets: `auto_protect`, `manual` (friendly name **Auto Protect**)
- `auto_protect` → API `smart` (reuse existing silent-auto option when supported)
- Leaving Auto / choosing Manual → `manual` + explicit or last speed

### Original Molekule

- Primary UX is presets, not a percentage speed slider
- HA presets: `silent`, `auto`, `boost` (friendly names **Silent / Auto / Boost**)
- API mode/action strings for those three presets are a **required discovery input** before coding the original fan path (see Delivery)
- On/off via existing power-status API

### Shared

- Refresh coordinator after commands; keep short post-command delay only if the API still needs it
- Capabilities always come from the device’s resolved model entry, never a global default that disables Auto

## Sensors

Create entities from **capabilities ∩ actual API fields** (do not invent empty sensors).

### Mini Plus / Mini Plus 2

- Always: Air Quality (AQI), PECO filter %
- If `sensordata` succeeds for that serial: expose returned metrics only for keys present
- No pre-filter entity

### Original Molekule

- PECO filter %
- Pre-filter % (new sensor; field name from live payload)
- AQI and any other useful fields the devices endpoint returns (“whatever we can get out of the app/API”)
- Do not call `sensordata` for particle metrics the app does not support; avoid empty/erroring entities

### Coordinator

- One poll cycle for device list
- Per-device `sensordata` fetch only when model capability `has_sensor_data` is true
- Missing/failed sensor reads → entity unavailable / `None`, not a failed integration update for the whole account

## Delivery

1. Work in fork `sven-7/home-assistant-molekule`
2. **First implementation step:** capture live `devices` (+ `sensordata` where applicable) for all three units to lock:
   - Exact `subProduct.name` strings
   - Mode values / action endpoints for Auto Protect, Silent, Auto, Boost
   - Filter field names (PECO, pre-filter)
3. Fill capability tables from that evidence
4. Install via HACS custom repository pointing at the fork (same domain `molekule`)

## Error handling

- Keep Cognito auth + token refresh; fix only if bugs appear during testing
- Unknown model → best-effort inference + one diagnostic log with model name and available fields
- Command failures raise HA errors; avoid stuck optimistic UI state

## Verification checklist

- [ ] Mini Plus: Auto Protect preset works
- [ ] Mini Plus 2: Auto Protect preset works
- [ ] Mini Plus / Mini Plus 2: fan speeds 1–5
- [ ] Original: Silent / Auto / Boost presets work
- [ ] Original: PECO + Pre-filter sensors (and any other available fields)
- [ ] Minis: AQI + PECO; richer sensors if API returns them
- [ ] Air Pro behavior unchanged if present on an account
- [ ] HACS swap keeps existing config entry usable

## Success criteria

User can control Auto Protect on both Minis and Silent/Auto/Boost on the original from Home Assistant, and sees the richest sensor set each model’s cloud API actually provides.
