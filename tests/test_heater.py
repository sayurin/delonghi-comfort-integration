"""Synthetic and sanitized hardware-derived heater telemetry tests."""

import json
from pathlib import Path

import pytest
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


@pytest.fixture
def heater(mocker):
    properties = json.loads(
        (Path(__file__).parent / "fixtures/heater_properties.json").read_text()
    )
    coordinator = mocker.MagicMock()
    coordinator.dsn = "test-dsn"
    coordinator.data = {
        item["property"]["name"]: item["property"]["value"] for item in properties
    }
    coordinator.last_update_success = True
    coordinator.get_device_info.return_value = {
        "identifiers": {("delonghi_comfort", "test-dsn")},
        "manufacturer": "De'Longhi",
    }
    coordinator.api.set_device_property = mocker.AsyncMock(return_value=True)
    coordinator.async_request_refresh = mocker.AsyncMock()
    coordinator.async_set_property = lambda name, value: (
        DeLonghiCoordinator.async_set_property(coordinator, name, value)
    )
    return (
        coordinator,
        DeLonghiHeater(coordinator),
        HeaterBrightness(coordinator),
        HeaterTemperature(coordinator),
        [HeaterSwitch(coordinator, description) for description in HEATER_DESCRIPTIONS],
    )


async def test_fixture_values_and_existing_unique_ids(heater):
    _coordinator, climate_entity, brightness, temperature, switches = heater
    assert climate_entity.unique_id == "delonghi_heater_test-dsn"
    assert brightness.unique_id == "delonghi_heater_test-dsn_brightness"
    assert temperature.unique_id == "delonghi_heater_test-dsn_temperature"
    assert [entity.unique_id for entity in switches] == [
        "delonghi_heater_test-dsn_eco",
        "delonghi_heater_test-dsn_lock",
    ]
    assert climate_entity.hvac_mode == HVACMode.HEAT
    assert climate_entity.hvac_action == HVACAction.HEATING
    assert climate_entity.preset_mode == "manual"
    assert climate_entity.fan_mode == "40"
    assert climate_entity.native_current_temperature == 20.5
    assert climate_entity.native_target_temperature == 21
    assert brightness.current_option == "Level 2"
    assert temperature.native_value == 20.5
    assert switches[0].is_on
    assert not switches[1].is_on
    assert climate_entity.extra_state_attributes is None


@pytest.mark.parametrize(
    ("filename", "model", "temperature", "target", "preset", "power", "action"),
    (
        (
            "mdh_wifi_properties.json",
            "MDH Wifi",
            21,
            20.0,
            "night_mode",
            "20",
            HVACAction.IDLE,
        ),
        (
            "mdh15_wifi_properties.json",
            "MDH15 Wifi",
            23,
            24.0,
            "day_mode",
            "100",
            HVACAction.HEATING,
        ),
    ),
)
async def test_hardware_derived_model_fixtures(
    heater,
    mocker,
    filename,
    model,
    temperature,
    target,
    preset,
    power,
    action,
):
    coordinator, climate_entity, brightness, _temperature, switches = heater
    properties = json.loads((Path(__file__).parent / "fixtures" / filename).read_text())
    assert len(properties) == 32
    coordinator.api.get_device_properties = mocker.AsyncMock(return_value=properties)
    coordinator.data = await DeLonghiCoordinator._async_update_data(coordinator)

    assert coordinator.data["appliance_model"] == model
    assert coordinator.data["serial_number"] == "DUMMY__DUMMY"
    assert coordinator.data["set_temp_unit"] is None
    assert climate_entity.native_current_temperature == temperature
    assert climate_entity.native_target_temperature == target
    assert climate_entity.preset_mode == preset
    assert climate_entity.fan_mode == power
    assert climate_entity.hvac_action == action
    assert coordinator.data["set_power_level"] == 5
    assert not switches[0].is_on
    assert not switches[1].is_on
    assert brightness.current_option == "Level 1"
    info = DeLonghiCoordinator.get_device_info(coordinator)
    assert info["model"] == model
    assert info["hw_version"] == coordinator.data["hardware_version"]


async def test_half_degree_setpoints_cover_full_supported_range(heater):
    coordinator, climate_entity, _brightness, _temperature, _switches = heater

    for half_degrees in range(20, 57):
        temperature = half_degrees / 2
        await climate_entity.async_set_temperature(temperature=temperature)
        coordinator.api.set_device_property.assert_awaited_with(
            "test-dsn", "temperature_setpoint", temperature
        )

    assert coordinator.async_request_refresh.await_count == 37


@pytest.mark.parametrize(
    ("platform", "expected"),
    (
        (climate, [DeLonghiHeater]),
        (sensor, [HeaterTemperature]),
        (select, [HeaterBrightness]),
        (switch, [HeaterSwitch, HeaterSwitch]),
    ),
)
async def test_platform_setup_creates_only_heater_entities(
    heater,
    mocker,
    platform,
    expected,
):
    coordinator, _climate, _brightness, _temperature, _switches = heater
    hass = mocker.MagicMock()
    entry = mocker.MagicMock()
    entry.entry_id = "test-entry"
    hass.data = {
        "delonghi_comfort": {entry.entry_id: {"heater_coordinators": [coordinator]}}
    }

    entities = []
    await platform.async_setup_entry(hass, entry, entities.extend)
    assert [type(entity) for entity in entities] == expected
    assert all(entity.coordinator is coordinator for entity in entities)

    hass.data["delonghi_comfort"][entry.entry_id]["heater_coordinators"] = []
    empty_entities = []
    await platform.async_setup_entry(hass, entry, empty_entities.extend)
    assert empty_entities == []


def test_heater_uses_class_defaults_and_json_icon(heater):
    _coordinator, climate_entity, _brightness, _temperature, _switches = heater
    root = Path(__file__).resolve().parents[1] / "custom_components/delonghi_comfort"
    icons = json.loads((root / "icons.json").read_text())

    assert climate_entity.icon is None
    assert (
        icons["entity"]["climate"][climate_entity.translation_key]["default"]
        == "mdi:radiator"
    )
    for attribute in (
        "_attr_supported_features",
        "_attr_has_entity_name",
        "_attr_name",
        "_attr_translation_key",
        "_attr_fan_modes",
        "_attr_hvac_modes",
        "_attr_max_temp",
        "_attr_min_temp",
        "_attr_preset_modes",
        "_attr_target_temperature_step",
        "_attr_native_temperature_unit",
    ):
        assert attribute in DeLonghiHeater.__dict__
        assert attribute not in vars(climate_entity)


def test_missing_and_unknown_values_do_not_crash_or_invent_state(heater):
    coordinator, climate_entity, brightness, temperature, switches = heater
    for value in (None, -1, 999, 1.5, "invalid", [], {}, True, float("nan")):
        coordinator.data = {
            key: value
            for key in ("device_mode", "current_power_level", "current_brightness")
        }
        assert climate_entity.preset_mode is None
        assert climate_entity.fan_mode is None
        assert brightness.current_option is None

    coordinator.data = {}
    assert climate_entity.hvac_mode is None
    assert climate_entity.hvac_action is None
    assert climate_entity.native_current_temperature is None
    assert climate_entity.native_target_temperature is None
    assert temperature.native_value is None
    assert switches[0].is_on is None
    coordinator.last_update_success = False
    assert not climate_entity.available
    assert not temperature.available


def test_numeric_strings_and_known_statuses(heater):
    coordinator, climate_entity, brightness, _temperature, switches = heater
    coordinator.data = {
        "device_status": "1",
        "MDH_Resources": "0",
        "device_mode": "2",
        "room_temp": "19.5",
        "current_power_level": "5",
        "current_brightness": "3",
        "get_eco": "0",
    }

    assert climate_entity.hvac_mode == HVACMode.HEAT
    assert climate_entity.hvac_action == HVACAction.IDLE
    assert climate_entity.preset_mode == "night_mode"
    assert climate_entity.fan_mode == "100"
    assert climate_entity.native_current_temperature == 19.5
    assert brightness.current_option == "Level 3"
    assert not switches[0].is_on
    coordinator.data["device_status"] = 2
    assert climate_entity.hvac_mode == HVACMode.OFF
    assert climate_entity.hvac_action == HVACAction.OFF


async def test_commands_keep_existing_property_names_and_values(heater):
    coordinator, climate_entity, brightness, _temperature, switches = heater
    commands = (
        (climate_entity.async_turn_on, (), {}, "set_status", 1),
        (climate_entity.async_turn_off, (), {}, "set_status", 2),
        (climate_entity.async_set_hvac_mode, (HVACMode.HEAT,), {}, "set_status", 1),
        (
            climate_entity.async_set_preset_mode,
            ("antifrost",),
            {},
            "set_device_mode",
            3,
        ),
        (climate_entity.async_set_fan_mode, ("60",), {}, "set_power_level", 3),
        (
            climate_entity.async_set_temperature,
            (),
            {"temperature": 21.5},
            "temperature_setpoint",
            21.5,
        ),
        (
            brightness.async_select_option,
            ("Level 3",),
            {},
            "set_brightness",
            3,
        ),
        (switches[0].async_turn_on, (), {}, "set_eco", 1),
        (switches[1].async_turn_off, (), {}, "set_lock", 0),
    )

    for command, args, kwargs, name, value in commands:
        await command(*args, **kwargs)
        coordinator.api.set_device_property.assert_awaited_with("test-dsn", name, value)

    assert coordinator.async_request_refresh.await_count == len(commands)


async def test_all_mode_values_icons_labels_and_device_commands(heater):
    coordinator, climate_entity, _brightness, _temperature, _switches = heater
    root = Path(__file__).resolve().parents[1] / "custom_components/delonghi_comfort"
    icons = json.loads((root / "icons.json").read_text())
    translations = json.loads((root / "translations/en.json").read_text())
    icon_attributes = icons["entity"]["climate"]["heater"]["state_attributes"]
    labels = translations["entity"]["climate"]["heater"]["state_attributes"]
    cases = (
        (
            "preset_mode",
            "preset_modes",
            "device_mode",
            "set_device_mode",
            1,
            climate_entity.async_set_preset_mode,
            (
                ("day_mode", "Day mode", "mdi:weather-sunny"),
                ("night_mode", "Night mode", "mdi:weather-night"),
                ("antifrost", "Antifrost", "mdi:snowflake-thermometer"),
                ("manual", "Manual", "mdi:hand-front-left"),
            ),
        ),
        (
            "fan_mode",
            "fan_modes",
            "current_power_level",
            "set_power_level",
            0,
            climate_entity.async_set_fan_mode,
            (
                ("0", "0%", "mdi:lightbulb-off"),
                ("20", "20%", "mdi:lightbulb-on-20"),
                ("40", "40%", "mdi:lightbulb-on-40"),
                ("60", "60%", "mdi:lightbulb-on-60"),
                ("80", "80%", "mdi:lightbulb-on-80"),
                ("100", "100%", "mdi:lightbulb-on"),
            ),
        ),
    )

    for attribute, modes, telemetry, command, offset, setter, entries in cases:
        assert getattr(climate_entity, modes) == [key for key, _, _ in entries]
        assert icon_attributes[attribute]["state"] == {
            key: icon for key, _, icon in entries
        }
        assert labels[attribute]["state"] == {key: label for key, label, _ in entries}
        for index, (key, _, _) in enumerate(entries, start=offset):
            coordinator.data[telemetry] = index
            assert getattr(climate_entity, attribute) == key
            await setter(key)
            coordinator.api.set_device_property.assert_awaited_with(
                "test-dsn", command, index
            )


@pytest.mark.parametrize(
    ("method", "args", "kwargs"),
    (
        ("hvac", (HVACMode.COOL,), {}),
        ("preset", ("unknown",), {}),
        ("fan", ("unknown",), {}),
        ("preset", ("Day mode",), {}),
        ("fan", ("20%",), {}),
        ("brightness", ("unknown",), {}),
        ("temperature", (), {"temperature": None}),
        ("temperature", (), {"temperature": 9.5}),
        ("temperature", (), {"temperature": 28.5}),
        ("temperature", (), {"temperature": 20.25}),
        ("temperature", (), {"temperature": float("nan")}),
        ("temperature", (), {"temperature": True}),
    ),
)
async def test_invalid_commands_never_reach_device(heater, method, args, kwargs):
    coordinator, climate_entity, brightness, _temperature, _switches = heater
    commands = {
        "hvac": climate_entity.async_set_hvac_mode,
        "preset": climate_entity.async_set_preset_mode,
        "fan": climate_entity.async_set_fan_mode,
        "brightness": brightness.async_select_option,
        "temperature": climate_entity.async_set_temperature,
    }

    with pytest.raises(ServiceValidationError):
        await commands[method](*args, **kwargs)
    coordinator.api.set_device_property.assert_not_awaited()


async def test_command_errors_are_visible_and_do_not_refresh_as_success(heater):
    coordinator, climate_entity, brightness, _temperature, switches = heater
    coordinator.api.set_device_property.side_effect = DeLonghiConnectionError(
        "Service unavailable"
    )

    for command in (
        climate_entity.async_turn_on,
        switches[0].async_turn_on,
    ):
        with pytest.raises(HomeAssistantError):
            await command()
    with pytest.raises(HomeAssistantError):
        await brightness.async_select_option("Level 1")

    coordinator.api.set_device_property.side_effect = None
    coordinator.api.set_device_property.return_value = False
    with pytest.raises(HomeAssistantError):
        await climate_entity.async_turn_off()
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.parametrize(
    "value",
    (None, True, [], {}, "unknown", "nan", "inf", float("inf")),
)
def test_numeric_values_reject_invalid_telemetry(value):
    assert numeric_value(value) is None


def test_numeric_values_accept_numeric_telemetry():
    assert numeric_value("20.5") == 20.5
    assert indexed_value("1", ["one", "two"], 1) == "one"
    assert indexed_value(0, ["one", "two"], 1) is None
