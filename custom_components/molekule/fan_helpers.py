"""Pure helpers for fan preset mapping (unit-tested without Home Assistant)."""
from __future__ import annotations

try:
    from .const import (
        API_MODE_MANUAL,
        API_MODE_SMART,
        PRESET_AUTO,
        PRESET_AUTO_PROTECT,
        PRESET_BOOST,
        PRESET_MANUAL,
        PRESET_SILENT,
    )
except ImportError:
    from const import (
        API_MODE_MANUAL,
        API_MODE_SMART,
        PRESET_AUTO,
        PRESET_AUTO_PROTECT,
        PRESET_BOOST,
        PRESET_MANUAL,
        PRESET_SILENT,
    )


def preset_from_device_mode(
    mode: str | None, preset_modes: tuple[str, ...]
) -> str | None:
    """Map a device API mode to an available Home Assistant preset."""
    if not preset_modes:
        return None
    if mode == API_MODE_SMART and PRESET_AUTO_PROTECT in preset_modes:
        return PRESET_AUTO_PROTECT
    if PRESET_MANUAL in preset_modes:
        return PRESET_MANUAL
    return None


def api_auto_requested(preset_mode: str) -> bool:
    """Return whether a preset requests Molekule Auto Protect mode."""
    return preset_mode == PRESET_AUTO_PROTECT


def original_preset_from_device(device: dict[str, object]) -> str | None:
    """Best-effort mapping of an original Molekule device payload to a preset.

    The original device dump only observed ``mode="on"`` with blank ``silent``
    and ``burst`` fields.  These precedence rules are provisional until Task 8
    records app toggles for Silent, Auto, and Boost.
    """
    mode = device.get("mode")
    if mode in ("off", None):
        return None
    if mode == API_MODE_SMART:
        return PRESET_AUTO

    burst = device.get("burst")
    if burst not in ("", "0", "N/A", None):
        return PRESET_BOOST

    silent = device.get("silent")
    if silent not in ("", "0", "false", None):
        return PRESET_SILENT

    fanspeed = str(device.get("fanspeed", ""))
    if fanspeed == "1":
        return PRESET_SILENT
    if fanspeed == "3":
        return PRESET_BOOST
    if mode in ("on", API_MODE_MANUAL):
        return PRESET_AUTO
    return None


def original_preset_to_action(preset_mode: str) -> tuple[str, dict[str, int | str]]:
    """Map an original Molekule preset to its provisional API action."""
    actions = {
        PRESET_SILENT: ("set-fan-speed", {"fanSpeed": 1}),
        PRESET_AUTO: ("enable-smart-mode", {"silent": "0"}),
        PRESET_BOOST: ("set-fan-speed", {"fanSpeed": 3}),
    }
    try:
        return actions[preset_mode]
    except KeyError as err:
        raise ValueError(f"Unsupported original Molekule preset: {preset_mode}") from err
