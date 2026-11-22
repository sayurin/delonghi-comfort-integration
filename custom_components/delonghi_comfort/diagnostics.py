"""On-demand account diagnostics for De'Longhi Comfort."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .api import (
    DeLonghiAPI,
    DeLonghiAuthenticationError,
    DeLonghiConnectionError,
    DeLonghiProtocolError,
)
from .const import (
    CONF_LANGUAGE,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_LANGUAGE,
    DOMAIN,
    SUPPORTED_MODELS,
)

_LOGGER = logging.getLogger(__name__)


async def _async_create_api(hass: HomeAssistant, entry: ConfigEntry) -> DeLonghiAPI:
    """Authenticate a diagnostic session."""
    api = DeLonghiAPI(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        async_get_clientsession(hass),
        entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
    )
    await api.authenticate()
    return api


async def _async_collect_devices(
    api: DeLonghiAPI, devices: list[dict[str, Any]]
) -> dict[str, Any]:
    """Collect only the supplied devices without transforming API responses."""
    diagnostics = []
    for index, item in enumerate(devices, start=1):
        device = item["device"]
        model = device.get("oem_model")
        record: dict[str, Any] = {
            "device": {
                "index": index,
                "supported": model in SUPPORTED_MODELS
                if isinstance(model, str)
                else None,
                **{
                    key: device[key]
                    for key in ("oem_model", "model", "sw_version")
                    if key in device
                },
            },
        }
        try:
            properties = await api.get_device_properties(device["dsn"])
        except DeLonghiAuthenticationError:
            raise
        except (DeLonghiConnectionError, DeLonghiProtocolError) as err:
            error = (
                "cannot_connect"
                if isinstance(err, DeLonghiConnectionError)
                else "unexpected_response"
            )
            _LOGGER.warning("Device %s diagnostics failed: %s", index, error)
            record["error"] = error
        else:
            record["properties"] = properties
        diagnostics.append(record)
    return {"devices": diagnostics}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Fetch all account devices, including unsupported models, only on request."""
    api = await _async_create_api(hass, entry)
    return await _async_collect_devices(api, await api.get_devices())


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Fetch only the selected registered device, without downloading the account list."""
    dsns = [identifier for domain, identifier in device.identifiers if domain == DOMAIN]
    if len(dsns) != 1:
        raise HomeAssistantError(
            "De'Longhi diagnostic device identifier is missing or ambiguous"
        )
    api = await _async_create_api(hass, entry)
    return await _async_collect_devices(
        api,
        [
            {
                "device": {
                    "dsn": dsns[0],
                    "model": device.model,
                    "sw_version": device.sw_version,
                }
            }
        ],
    )
