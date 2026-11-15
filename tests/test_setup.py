"""Offline tests for setup retries and coordinator failures."""

import logging

import pytest
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


@pytest.fixture
def setup_context(mocker):
    hass = mocker.MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = mocker.AsyncMock()
    entry = mocker.MagicMock()
    entry.entry_id = "test-entry"
    entry.data = {
        "username": "test@example.invalid",
        "password": "test-password",
    }
    api = mocker.MagicMock()
    api.authenticate = mocker.AsyncMock(return_value=True)
    api.get_devices = mocker.AsyncMock()
    coordinator = mocker.MagicMock()
    coordinator.async_config_entry_first_refresh = mocker.AsyncMock()
    for target, result in (
        ("DeLonghiAPI", api),
        ("async_get_clientsession", mocker.MagicMock()),
        ("DeLonghiCoordinator", coordinator),
    ):
        mocker.patch(f"{MODULE}.{target}", return_value=result)
    return hass, entry, api, coordinator


async def test_mixed_account_initializes_only_heater(setup_context, caplog):
    hass, entry, api, coordinator = setup_context
    api.get_devices.return_value = [
        {"device": {"dsn": "test-heater", "oem_model": "DL-heater"}},
        {"device": {"dsn": "test-unknown", "oem_model": "unknown"}},
    ]

    with caplog.at_level(logging.WARNING, logger=MODULE):
        assert await async_setup_entry(hass, entry)

    assert "test-unknown" not in caplog.text
    data = hass.data["delonghi_comfort"]["test-entry"]
    assert set(data) == {"heater_coordinators"}
    assert data["heater_coordinators"] == [coordinator]
    coordinator.async_config_entry_first_refresh.assert_awaited_once()


async def test_unknown_only_account_creates_no_entities(setup_context, caplog):
    hass, entry, api, coordinator = setup_context
    api.get_devices.return_value = [{"device": {"dsn": "unknown"}}]

    with caplog.at_level(logging.WARNING, logger=MODULE):
        with pytest.raises(ConfigEntryError):
            await async_setup_entry(hass, entry)

    hass.config_entries.async_forward_entry_setups.assert_not_awaited()
    coordinator.async_config_entry_first_refresh.assert_not_awaited()
    assert hass.data == {}


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (DeLonghiAuthenticationError, ConfigEntryAuthFailed),
        (DeLonghiConnectionError, ConfigEntryNotReady),
    ),
)
async def test_auth_failure_and_outage_have_distinct_ha_errors(
    setup_context,
    error,
    expected,
):
    _hass, entry, api, _coordinator = setup_context
    api.authenticate.side_effect = error("sanitized")

    with pytest.raises(expected):
        await async_setup_entry(_hass, entry)


async def test_empty_devices_retry_instead_of_succeeding(setup_context):
    hass, entry, api, _coordinator = setup_context
    api.get_devices.return_value = []

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry)


async def test_failed_platform_unload_keeps_entry_data(setup_context, mocker):
    hass, entry, _api, _coordinator = setup_context
    hass.data = {"delonghi_comfort": {"test-entry": {"preserved": True}}}
    hass.config_entries.async_unload_platforms = mocker.AsyncMock(return_value=False)
    assert not await async_unload_entry(hass, entry)
    assert "test-entry" in hass.data["delonghi_comfort"]

    hass.config_entries.async_unload_platforms.return_value = True
    assert await async_unload_entry(hass, entry)
    assert "test-entry" not in hass.data["delonghi_comfort"]


async def test_coordinator_properties_and_failure_classification(mocker):
    coordinator = mocker.MagicMock()
    coordinator.api.get_device_properties = mocker.AsyncMock(
        return_value=[
            {"property": {"name": "room_temp", "value": 20.5}},
            {"property": {"name": "future_property", "value": "unknown"}},
        ]
    )

    data = await DeLonghiCoordinator._async_update_data(coordinator)
    assert data == {"room_temp": 20.5, "future_property": "unknown"}

    coordinator.api.get_device_properties.return_value = []
    with pytest.raises(UpdateFailed):
        await DeLonghiCoordinator._async_update_data(coordinator)

    for error, expected in (
        (DeLonghiAuthenticationError, ConfigEntryAuthFailed),
        (DeLonghiConnectionError, UpdateFailed),
    ):
        coordinator.api.get_device_properties.side_effect = error("sanitized")
        with pytest.raises(expected):
            await DeLonghiCoordinator._async_update_data(coordinator)
