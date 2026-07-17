from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.percentage import (
    int_states_in_range,
    ranged_value_to_percentage,
    percentage_to_ranged_value,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .capabilities import capabilities_for_device
from .const import (
    API_MODE_SMART,
    CONF_SILENT_AUTO,
    DOMAIN,
    PRESET_AUTO,
    PRESET_AUTO_PROTECT,
    PRESET_MANUAL,
)
from .fan_helpers import (
    api_auto_requested,
    original_preset_from_device,
    original_preset_to_action,
    preset_from_device_mode,
)
import logging
import asyncio
import time

_LOGGER = logging.getLogger(__name__)

# Cloud state often lags the action response.
_STATE_SETTLE_TIMEOUT = 12.0
_STATE_POLL_INTERVAL = 1.5


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    fans = []
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.data or "content" not in coordinator.data:
        _LOGGER.error("No data received from the Molekule API")
        return

    for device in coordinator.data["content"]:
        fans.append(MolekuleFan(coordinator, device["serialNumber"], api))

    async_add_entities(fans, True)


class MolekuleFan(CoordinatorEntity, FanEntity):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api):
        super().__init__(coordinator)
        self._device_id = device_id
        self._api = api
        self._attr_unique_id = f"{device_id}_fan"

        self._caps = capabilities_for_device(self._device or {})
        # On/off maps to Molekule standby via set-power-status (app may not
        # label this "power", but the cloud API does).
        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if self._caps.fan_control == "speed" and self._caps.max_fan_speed:
            features |= FanEntityFeature.SET_SPEED
        if self._caps.preset_modes:
            features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = list(self._caps.preset_modes)
        self._attr_supported_features = features

        self._attr_device_info = coordinator.data[device_id]["device_info"]

    @property
    def _device(self):
        return next(
            (
                device
                for device in self.coordinator.data["content"]
                if device["serialNumber"] == self._device_id
            ),
            None,
        )

    @property
    def _speed_range(self):
        return (1, self._caps.max_fan_speed or 3)

    @property
    def name(self):
        return f"{self._device['name']} Fan" if self._device else None

    @property
    def is_on(self):
        return self._device["mode"] != "off" if self._device else None

    @property
    def percentage(self):
        if self._caps.fan_control != "speed":
            return None
        if not self._device or self._device["mode"] == "off":
            return 0
        # In Auto Protect, speed is managed by the device — don't imply manual.
        if self._device.get("mode") == API_MODE_SMART:
            return None
        return ranged_value_to_percentage(
            self._speed_range, int(self._device["fanspeed"])
        )

    @property
    def preset_mode(self):
        if self._caps.fan_control == "presets":
            return original_preset_from_device(self._device or {})
        return preset_from_device_mode(
            self._device.get("mode") if self._device else None,
            self._caps.preset_modes,
        )

    @property
    def speed_count(self):
        if self._caps.fan_control != "speed":
            return None
        return int_states_in_range(self._speed_range)

    async def _refresh_until(self, predicate, description: str) -> bool:
        """Poll coordinator until predicate passes or timeout."""
        deadline = time.monotonic() + _STATE_SETTLE_TIMEOUT
        while time.monotonic() < deadline:
            await self.coordinator.async_request_refresh()
            if predicate():
                return True
            await asyncio.sleep(_STATE_POLL_INTERVAL)
        _LOGGER.warning(
            "%s: timed out waiting for %s (last mode=%s fanspeed=%s)",
            self.name,
            description,
            (self._device or {}).get("mode"),
            (self._device or {}).get("fanspeed"),
        )
        return False

    async def async_set_percentage(self, percentage: int) -> None:
        if self._caps.fan_control != "speed":
            raise HomeAssistantError("Fan speed is not supported by this Molekule model")
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = round(percentage_to_ranged_value(self._speed_range, percentage))
        # Setting an explicit speed also leaves Auto Protect (homebridge pattern).
        ok = await self._api.set_fan_speed(self._device_id, speed)
        if not ok:
            raise HomeAssistantError("Failed to set Molekule fan speed")
        await self._refresh_until(
            lambda: self._device
            and self._device.get("mode") != API_MODE_SMART
            and str(self._device.get("fanspeed")) == str(speed),
            f"manual speed {speed}",
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in self._caps.preset_modes:
            raise ValueError(f"Unsupported preset: {preset_mode}")

        if self._caps.fan_control == "presets":
            # Original Air: Silent/Auto/Boost == fan speeds 1/2/3.
            if not self.is_on:
                if not await self._api.set_power_status(self._device_id, True):
                    raise HomeAssistantError("Failed to wake Molekule from standby")
            action, body = original_preset_to_action(preset_mode)
            ok = await self._api.set_mode_action(self._device_id, action, body)
            if not ok:
                raise HomeAssistantError("Failed to set Molekule preset mode")
            expected = str(body["fanSpeed"])
            await self._refresh_until(
                lambda: self._device
                and self._device.get("mode") != "off"
                and str(self._device.get("fanspeed")) == expected,
                f"original preset {preset_mode}",
            )
            return

        silent_auto = self.coordinator.config_entry.options.get(CONF_SILENT_AUTO, False)

        if api_auto_requested(preset_mode):
            if not self.is_on:
                if not await self._api.set_power_status(self._device_id, True):
                    raise HomeAssistantError("Failed to wake Molekule from standby")
            ok = await self._api.set_auto_mode(self._device_id, True, silent_auto)
            if not ok:
                raise HomeAssistantError(
                    "Failed to set Molekule Auto Protect (API rejected the request)"
                )
            await self._refresh_until(
                lambda: self._device and self._device.get("mode") == API_MODE_SMART,
                "Auto Protect (smart)",
            )
            return

        if preset_mode == PRESET_MANUAL:
            # Leave smart mode by setting an explicit speed (keep current if known).
            try:
                current = int((self._device or {}).get("fanspeed") or 1)
            except (TypeError, ValueError):
                current = 1
            current = max(self._speed_range[0], min(self._speed_range[1], current))
            ok = await self._api.set_auto_mode(self._device_id, False, silent_auto)
            if not ok:
                ok = await self._api.set_fan_speed(self._device_id, current)
            if not ok:
                raise HomeAssistantError("Failed to leave Molekule Auto Protect")
            await self._refresh_until(
                lambda: self._device and self._device.get("mode") != API_MODE_SMART,
                "manual mode",
            )
            return

        raise HomeAssistantError(f"Unsupported Molekule preset: {preset_mode}")

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        if not self.is_on:
            ok = await self._api.set_power_status(self._device_id, True)
            if not ok:
                raise HomeAssistantError("Failed to turn on Molekule")

        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif self._caps.fan_control == "speed":
            await self.async_set_percentage(
                ranged_value_to_percentage(self._speed_range, self._speed_range[0])
            )
        elif self._caps.fan_control == "presets":
            # Original: wake to Auto (speed 2) if no preset given.
            await self.async_set_preset_mode(PRESET_AUTO)
        else:
            await self._refresh_until(
                lambda: self._device and self._device.get("mode") != "off",
                "power on",
            )

    async def async_turn_off(self, **kwargs) -> None:
        ok = await self._api.set_power_status(self._device_id, False)
        if not ok:
            raise HomeAssistantError("Failed to turn off Molekule")
        await self._refresh_until(
            lambda: self._device and self._device.get("mode") == "off",
            "power off / standby",
        )
