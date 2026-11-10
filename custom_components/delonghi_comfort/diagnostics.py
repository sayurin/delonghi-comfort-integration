"""On-demand, anonymized account diagnostics for De'Longhi Comfort."""

import logging
import re
from typing import Any

from homeassistant.components.diagnostics import REDACTED
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
_SENSITIVE_NAME = re.compile(
    r"password|passwd|secret|token|signature|authorization|credential|"
    r"dsn|serial|uuid|uid|email|username|user_id|device_id|"
    r"ssid|mac|address|latitude|longitude|location|url|uri|key|^id$|^name$",
    re.IGNORECASE,
)
_NUMERIC_STRING = re.compile(r"-?\d+(?:\.\d+)?")
_SAFE_STRING_PROPERTIES = frozenset(
    {
        "appliance_model",
        "hardware_version",
        "software_version",
        "firmware_version",
    }
)
_SAFE_MODEL = re.compile(r"[A-Za-z0-9_. -]{1,80}")


def _redact_value(
    value: Any, secrets: tuple[str, ...], *, allow_string: bool = False
) -> Any:
    """Keep numeric telemetry; redact unknown text instead of guessing its privacy."""
    if isinstance(value, dict):
        return {
            REDACTED if any(secret in str(key) for secret in secrets) else key: REDACTED
            if _SENSITIVE_NAME.search(str(key))
            else _redact_value(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, secrets) for item in value]
    if isinstance(value, str):
        if any(secret in value for secret in secrets):
            return REDACTED
        if _NUMERIC_STRING.fullmatch(value) or (
            allow_string and _SAFE_MODEL.fullmatch(value)
        ):
            return value
        return REDACTED if value else value
    return value


def _redact_properties(
    properties: list[dict[str, Any]], secrets: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Preserve the fixture name/value shape without exposing cloud metadata."""
    result = []
    for item in properties:
        prop = item["property"]
        name = prop["name"]
        private_name = any(secret in name for secret in secrets)
        result.append(
            {
                "property": {
                    "name": REDACTED if private_name else name,
                    "value": REDACTED
                    if private_name or _SENSITIVE_NAME.search(name)
                    else _redact_value(
                        prop["value"],
                        secrets,
                        allow_string=name in _SAFE_STRING_PROPERTIES,
                    ),
                }
            }
        )
    return result


async def _async_create_api(hass: HomeAssistant, entry: ConfigEntry) -> DeLonghiAPI:
    """Authenticate a diagnostic session without exposing account data."""
    api = DeLonghiAPI(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        async_get_clientsession(hass),
        entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
    )
    await api.authenticate()
    return api


async def _async_collect_devices(
    api: DeLonghiAPI, entry: ConfigEntry, devices: list[dict[str, Any]]
) -> dict[str, Any]:
    """Collect only the supplied devices using the same privacy rules."""
    secrets = tuple(
        value
        for value in (
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            api.access_token,
            api.refresh_token,
            *(item["device"]["dsn"] for item in devices),
        )
        if value
    )
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
                    key: _redact_value(device[key], secrets, allow_string=True)
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
            record["properties"] = _redact_properties(properties, secrets)
        diagnostics.append(record)
    return {"devices": diagnostics}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Fetch all account devices, including unsupported models, only on request."""
    api = await _async_create_api(hass, entry)
    return await _async_collect_devices(api, entry, await api.get_devices())


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
        entry,
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
