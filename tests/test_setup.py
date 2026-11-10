"""Offline tests for supported models, setup retries and coordinator failures."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.delonghi_comfort import async_setup_entry, async_unload_entry
from custom_components.delonghi_comfort.api import (
    DeLonghiAuthenticationError,
    DeLonghiConnectionError,
)
from custom_components.delonghi_comfort.coordinator import DeLonghiCoordinator

MODULE = "custom_components.delonghi_comfort"


class SetupTests(unittest.IsolatedAsyncioTestCase):
    """Use only allowlisted heaters and preserve the entry lifecycle."""

    def setUp(self):
        self.hass = MagicMock()
        self.hass.data = {}
        self.hass.config_entries.async_forward_entry_setups = AsyncMock()
        self.entry = MagicMock()
        self.entry.entry_id = "test-entry"
        self.entry.data = {"username": "test@example.invalid", "password": "test-password"}
        self.api = MagicMock()
        self.api.authenticate = AsyncMock(return_value=True)
        self.api.get_devices = AsyncMock()
        self.coordinator = MagicMock()
        self.coordinator.async_config_entry_first_refresh = AsyncMock()
        for target, result in (
            ("DeLonghiAPI", self.api),
            ("async_get_clientsession", MagicMock()),
            ("DeLonghiCoordinator", self.coordinator),
        ):
            patcher = patch(f"{MODULE}.{target}", return_value=result)
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_mixed_account_initializes_only_heater(self):
        heater = {"device": {"dsn": "test-heater", "oem_model": "DL-heater"}}
        self.api.get_devices.return_value = [
            heater, {"device": {"dsn": "test-unknown", "oem_model": "unknown"}}
        ]
        with self.assertLogs(MODULE, level="WARNING") as logs:
            self.assertTrue(await async_setup_entry(self.hass, self.entry))
        self.assertNotIn("test-unknown", "\n".join(logs.output))
        data = self.hass.data["delonghi_comfort"]["test-entry"]
        self.assertEqual(set(data), {"heater_coordinators"})
        self.assertEqual(data["heater_coordinators"], [self.coordinator])
        self.coordinator.async_config_entry_first_refresh.assert_awaited_once()

    async def test_unknown_only_account_creates_no_entities(self):
        self.api.get_devices.return_value = [{"device": {"dsn": "unknown"}}]
        with self.assertLogs(MODULE, level="WARNING"):
            with self.assertRaises(ConfigEntryError):
                await async_setup_entry(self.hass, self.entry)
        self.hass.config_entries.async_forward_entry_setups.assert_not_awaited()
        self.coordinator.async_config_entry_first_refresh.assert_not_awaited()
        self.assertEqual(self.hass.data, {})

    async def test_auth_failure_and_outage_have_distinct_ha_errors(self):
        for error, expected in (
            (DeLonghiAuthenticationError, ConfigEntryAuthFailed),
            (DeLonghiConnectionError, ConfigEntryNotReady),
        ):
            self.api.authenticate.side_effect = error("sanitized")
            with self.assertRaises(expected):
                await async_setup_entry(self.hass, self.entry)

    async def test_empty_devices_retry_instead_of_succeeding(self):
        self.api.get_devices.return_value = []
        with self.assertRaises(ConfigEntryNotReady):
            await async_setup_entry(self.hass, self.entry)

    async def test_failed_platform_unload_keeps_entry_data(self):
        self.hass.data = {"delonghi_comfort": {"test-entry": {"preserved": True}}}
        self.hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
        self.assertFalse(await async_unload_entry(self.hass, self.entry))
        self.assertIn("test-entry", self.hass.data["delonghi_comfort"])
        self.hass.config_entries.async_unload_platforms.return_value = True
        self.assertTrue(await async_unload_entry(self.hass, self.entry))
        self.assertNotIn("test-entry", self.hass.data["delonghi_comfort"])


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    """Check polling error mapping without connecting to a device."""

    async def test_properties_and_failure_classification(self):
        coordinator = MagicMock()
        coordinator.api.get_device_properties = AsyncMock(
            return_value=[
                {"property": {"name": "room_temp", "value": 20.5}},
                {"property": {"name": "future_property", "value": "unknown"}},
            ]
        )
        data = await DeLonghiCoordinator._async_update_data(coordinator)
        self.assertEqual(data, {"room_temp": 20.5, "future_property": "unknown"})
        coordinator.api.get_device_properties.return_value = []
        with self.assertRaises(UpdateFailed):
            await DeLonghiCoordinator._async_update_data(coordinator)
        for error, expected in (
            (DeLonghiAuthenticationError, ConfigEntryAuthFailed),
            (DeLonghiConnectionError, UpdateFailed),
        ):
            coordinator.api.get_device_properties.side_effect = error("sanitized")
            with self.assertRaises(expected):
                await DeLonghiCoordinator._async_update_data(coordinator)
