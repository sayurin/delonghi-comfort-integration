"""Climate platform for De'Longhi Comfort integration."""

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import indexed_value, numeric_value


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up De'Longhi heater climate entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        DeLonghiHeater(coordinator=coordinator)
        for coordinator in data["heater_coordinators"]
    )


class DeLonghiHeater(CoordinatorEntity, ClimateEntity):
    """Representation of a De'Longhi heater climate entity."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "heater"
    _attr_fan_modes = ["0", "20", "40", "60", "80", "100"]
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_max_temp = 28
    _attr_min_temp = 10
    _attr_preset_modes = ["day_mode", "night_mode", "antifrost", "manual"]
    _attr_target_temperature_step = 0.5
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"delonghi_heater_{coordinator.dsn}"
        self._attr_device_info = coordinator.get_device_info()

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation mode."""
        status = numeric_value(self.coordinator.data.get("device_status"))
        return {1: HVACMode.HEAT, 2: HVACMode.OFF}.get(status)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        status = numeric_value(self.coordinator.data.get("device_status"))
        if status == 1:  # ON
            power_level = numeric_value(self.coordinator.data.get("MDH_Resources"))
            if power_level == 0:
                return HVACAction.IDLE
            if power_level is not None and power_level > 0:
                return HVACAction.HEATING
        return HVACAction.OFF if status == 2 else None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return indexed_value(
            self.coordinator.data.get("device_mode"), self.preset_modes, 1
        )

    @property
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return numeric_value(self.coordinator.data.get("room_temp"))

    @property
    def native_target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return numeric_value(self.coordinator.data.get("temperature_setpoint"))

    @property
    def fan_mode(self) -> str | None:
        """Return the fan mode."""
        return indexed_value(
            self.coordinator.data.get("current_power_level"), self.fan_modes
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()
        else:
            raise ServiceValidationError("Unsupported heater HVAC mode")

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.coordinator.async_set_property("set_status", 1)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.coordinator.async_set_property("set_status", 2)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode not in self.preset_modes:
            raise ServiceValidationError("Unsupported heater preset mode")
        device_mode = self.preset_modes.index(preset_mode) + 1
        await self.coordinator.async_set_property("set_device_mode", device_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode not in self.fan_modes:
            raise ServiceValidationError("Unsupported heater power level")
        power_level = self.fan_modes.index(fan_mode)
        await self.coordinator.async_set_property("set_power_level", power_level)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = numeric_value(kwargs.get(ATTR_TEMPERATURE))
        if (
            temperature is None
            or not self.min_temp <= temperature <= self.max_temp
            or temperature % self.target_temperature_step
        ):
            raise ServiceValidationError("Heater temperature must be 10-28 C in 0.5 C steps")
        await self.coordinator.async_set_property("temperature_setpoint", temperature)
