"""The De'Longhi Comfort integration."""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_LANGUAGE,
    CONF_SCAN_INTERVAL,
    DEFAULT_LANGUAGE,
    SUPPORTED_MODELS,
)
from .api import DeLonghiAPI, DeLonghiAuthenticationError, DeLonghiError
from .coordinator import DeLonghiCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up De'Longhi Comfort from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    language = entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)

    session = async_get_clientsession(hass)
    api = DeLonghiAPI(username, password, session, language)

    try:
        await api.authenticate()
        devices = await api.get_devices()
    except DeLonghiAuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from None
    except DeLonghiError as err:
        raise ConfigEntryNotReady(str(err)) from None
    if not devices:
        raise ConfigEntryNotReady("No De'Longhi devices found on the account")

    supported_devices = [
        device for device in devices
        if device["device"].get("oem_model") in SUPPORTED_MODELS
    ]
    unsupported_count = len(devices) - len(supported_devices)
    if unsupported_count:
        _LOGGER.warning(
            "Skipping %s unsupported De'Longhi device(s); only DL-heater is supported",
            unsupported_count,
        )
    if not supported_devices:
        raise ConfigEntryError("No supported De'Longhi devices found; only DL-heater is supported")

    # Create coordinators for each device
    heater_coordinators = []
    for device in supported_devices:
        device_info = device["device"]
        dsn = device_info["dsn"]

        coordinator = DeLonghiCoordinator(hass, api, dsn, device_info, entry)
        await coordinator.async_config_entry_first_refresh()
        heater_coordinators.append(coordinator)

    # Store API instance, devices, and coordinators in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "devices": supported_devices,
        "heater_coordinators": heater_coordinators,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the De'Longhi Comfort integration."""
    # This integration is only configurable via config flow
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
