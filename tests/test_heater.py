"""Synthetic heater telemetry tests; these are not captured hardware fixtures."""

import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.delonghi_comfort import climate, select, sensor, switch
from custom_components.delonghi_comfort.api import DeLonghiConnectionError
from custom_components.delonghi_comfort.climate import DeLonghiHeater
from custom_components.delonghi_comfort.coordinator import (
    DeLonghiCoordinator,
    indexed_value,
    numeric_value,
)
from custom_components.delonghi_comfort.select import HeaterBrightness
from custom_components.delonghi_comfort.sensor import HeaterTemperature
from custom_components.delonghi_comfort.switch import HEATER_DESCRIPTIONS, HeaterSwitch


class HeaterTests(unittest.IsolatedAsyncioTestCase):
    """Keep heater IDs and commands stable while accepting unknown telemetry."""

    def setUp(self):
        properties = json.loads(
            (Path(__file__).parent / "fixtures/heater_properties.json").read_text()
        )
        self.coordinator = MagicMock()
        self.coordinator.dsn = "test-dsn"
        self.coordinator.data = {
            item["property"]["name"]: item["property"]["value"] for item in properties
        }
        self.coordinator.last_update_success = True
        self.coordinator.get_device_info.return_value = {
            "identifiers": {("delonghi_comfort", "test-dsn")},
            "manufacturer": "De'Longhi",
        }
        self.coordinator.api.set_device_property = AsyncMock(return_value=True)
        self.coordinator.async_request_refresh = AsyncMock()
        self.coordinator.async_set_property = lambda name, value: (
            DeLonghiCoordinator.async_set_property(self.coordinator, name, value)
        )
        self.climate = DeLonghiHeater(self.coordinator)
        self.brightness = HeaterBrightness(self.coordinator)
        self.temperature = HeaterTemperature(self.coordinator)
        self.switches = [
            HeaterSwitch(self.coordinator, description)
            for description in HEATER_DESCRIPTIONS
        ]

    async def test_fixture_values_and_existing_unique_ids(self):
        self.assertEqual(self.climate.unique_id, "delonghi_heater_test-dsn")
        self.assertEqual(self.brightness.unique_id, "delonghi_heater_test-dsn_brightness")
        self.assertEqual(self.temperature.unique_id, "delonghi_heater_test-dsn_temperature")
        self.assertEqual(
            [entity.unique_id for entity in self.switches],
            ["delonghi_heater_test-dsn_eco", "delonghi_heater_test-dsn_lock"],
        )
        self.assertEqual(self.climate.hvac_mode, HVACMode.HEAT)
        self.assertEqual(self.climate.hvac_action, HVACAction.HEATING)
        self.assertEqual(self.climate.preset_mode, "manual")
        self.assertEqual(self.climate.fan_mode, "40")
        self.assertEqual(self.climate.native_current_temperature, 20.5)
        self.assertEqual(self.climate.native_target_temperature, 21)
        self.assertEqual(self.brightness.current_option, "Level 2")
        self.assertEqual(self.temperature.native_value, 20.5)
        self.assertTrue(self.switches[0].is_on)
        self.assertFalse(self.switches[1].is_on)
        self.assertIsNone(self.climate.extra_state_attributes)

    async def test_platform_setup_creates_only_heater_entities(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test-entry"
        hass.data = {
            "delonghi_comfort": {
                entry.entry_id: {"heater_coordinators": [self.coordinator]}
            }
        }
        for platform, expected in (
            (climate, [DeLonghiHeater]),
            (sensor, [HeaterTemperature]),
            (select, [HeaterBrightness]),
            (switch, [HeaterSwitch, HeaterSwitch]),
        ):
            with self.subTest(platform=platform.__name__):
                entities = []
                await platform.async_setup_entry(hass, entry, entities.extend)
                self.assertEqual([type(entity) for entity in entities], expected)
                self.assertTrue(
                    all(entity.coordinator is self.coordinator for entity in entities)
                )
                hass.data["delonghi_comfort"][entry.entry_id]["heater_coordinators"] = []
                empty_entities = []
                await platform.async_setup_entry(hass, entry, empty_entities.extend)
                self.assertEqual(empty_entities, [])
                hass.data["delonghi_comfort"][entry.entry_id]["heater_coordinators"] = [
                    self.coordinator
                ]

    async def test_heater_uses_class_defaults_and_json_icon(self):
        root = Path(__file__).resolve().parents[1] / "custom_components/delonghi_comfort"
        icons = json.loads((root / "icons.json").read_text())
        self.assertIsNone(self.climate.icon)
        self.assertEqual(
            icons["entity"]["climate"][self.climate.translation_key]["default"],
            "mdi:radiator",
        )
        for attribute in (
            "_attr_supported_features", "_attr_has_entity_name", "_attr_name",
            "_attr_translation_key", "_attr_fan_modes", "_attr_hvac_modes",
            "_attr_max_temp", "_attr_min_temp", "_attr_preset_modes",
            "_attr_target_temperature_step", "_attr_native_temperature_unit",
        ):
            self.assertIn(attribute, DeLonghiHeater.__dict__)
            self.assertNotIn(attribute, vars(self.climate))

    async def test_missing_and_unknown_values_do_not_crash_or_invent_state(self):
        for value in (None, -1, 999, 1.5, "invalid", [], {}, True, float("nan")):
            with self.subTest(value=value):
                self.coordinator.data = {
                    key: value
                    for key in ("device_mode", "current_power_level", "current_brightness")
                }
                self.assertIsNone(self.climate.preset_mode)
                self.assertIsNone(self.climate.fan_mode)
                self.assertIsNone(self.brightness.current_option)
        self.coordinator.data = {}
        self.assertIsNone(self.climate.hvac_mode)
        self.assertIsNone(self.climate.hvac_action)
        self.assertIsNone(self.climate.native_current_temperature)
        self.assertIsNone(self.climate.native_target_temperature)
        self.assertIsNone(self.temperature.native_value)
        self.assertIsNone(self.switches[0].is_on)
        self.coordinator.last_update_success = False
        self.assertFalse(self.climate.available)
        self.assertFalse(self.temperature.available)

    async def test_numeric_strings_and_known_statuses(self):
        self.coordinator.data = {
            "device_status": "1",
            "MDH_Resources": "0",
            "device_mode": "2",
            "room_temp": "19.5",
            "current_power_level": "5",
            "current_brightness": "3",
            "get_eco": "0",
        }
        self.assertEqual(self.climate.hvac_mode, HVACMode.HEAT)
        self.assertEqual(self.climate.hvac_action, HVACAction.IDLE)
        self.assertEqual(self.climate.preset_mode, "night_mode")
        self.assertEqual(self.climate.fan_mode, "100")
        self.assertEqual(self.climate.native_current_temperature, 19.5)
        self.assertEqual(self.brightness.current_option, "Level 3")
        self.assertFalse(self.switches[0].is_on)
        self.coordinator.data["device_status"] = 2
        self.assertEqual(self.climate.hvac_mode, HVACMode.OFF)
        self.assertEqual(self.climate.hvac_action, HVACAction.OFF)

    async def test_commands_keep_existing_property_names_and_values(self):
        commands = (
            (self.climate.async_turn_on, (), {}, "set_status", 1),
            (self.climate.async_turn_off, (), {}, "set_status", 2),
            (self.climate.async_set_hvac_mode, (HVACMode.HEAT,), {}, "set_status", 1),
            (self.climate.async_set_preset_mode, ("antifrost",), {}, "set_device_mode", 3),
            (self.climate.async_set_fan_mode, ("60",), {}, "set_power_level", 3),
            (self.climate.async_set_temperature, (), {"temperature": 21.5}, "temperature_setpoint", 21.5),
            (self.brightness.async_select_option, ("Level 3",), {}, "set_brightness", 3),
            (self.switches[0].async_turn_on, (), {}, "set_eco", 1),
            (self.switches[1].async_turn_off, (), {}, "set_lock", 0),
        )
        for command, args, kwargs, name, value in commands:
            with self.subTest(name=name, value=value):
                await command(*args, **kwargs)
                self.coordinator.api.set_device_property.assert_awaited_with(
                    "test-dsn", name, value
                )
        self.assertEqual(self.coordinator.async_request_refresh.await_count, len(commands))

    async def test_all_mode_values_icons_labels_and_device_commands(self):
        root = Path(__file__).resolve().parents[1] / "custom_components/delonghi_comfort"
        icons = json.loads((root / "icons.json").read_text())
        translations = json.loads((root / "translations/en.json").read_text())
        icon_attributes = icons["entity"]["climate"]["heater"]["state_attributes"]
        labels = translations["entity"]["climate"]["heater"]["state_attributes"]
        cases = (
            ("preset_mode", "preset_modes", "device_mode", "set_device_mode", 1,
             self.climate.async_set_preset_mode, (
                 ("day_mode", "Day mode", "mdi:weather-sunny"),
                 ("night_mode", "Night mode", "mdi:weather-night"),
                 ("antifrost", "Antifrost", "mdi:snowflake-thermometer"),
                 ("manual", "Manual", "mdi:hand-front-left"),
             )),
            ("fan_mode", "fan_modes", "current_power_level", "set_power_level", 0,
             self.climate.async_set_fan_mode, (
                 ("0", "0%", "mdi:lightbulb-off"),
                 ("20", "20%", "mdi:lightbulb-on-20"),
                 ("40", "40%", "mdi:lightbulb-on-40"),
                 ("60", "60%", "mdi:lightbulb-on-60"),
                 ("80", "80%", "mdi:lightbulb-on-80"),
                 ("100", "100%", "mdi:lightbulb-on"),
             )),
        )
        for attribute, modes, telemetry, command, offset, setter, entries in cases:
            self.assertEqual(getattr(self.climate, modes), [key for key, _, _ in entries])
            self.assertEqual(icon_attributes[attribute]["state"],
                             {key: icon for key, _, icon in entries})
            self.assertEqual(labels[attribute]["state"],
                             {key: label for key, label, _ in entries})
            for index, (key, _, _) in enumerate(entries, start=offset):
                with self.subTest(attribute=attribute, key=key):
                    self.coordinator.data[telemetry] = index
                    self.assertEqual(getattr(self.climate, attribute), key)
                    await setter(key)
                    self.coordinator.api.set_device_property.assert_awaited_with(
                        "test-dsn", command, index
                    )

    async def test_invalid_commands_never_reach_device(self):
        commands = (
            (self.climate.async_set_hvac_mode, (HVACMode.COOL,), {}),
            (self.climate.async_set_preset_mode, ("unknown",), {}),
            (self.climate.async_set_fan_mode, ("unknown",), {}),
            (self.climate.async_set_preset_mode, ("Day mode",), {}),
            (self.climate.async_set_fan_mode, ("20%",), {}),
            (self.brightness.async_select_option, ("unknown",), {}),
            *((self.climate.async_set_temperature, (), {"temperature": value})
              for value in (None, 9.5, 28.5, 20.25, float("nan"), True)),
        )
        for command, args, kwargs in commands:
            with self.assertRaises(ServiceValidationError):
                await command(*args, **kwargs)
        self.coordinator.api.set_device_property.assert_not_awaited()

    async def test_command_errors_are_visible_and_do_not_refresh_as_success(self):
        self.coordinator.api.set_device_property.side_effect = DeLonghiConnectionError(
            "Service unavailable"
        )
        for command in (
            self.climate.async_turn_on,
            self.switches[0].async_turn_on,
        ):
            with self.assertRaises(HomeAssistantError):
                await command()
        with self.assertRaises(HomeAssistantError):
            await self.brightness.async_select_option("Level 1")
        self.coordinator.api.set_device_property.side_effect = None
        self.coordinator.api.set_device_property.return_value = False
        with self.assertRaises(HomeAssistantError):
            await self.climate.async_turn_off()
        self.coordinator.async_request_refresh.assert_not_awaited()


class TelemetryTests(unittest.TestCase):
    """Reject nonnumeric and nonfinite telemetry."""

    def test_numeric_values(self):
        for value in (None, True, [], {}, "unknown", "nan", "inf", float("inf")):
            self.assertIsNone(numeric_value(value))
        self.assertEqual(numeric_value("20.5"), 20.5)
        self.assertEqual(indexed_value("1", ["one", "two"], 1), "one")
        self.assertIsNone(indexed_value(0, ["one", "two"], 1))
