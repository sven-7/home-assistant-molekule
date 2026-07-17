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

# Original Molekule Air has no cloud smart/auto mode (homebridge
# AutoFunctionality=0). App labels Silent / Auto / Boost are the three
# discrete fan speeds.
_ORIGINAL_SPEED_TO_PRESET = {
    "1": PRESET_SILENT,
    "2": PRESET_AUTO,
    "3": PRESET_BOOST,
}
_ORIGINAL_PRESET_TO_SPEED = {
    PRESET_SILENT: 1,
    PRESET_AUTO: 2,
    PRESET_BOOST: 3,
}


def preset_from_device_mode(
    mode: str | None, preset_modes: tuple[str, ...]
) -> str | None:
    """Map a device API mode to an available Home Assistant preset."""
    if not preset_modes:
        return None
    if mode == API_MODE_SMART:
        if PRESET_AUTO in preset_modes:
            return PRESET_AUTO
        if PRESET_AUTO_PROTECT in preset_modes:
            return PRESET_AUTO_PROTECT
        return None
    if mode in (API_MODE_MANUAL, "on") and PRESET_MANUAL in preset_modes:
        return PRESET_MANUAL
    if PRESET_MANUAL in preset_modes and mode not in ("off", None):
        return PRESET_MANUAL
    return None


def api_auto_requested(preset_mode: str) -> bool:
    """Return whether a preset requests Molekule Auto Protect mode."""
    return preset_mode in (PRESET_AUTO, PRESET_AUTO_PROTECT)


def original_preset_from_device(device: dict[str, object]) -> str | None:
    """Map original Molekule Air state to Silent / Auto / Boost.

    These presets are fan-speed labels (1/2/3), not cloud smart mode.
    """
    mode = device.get("mode")
    if mode in ("off", None):
        return None
    fanspeed = str(device.get("fanspeed", "")).strip()
    return _ORIGINAL_SPEED_TO_PRESET.get(fanspeed)


def original_preset_to_action(preset_mode: str) -> tuple[str, dict[str, int | str]]:
    """Map an original Molekule preset to set-fan-speed."""
    try:
        speed = _ORIGINAL_PRESET_TO_SPEED[preset_mode]
    except KeyError as err:
        raise ValueError(f"Unsupported original Molekule preset: {preset_mode}") from err
    return ("set-fan-speed", {"fanSpeed": speed})
