"""Select platform for De'Longhi Comfort integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import indexed_value


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up De'Longhi heater select entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        HeaterBrightness(coordinator=coordinator)
        for coordinator in data["heater_coordinators"]
    )


class HeaterBrightness(CoordinatorEntity, SelectEntity):
    """Representation of a heater brightness entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:brightness-6"
    _attr_name = "Display brightness"
    _attr_options = ["Level 1", "Level 2", "Level 3"]

    def __init__(self, coordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"delonghi_heater_{coordinator.dsn}_brightness"
        self._attr_device_info = coordinator.get_device_info()

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return indexed_value(
            self.coordinator.data.get("current_brightness"), self.options, 1
        )

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option not in self.options:
            raise ServiceValidationError("Unsupported heater brightness")
        await self.coordinator.async_set_property(
            "set_brightness", self.options.index(option) + 1
        )
