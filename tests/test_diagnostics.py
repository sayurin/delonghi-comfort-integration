"""Offline account diagnostics and privacy regression tests."""

import json
from pathlib import Path

import pytest
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


@pytest.fixture
def diagnostic_context(mocker):
    hass = mocker.MagicMock()
    entry = mocker.MagicMock()
    entry.data = {
        "username": "fixture@example.invalid",
        "password": "fixture-password",
        "language": "ja",
    }
    api = mocker.MagicMock()
    api.access_token = "fixture-access-token"
    api.refresh_token = "fixture-refresh-token"
    api.authenticate = mocker.AsyncMock()
    devices = [
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
    api.get_devices = mocker.AsyncMock(return_value=devices)
    api.get_device_properties = mocker.AsyncMock(
        return_value=[
            {"property": {"name": "room_temp", "value": "20.5", "key": 999}},
        ]
    )
    factory = mocker.patch(f"{MODULE}.DeLonghiAPI", return_value=api)
    mocker.patch(f"{MODULE}.async_get_clientsession", return_value="session")
    return hass, entry, api, devices, factory


async def test_all_devices_including_unsupported_are_fetched_on_request(
    diagnostic_context,
):
    hass, entry, api, _devices, factory = diagnostic_context

    data = await async_get_config_entry_diagnostics(hass, entry)

    factory.assert_called_once_with(
        "fixture@example.invalid", "fixture-password", "session", "ja"
    )
    api.authenticate.assert_awaited_once()
    assert [call.args for call in api.get_device_properties.await_args_list] == [
        ("fixture-heater",),
        ("fixture-other",),
    ]
    assert [item["device"]["supported"] for item in data["devices"]] == [True, False]
    assert data["devices"][1]["device"]["model"] == "AC-100"
    assert data["devices"][1]["properties"] == [
        {"property": {"name": "room_temp", "value": "20.5"}}
    ]
    hass.config_entries.async_forward_entry_setups.assert_not_called()
    api.set_device_property.assert_not_called()


async def test_sensitive_properties_nested_data_and_unknown_text_are_redacted(
    diagnostic_context,
):
    hass, entry, api, devices, _factory = diagnostic_context
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
    api.get_device_properties.return_value = properties

    data = await async_get_config_entry_diagnostics(hass, entry)

    values = {
        item["property"]["name"]: item["property"]["value"]
        for item in data["devices"][0]["properties"]
    }
    assert values["room_temp"] == 20.5
    assert values["hardware_version"] == "1.2.3"
    for name in (
        "wifi_ssid",
        "serial_number",
        "access_token",
        "future_text",
        "future_data_json",
    ):
        assert values[name] == REDACTED
    assert values["future_data"] == {
        "id": REDACTED,
        "voltage": 220,
        "samples": [REDACTED, "20.5", REDACTED],
    }
    serialized = json.dumps(data)
    for secret in (
        *entry.data.values(),
        "fixture-heater",
        "fixture-other",
        "fixture-access-token",
        "fixture-refresh-token",
        "Private room",
        "Private network",
        "987654",
        "999",
    ):
        if secret != "ja":
            assert str(secret) not in serialized
    assert properties[1]["property"]["value"] == "Private network"
    assert devices[0]["device"]["dsn"] == "fixture-heater"


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (DeLonghiConnectionError, "cannot_connect"),
        (DeLonghiProtocolError, "unexpected_response"),
    ),
)
async def test_individual_failures_are_explicit_and_other_devices_are_retained(
    diagnostic_context,
    caplog,
    error,
    expected,
):
    hass, entry, api, _devices, _factory = diagnostic_context
    api.get_device_properties.side_effect = [error("private-error"), []]

    with caplog.at_level("WARNING", logger=MODULE):
        data = await async_get_config_entry_diagnostics(hass, entry)

    assert data["devices"][0]["error"] == expected
    assert "properties" not in data["devices"][0]
    assert data["devices"][1]["properties"] == []
    assert "private-error" not in caplog.text
    assert "fixture-heater" not in caplog.text


async def test_account_failure_and_expired_session_do_not_return_success(
    diagnostic_context,
):
    hass, entry, api, _devices, _factory = diagnostic_context
    api.get_devices.side_effect = DeLonghiConnectionError("Service unavailable")

    with pytest.raises(DeLonghiConnectionError):
        await async_get_config_entry_diagnostics(hass, entry)
    api.get_device_properties.assert_not_awaited()

    api.get_devices.side_effect = None
    api.get_device_properties.side_effect = DeLonghiAuthenticationError("Expired")
    with pytest.raises(DeLonghiAuthenticationError):
        await async_get_config_entry_diagnostics(hass, entry)


async def test_empty_account_has_an_explicit_empty_device_list(diagnostic_context):
    hass, entry, api, _devices, _factory = diagnostic_context
    api.get_devices.return_value = []

    assert await async_get_config_entry_diagnostics(hass, entry) == {"devices": []}
    api.get_device_properties.assert_not_awaited()


async def test_device_diagnostics_never_downloads_account_list_or_other_properties(
    diagnostic_context,
    mocker,
):
    hass, entry, api, _devices, _factory = diagnostic_context
    device = mocker.MagicMock()
    device.identifiers = {("delonghi_comfort", "fixture-heater")}
    device.model = "MDHAA15WIFI-BK"
    device.sw_version = "1.2.3"

    data = await async_get_device_diagnostics(hass, entry, device)

    api.get_devices.assert_not_awaited()
    api.get_device_properties.assert_awaited_once_with("fixture-heater")
    assert len(data["devices"]) == 1
    assert data["devices"][0]["device"]["model"] == "MDHAA15WIFI-BK"
    assert "fixture-heater" not in json.dumps(data)
    assert data["devices"][0]["properties"] == [
        {"property": {"name": "room_temp", "value": "20.5"}}
    ]


@pytest.mark.parametrize(
    "identifiers",
    (
        set(),
        {("other", "fixture-heater")},
        {("delonghi_comfort", "first"), ("delonghi_comfort", "second")},
    ),
)
async def test_device_diagnostics_rejects_missing_or_ambiguous_identifiers(
    diagnostic_context,
    mocker,
    identifiers,
):
    hass, entry, api, _devices, _factory = diagnostic_context
    device = mocker.MagicMock()
    device.identifiers = identifiers

    with pytest.raises(HomeAssistantError):
        await async_get_device_diagnostics(hass, entry, device)

    api.authenticate.assert_not_awaited()
    api.get_devices.assert_not_awaited()
    api.get_device_properties.assert_not_awaited()


def test_japanese_translation_has_exactly_the_english_keys():
    root = (
        Path(__file__).resolve().parents[1]
        / "custom_components/delonghi_comfort/translations"
    )
    english = json.loads((root / "en.json").read_text())
    japanese = json.loads((root / "ja.json").read_text())

    def check_keys(left, right):
        assert set(left) == set(right)
        for key, value in left.items():
            if isinstance(value, dict):
                check_keys(value, right[key])
            else:
                assert isinstance(right[key], str)
                assert right[key]

    check_keys(english, japanese)
