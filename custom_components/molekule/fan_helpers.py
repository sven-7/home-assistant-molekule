"""Pure helpers for fan preset mapping (unit-tested without Home Assistant)."""
from __future__ import annotations

try:
    from .const import API_MODE_SMART, PRESET_AUTO_PROTECT, PRESET_MANUAL
except ImportError:
    from const import API_MODE_SMART, PRESET_AUTO_PROTECT, PRESET_MANUAL


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
