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
from .const import CONF_SILENT_AUTO, DOMAIN, PRESET_AUTO_PROTECT
from .fan_helpers import (
    api_auto_requested,
    original_preset_from_device,
    original_preset_to_action,
    preset_from_device_mode,
)
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

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
        return next((device for device in self.coordinator.data["content"] if device["serialNumber"] == self._device_id), None)

    @property
    def _speed_range(self):
        return (1, self._caps.max_fan_speed or 3)

    @property
    def name(self):
        return f"{self._device['name']} Fan" if self._device else None

    @property
    def is_on(self):
        return self._device['mode'] != "off" if self._device else None

    @property
    def percentage(self):
        if self._caps.fan_control != "speed":
            return None
        if not self._device or self._device['mode'] == "off":
            return 0
        return ranged_value_to_percentage(self._speed_range, int(self._device['fanspeed']))

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

    async def async_set_percentage(self, percentage: int) -> None:
        if self._caps.fan_control != "speed":
            raise HomeAssistantError("Fan speed is not supported by this Molekule model")
        if percentage == 0:
            await self.async_turn_off()
        else:
            speed = round(percentage_to_ranged_value(self._speed_range, percentage))
            await self._api.set_fan_speed(self._device_id, speed)
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in self._caps.preset_modes:
            raise ValueError(f"Unsupported preset: {preset_mode}")
        if self._caps.fan_control == "presets":
            action, body = original_preset_to_action(preset_mode)
            ok = await self._api.set_mode_action(self._device_id, action, body)
            if not ok:
                raise HomeAssistantError("Failed to set Molekule preset mode")
            await self.coordinator.async_request_refresh()
            return
        if PRESET_AUTO_PROTECT not in self._caps.preset_modes:
            raise HomeAssistantError("Preset control is not implemented for this Molekule model")

        silent_auto = self.coordinator.config_entry.options.get(CONF_SILENT_AUTO, False)
        ok = await self._api.set_auto_mode(
            self._device_id, api_auto_requested(preset_mode), silent_auto
        )
        if not ok:
            raise HomeAssistantError("Failed to set Molekule preset mode")
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs) -> None:
        if not self.is_on:
            await self._api.set_power_status(self._device_id, True)
        
        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif self._caps.fan_control == "speed":
            # If no percentage or preset_mode is provided, set to the lowest speed
            await self.async_set_percentage(ranged_value_to_percentage(self._speed_range, self._speed_range[0]))
        
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self._api.set_power_status(self._device_id, False)
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
