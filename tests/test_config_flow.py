"""Offline tests for account validation, options and reauthentication."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.delonghi_comfort.api import (
    DeLonghiAuthenticationError,
    DeLonghiConnectionError,
    DeLonghiProtocolError,
)
from custom_components.delonghi_comfort.config_flow import (
    DelonghiComfortConfigFlow,
    DelonghiComfortOptionsFlow,
)

FLOW_MODULE = "custom_components.delonghi_comfort.config_flow"
ACCOUNT = {
    "username": "test@example.invalid",
    "password": "test-password",
    "language": "ja",
}
DEVICES = [{"device": {"dsn": "test-dsn", "oem_model": "DL-heater"}}]


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    """Preserve account IDs while surfacing categorized failures."""

    def setUp(self):
        self.flow = DelonghiComfortConfigFlow()
        self.flow.hass = MagicMock()
        self.flow.async_set_unique_id = AsyncMock()
        self.flow._abort_if_unique_id_configured = MagicMock()
        self.api = MagicMock()
        self.api.authenticate = AsyncMock(return_value=True)
        self.api.get_devices = AsyncMock(return_value=DEVICES)
        self.api_patch = patch(f"{FLOW_MODULE}.DeLonghiAPI", return_value=self.api)
        self.api_patch.start()
        self.addCleanup(self.api_patch.stop)
        self.session_patch = patch(f"{FLOW_MODULE}.async_get_clientsession")
        self.session_patch.start()
        self.addCleanup(self.session_patch.stop)

    async def test_user_entry_keeps_existing_username_id(self):
        result = await self.flow.async_step_user(ACCOUNT)
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"], ACCOUNT)
        self.flow.async_set_unique_id.assert_awaited_once_with(ACCOUNT["username"])

    async def test_user_failure_classification(self):
        for exception, error in (
            (DeLonghiAuthenticationError, "invalid_auth"),
            (DeLonghiConnectionError, "cannot_connect"),
            (DeLonghiProtocolError, "unexpected_response"),
        ):
            with self.subTest(error=error):
                self.api.authenticate.side_effect = exception("sanitized")
                result = await self.flow.async_step_user(ACCOUNT)
                self.assertEqual(result["errors"], {"base": error})

    async def test_empty_and_unsupported_accounts(self):
        for devices, error in (
            ([], "no_devices"),
            ([{"device": {"oem_model": "unknown"}}], "unsupported_devices"),
            ([{"device": {}}], "unsupported_devices"),
        ):
            self.api.get_devices.return_value = devices
            result = await self.flow.async_step_user(ACCOUNT)
            self.assertEqual(result["errors"], {"base": error})

    async def test_reauthentication_reloads_same_entry_and_preserves_data(self):
        entry = MagicMock()
        entry.data = {**ACCOUNT, "preserved": "existing"}
        self.flow._get_reauth_entry = MagicMock(return_value=entry)
        self.flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": "abort", "reason": "reauth_successful"}
        )
        form = await self.flow.async_step_reauth(entry.data)
        self.assertEqual(form["step_id"], "reauth_confirm")
        result = await self.flow.async_step_reauth_confirm({"password": "new-password"})
        self.assertEqual(result["reason"], "reauth_successful")
        self.flow.async_update_reload_and_abort.assert_called_once_with(
            entry, data_updates={**entry.data, "password": "new-password"}
        )
        self.flow.async_set_unique_id.assert_not_awaited()

    async def test_failed_reauthentication_does_not_update_entry(self):
        entry = MagicMock()
        entry.data = ACCOUNT.copy()
        self.flow._get_reauth_entry = MagicMock(return_value=entry)
        self.flow.async_update_reload_and_abort = MagicMock()
        self.api.authenticate.side_effect = DeLonghiAuthenticationError("sanitized")
        result = await self.flow.async_step_reauth_confirm({"password": "wrong"})
        self.assertEqual(result["errors"]["base"], "invalid_auth")
        self.assertEqual(entry.data, ACCOUNT)
        self.flow.async_update_reload_and_abort.assert_not_called()


class OptionsFlowTests(unittest.IsolatedAsyncioTestCase):
    """Validate defaults and bounds using the current HA options-flow API."""

    def setUp(self):
        self.flow = DelonghiComfortOptionsFlow()
        self.flow.hass = MagicMock()
        self.flow.handler = "test-entry"
        entry = MagicMock()
        entry.options = {}
        self.flow.hass.config_entries.async_get_known_entry.return_value = entry

    async def test_default_and_allowed_scan_intervals(self):
        result = await self.flow.async_step_init()
        self.assertEqual(result["data_schema"]({})["scan_interval"], 5)
        for value in (5, 15, 300):
            result = await self.flow.async_step_init({"scan_interval": value})
            self.assertEqual(result["data"], {"scan_interval": value})

    async def test_invalid_scan_intervals_do_not_create_options(self):
        for value in (4, 301, "invalid"):
            result = await self.flow.async_step_init({"scan_interval": value})
            self.assertEqual(result["errors"]["base"], "invalid_scan_interval")
