"""Offline account diagnostics and privacy regression tests."""

import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.exceptions import HomeAssistantError

from custom_components.delonghi_comfort.api import (
    DeLonghiAuthenticationError,
    DeLonghiConnectionError,
    DeLonghiProtocolError,
)
from custom_components.delonghi_comfort.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

MODULE = "custom_components.delonghi_comfort.diagnostics"


class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    """Fetch all models on demand without exposing credentials or identifiers."""

    def setUp(self):
        self.hass = MagicMock()
        self.entry = MagicMock()
        self.entry.data = {
            "username": "fixture@example.invalid",
            "password": "fixture-password",
            "language": "ja",
        }
        self.api = MagicMock()
        self.api.access_token = "fixture-access-token"
        self.api.refresh_token = "fixture-refresh-token"
        self.api.authenticate = AsyncMock()
        self.devices = [
            {
                "device": {
                    "dsn": "fixture-heater",
                    "oem_model": "DL-heater",
                    "product_name": "Private room",
                    "id": 123,
                }
            },
            {
                "device": {
                    "dsn": "fixture-other",
                    "oem_model": "DL-other",
                    "model": "AC-100",
                    "mac": "01:23:45:67:89:ab",
                }
            },
        ]
        self.api.get_devices = AsyncMock(return_value=self.devices)
        self.api.get_device_properties = AsyncMock(
            return_value=[
                {"property": {"name": "room_temp", "value": "20.5", "key": 999}},
            ]
        )
        patcher = patch(f"{MODULE}.DeLonghiAPI", return_value=self.api)
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch(f"{MODULE}.async_get_clientsession", return_value="session")
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_all_devices_including_unsupported_are_fetched_on_request(self):
        data = await async_get_config_entry_diagnostics(self.hass, self.entry)
        self.factory.assert_called_once_with(
            "fixture@example.invalid", "fixture-password", "session", "ja"
        )
        self.api.authenticate.assert_awaited_once()
        self.assertEqual(
            [call.args for call in self.api.get_device_properties.await_args_list],
            [("fixture-heater",), ("fixture-other",)],
        )
        self.assertEqual(
            [item["device"]["supported"] for item in data["devices"]], [True, False]
        )
        self.assertEqual(data["devices"][1]["device"]["model"], "AC-100")
        self.assertEqual(
            data["devices"][1]["properties"],
            [{"property": {"name": "room_temp", "value": "20.5"}}],
        )
        self.hass.config_entries.async_forward_entry_setups.assert_not_called()
        self.api.set_device_property.assert_not_called()

    async def test_sensitive_properties_nested_data_and_unknown_text_are_redacted(self):
        properties = [
            {"property": {"name": name, "value": value}}
            for name, value in (
                ("room_temp", 20.5),
                ("wifi_ssid", "Private network"),
                ("serial_number", 987654),
                ("access_token", "fixture-access-token"),
                ("future_text", "private-text-without-recognizable-format"),
                ("hardware_version", "1.2.3"),
                (
                    "future_data",
                    {
                        "id": 123,
                        "voltage": 220,
                        "samples": ["fixture-heater", "20.5", "Private room"],
                    },
                ),
                ("future_data_json", '{"password":"private"}'),
            )
        ]
        self.api.get_device_properties.return_value = properties
        data = await async_get_config_entry_diagnostics(self.hass, self.entry)
        values = {
            item["property"]["name"]: item["property"]["value"]
            for item in data["devices"][0]["properties"]
        }
        self.assertEqual(values["room_temp"], 20.5)
        self.assertEqual(values["hardware_version"], "1.2.3")
        for name in (
            "wifi_ssid",
            "serial_number",
            "access_token",
            "future_text",
            "future_data_json",
        ):
            self.assertEqual(values[name], REDACTED)
        self.assertEqual(
            values["future_data"],
            {"id": REDACTED, "voltage": 220, "samples": [REDACTED, "20.5", REDACTED]},
        )
        serialized = json.dumps(data)
        for secret in (
            *self.entry.data.values(),
            "fixture-heater",
            "fixture-other",
            "fixture-access-token",
            "fixture-refresh-token",
            "Private room",
            "Private network",
            "987654",
            "999",
        ):
            if secret == "ja":
                continue
            self.assertNotIn(str(secret), serialized)
        self.assertEqual(properties[1]["property"]["value"], "Private network")
        self.assertEqual(self.devices[0]["device"]["dsn"], "fixture-heater")

    async def test_individual_failures_are_explicit_and_other_devices_are_retained(
        self,
    ):
        for error, expected in (
            (DeLonghiConnectionError, "cannot_connect"),
            (DeLonghiProtocolError, "unexpected_response"),
        ):
            self.api.get_device_properties.side_effect = [
                error("private-error"),
                [],
            ]
            with self.assertLogs(MODULE, level="WARNING") as logs:
                data = await async_get_config_entry_diagnostics(self.hass, self.entry)
            self.assertEqual(data["devices"][0]["error"], expected)
            self.assertNotIn("properties", data["devices"][0])
            self.assertEqual(data["devices"][1]["properties"], [])
            self.assertNotIn("private-error", "\n".join(logs.output))
            self.assertNotIn("fixture-heater", "\n".join(logs.output))

    async def test_account_failure_and_expired_session_do_not_return_success(self):
        self.api.get_devices.side_effect = DeLonghiConnectionError(
            "Service unavailable"
        )
        with self.assertRaises(DeLonghiConnectionError):
            await async_get_config_entry_diagnostics(self.hass, self.entry)
        self.api.get_device_properties.assert_not_awaited()
        self.api.get_devices.side_effect = None
        self.api.get_device_properties.side_effect = DeLonghiAuthenticationError(
            "Expired"
        )
        with self.assertRaises(DeLonghiAuthenticationError):
            await async_get_config_entry_diagnostics(self.hass, self.entry)

    async def test_empty_account_has_an_explicit_empty_device_list(self):
        self.api.get_devices.return_value = []
        self.assertEqual(
            await async_get_config_entry_diagnostics(self.hass, self.entry),
            {"devices": []},
        )
        self.api.get_device_properties.assert_not_awaited()

    async def test_device_diagnostics_never_downloads_account_list_or_other_properties(
        self,
    ):
        device = MagicMock()
        device.identifiers = {("delonghi_comfort", "fixture-heater")}
        device.model = "MDHAA15WIFI-BK"
        device.sw_version = "1.2.3"
        data = await async_get_device_diagnostics(self.hass, self.entry, device)
        self.api.get_devices.assert_not_awaited()
        self.api.get_device_properties.assert_awaited_once_with("fixture-heater")
        self.assertEqual(len(data["devices"]), 1)
        self.assertEqual(data["devices"][0]["device"]["model"], "MDHAA15WIFI-BK")
        self.assertNotIn("fixture-heater", json.dumps(data))
        self.assertEqual(
            data["devices"][0]["properties"],
            [{"property": {"name": "room_temp", "value": "20.5"}}],
        )

    async def test_device_diagnostics_rejects_missing_or_ambiguous_identifiers(self):
        device = MagicMock()
        for identifiers in (
            set(),
            {("other", "fixture-heater")},
            {("delonghi_comfort", "first"), ("delonghi_comfort", "second")},
        ):
            device.identifiers = identifiers
            with self.assertRaises(HomeAssistantError):
                await async_get_device_diagnostics(self.hass, self.entry, device)
        self.api.authenticate.assert_not_awaited()
        self.api.get_devices.assert_not_awaited()
        self.api.get_device_properties.assert_not_awaited()


class TranslationTests(unittest.TestCase):
    """Keep complete Japanese translations in sync with the active English keys."""

    def test_japanese_translation_has_exactly_the_english_keys(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "custom_components/delonghi_comfort/translations"
        )
        english = json.loads((root / "en.json").read_text())
        japanese = json.loads((root / "ja.json").read_text())

        def check_keys(left, right):
            self.assertEqual(set(left), set(right))
            for key, value in left.items():
                if isinstance(value, dict):
                    check_keys(value, right[key])
                else:
                    self.assertIsInstance(right[key], str)
                    self.assertTrue(right[key])

        check_keys(english, japanese)
