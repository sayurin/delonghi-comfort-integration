"""Data update coordinator for De'Longhi Comfort integration."""

from datetime import timedelta
import logging
import math
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DeLonghiAPI, DeLonghiAuthenticationError, DeLonghiError
from .const import SCAN_INTERVAL, CONF_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def numeric_value(value: Any) -> float | None:
    """Return finite numeric telemetry, including numeric API strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def indexed_value(value: Any, options: list[str], first_value: int = 0) -> str | None:
    """Map only integral values within the documented device enum."""
    number = numeric_value(value)
    if number is None or not number.is_integer():
        return None
    index = int(number) - first_value
    return options[index] if 0 <= index < len(options) else None


class DeLonghiCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage data updates for De'Longhi devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DeLonghiAPI,
        dsn: str,
        device_info: dict[str, Any],
        config_entry,
    ) -> None:
        """Initialize the coordinator."""
        # Get scan interval from options, fallback to default
        scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=f"delonghi_comfort_{dsn}",
            config_entry=config_entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.dsn = dsn
        self.device_name = device_info.get("product_name", f"De'Longhi {dsn}")
        self.device_model = device_info.get("model", "Unknown")
        self.device_version = device_info.get("sw_version")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API."""
        try:
            properties = await self.api.get_device_properties(self.dsn)
            if not properties:
                raise UpdateFailed("De'Longhi returned no device properties")

            # Parse properties into a more usable format
            data = {}
            for prop in properties:
                if "property" in prop:
                    prop_info = prop["property"]
                    data[prop_info["name"]] = prop_info["value"]

        except DeLonghiAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from None
        except DeLonghiError as err:
            raise UpdateFailed(str(err)) from None
        else:
            return data

    def get_device_info(self) -> DeviceInfo:
        """Return device information for this coordinator."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.dsn)},
            manufacturer="De'Longhi",
            model=self.data.get("appliance_model") or self.device_model,
            name=self.device_name,
            hw_version=self.data.get("hardware_version"),
            sw_version=self.device_version,
        )

    async def async_set_property(self, name: str, value: int | float) -> None:
        """Report command failures to HA and refresh only after acceptance."""
        if not await self.api.set_device_property(self.dsn, name, value):
            raise HomeAssistantError("De'Longhi did not accept the device command")
        await self.async_request_refresh()
