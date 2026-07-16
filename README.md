![logo](https://github.com/user-attachments/assets/65b8b825-56c5-41db-8d95-6bdddef1ddf2)

# README

Home Assistant Molekule Integration

Version: 0.2.0

### Description

This integration provides support for Molekule devices directly integrated into Home Assistant.

This is a fork of [cowboyrushforth/home-assistant-molekule](https://github.com/cowboyrushforth/home-assistant-molekule) with added support for Air Mini Plus / Mini Plus 2 and improved handling for the original Molekule Air.

This relies on the cloud; it talks directly to Molekule's web API.

### Supported models

| Model | Fan control | Sensors |
| --- | --- | --- |
| **Molekule Air Pro** | Auto + manual, speeds 1–6 | Air Quality, VOC, Humidity, PM2.5, PM10, CO2, PECO filter |
| **Air Mini Plus / Mini Plus 2** | Auto Protect + manual, speeds 1–5 | Air Quality, PECO filter (+ PM2.5 when the API returns sensordata) |
| **Molekule Air (original)** | Silent / Auto / Boost presets (provisional) | Air Quality, PECO filter, Pre-filter |

Mini Plus 2 uses the same API model name as Air Mini Plus (`Air Mini Plus`).

Depending on your model, sensors may include:

* Air Quality
* VOC
* Humidity
* PM2.5
* PM10
* CO2
* PECO filter life
* Pre-filter life (original Molekule Air only)

The fan entity lets you:

* Control mode (Automatic / Manual, or presets on the original unit)
* Control fan speed or preset

There is configuration for:

* How often to poll Molekule's API
* Whether to enable "Quiet" (aka Silent) mode when the unit is set to Automatic (Air Pro)

### Installation

This integration requires [HACS](https://hacs.xyz/).

Install from this fork by adding `sven-7/home-assistant-molekule` [as a custom repository in HACS](https://hacs.xyz/docs/faq/custom_repositories/), then search for **Molekule** and install.

The upstream repository is `cowboyrushforth/home-assistant-molekule`; use this fork for Mini Plus and original Air support.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=molekule)

### Notes

* Pull Requests and Issues are welcome on this fork.
* Air Pro behavior matches the upstream integration; Mini and original support is newer and less field-tested.
* Original Molekule Silent/Auto/Boost preset mapping is provisional pending further live API validation.
* This was inspired by: https://github.com/csirikak/homebridge-molekule  (Thanks!)
