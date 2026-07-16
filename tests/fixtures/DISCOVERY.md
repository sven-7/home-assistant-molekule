# Discovery notes

Filled from `dump_molekule_devices.py` run 2026-07-16.

| Friendly | API `subProduct.name` | Observed mode values | Filter keys | sensordata |
|----------|------------------------|----------------------|-------------|------------|
| Lounge (Mini Plus / Plus 2) | `Air Mini Plus` | `smart`, `manual` | `pecoFilter` present (may be `""`); `preFilter` present but empty | Yes — `PM2_5` returned; `PM10`/`RH`/`TVOC`/`CO2` null |
| Lil boy (Mini Plus / Plus 2) | `Air Mini Plus` | `smart`, `manual` | same | same |
| Mini Plus 2 (no separate API string) | N/A — same as `Air Mini Plus` | — | — | — |
| Biggy (Original) | `Molekule Air` | `on` (when powered; not `smart`/`manual`) | `pecoFilter`=`98`, `preFilter`=`97` | No — API 400 `Device does not support sensor data` |

## Alias notes

- Both Mini units use the **same** API model string: `Air Mini Plus` (product code `MN`, serial prefix `MN2`). There is **no** separate Mini Plus 2 model name in the API — treat both as family `mini_plus`.
- Device field `model` on Minis may say `Air Mini Pro` even when `subProduct.name` is `Air Mini Plus` — always key capabilities off `subProduct.name`.
- Original product code `MH` / prefix `MH1`.

## Mode / preset mapping (from live fields)

### Mini Plus (`Air Mini Plus`)

- Auto Protect ↔ API `mode == "smart"`; enable via existing `enable-smart-mode`
- Manual ↔ API `mode == "manual"`; fan speed via `set-fan-speed` (observed speeds 2–3; app range 1–5)
- Also has `silent`, `burst` fields (`burst` observed `"0"`)

### Original (`Molekule Air`)

App UX is Silent / Auto / Boost, but API does **not** use those as `mode` strings.

Observed while on:
- `mode`: `"on"` (off would be `"off"` — confirm when toggling power)
- `silent`: `""` (empty at capture)
- `burst`: `"N/A"`
- `fanspeed`: `"2"`
- `aqi`: `""` (empty — do not invent AQI entity unless non-empty)

**Working hypothesis for Task 5** (confirm by toggling in app and re-dumping):
- Silent → set `silent` / low fanspeed (likely speed 1) while `mode=on`
- Auto → may use smart-mode or a dedicated action (not observed in this dump)
- Boost → may set `burst` or max fanspeed

Do not hardcode Silent/Auto/Boost → `smart`/`manual` for original without a second dump after mode changes.

## Sensor policy from dump

- Mini: create AQI + PECO; create PM2.5 when sensordata returns a value; skip empty `preFilter`; skip null particle metrics
- Original: create PECO + Pre-filter; skip sensordata; skip AQI while `aqi` is empty
