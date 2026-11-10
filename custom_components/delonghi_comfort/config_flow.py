"""Configuration and reauthentication for De'Longhi Comfort."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    DeLonghiAPI,
    DeLonghiAuthenticationError,
    DeLonghiConnectionError,
    DeLonghiProtocolError,
)
from .const import (
    CONF_LANGUAGE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_LANGUAGE,
    DOMAIN,
    LANGUAGES,
    SCAN_INTERVAL,
    SUPPORTED_MODELS,
)


class DelonghiComfortConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure an account without changing its existing unique ID."""

    VERSION = 1

    async def _validate_account(self, data: dict[str, Any]) -> str | None:
        api = DeLonghiAPI(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            async_get_clientsession(self.hass),
            data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
        )
        try:
            await api.authenticate()
            devices = await api.get_devices()
        except DeLonghiAuthenticationError:
            return "invalid_auth"
        except DeLonghiConnectionError:
            return "cannot_connect"
        except DeLonghiProtocolError:
            return "unexpected_response"
        if not devices:
            return "no_devices"
        if not any(device["device"].get("oem_model") in SUPPORTED_MODELS for device in devices):
            return "unsupported_devices"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create an entry after validating account access and supported devices."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            if error := await self._validate_account(user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"De'Longhi Comfort ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(
                        list(LANGUAGES)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Ask for new credentials without creating another entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Replace only the password of the account being reauthenticated."""
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            if error := await self._validate_account(data):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return DelonghiComfortOptionsFlow()


class DelonghiComfortOptionsFlow(config_entries.OptionsFlow):
    """Change polling options without storing account credentials in options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the polling interval."""
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
            }
        )
        errors = {}
        if user_input is not None:
            try:
                options = schema(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_scan_interval"
            else:
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
