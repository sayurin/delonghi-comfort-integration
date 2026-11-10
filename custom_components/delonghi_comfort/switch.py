"""Switch platform for De'Longhi Comfort integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import numeric_value

HEATER_DESCRIPTIONS = (
    SwitchEntityDescription(
        key="eco",
        icon="mdi:sprout",
        translation_key="eco",
    ),
    SwitchEntityDescription(
        key="lock",
        icon="mdi:lock",
        translation_key="lock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up De'Longhi heater switch entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        HeaterSwitch(coordinator=coordinator, description=description)
        for coordinator in data["heater_coordinators"]
        for description in HEATER_DESCRIPTIONS
    )


class HeaterSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a De'Longhi heater switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"delonghi_heater_{coordinator.dsn}_{description.key}"
        self._attr_device_info = coordinator.get_device_info()

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        value = numeric_value(
            self.coordinator.data.get(f"get_{self.entity_description.key}")
        )
        return bool(value) if value in (0, 1) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.async_set_property(f"set_{self.entity_description.key}", 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.async_set_property(f"set_{self.entity_description.key}", 0)
