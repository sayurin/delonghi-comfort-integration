"""Offline tests for account validation, options and reauthentication."""

import pytest

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


@pytest.fixture
def config_flow(mocker):
    flow = DelonghiComfortConfigFlow()
    flow.hass = mocker.MagicMock()
    flow.async_set_unique_id = mocker.AsyncMock()
    flow._abort_if_unique_id_configured = mocker.MagicMock()
    api = mocker.MagicMock()
    api.authenticate = mocker.AsyncMock(return_value=True)
    api.get_devices = mocker.AsyncMock(return_value=DEVICES)
    mocker.patch(f"{FLOW_MODULE}.DeLonghiAPI", return_value=api)
    mocker.patch(f"{FLOW_MODULE}.async_get_clientsession")
    return flow, api


@pytest.fixture
def options_flow(mocker):
    flow = DelonghiComfortOptionsFlow()
    flow.hass = mocker.MagicMock()
    flow.handler = "test-entry"
    entry = mocker.MagicMock()
    entry.options = {}
    flow.hass.config_entries.async_get_known_entry.return_value = entry
    return flow


async def test_user_entry_keeps_existing_username_id(config_flow):
    flow, _api = config_flow

    result = await flow.async_step_user(ACCOUNT)

    assert result["type"] == "create_entry"
    assert result["data"] == ACCOUNT
    flow.async_set_unique_id.assert_awaited_once_with(ACCOUNT["username"])


@pytest.mark.parametrize(
    ("exception", "error"),
    (
        (DeLonghiAuthenticationError, "invalid_auth"),
        (DeLonghiConnectionError, "cannot_connect"),
        (DeLonghiProtocolError, "unexpected_response"),
    ),
)
async def test_user_failure_classification(config_flow, exception, error):
    flow, api = config_flow
    api.authenticate.side_effect = exception("sanitized")

    result = await flow.async_step_user(ACCOUNT)

    assert result["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("devices", "error"),
    (
        ([], "no_devices"),
        ([{"device": {"oem_model": "unknown"}}], "unsupported_devices"),
        ([{"device": {}}], "unsupported_devices"),
    ),
)
async def test_empty_and_unsupported_accounts(config_flow, devices, error):
    flow, api = config_flow
    api.get_devices.return_value = devices

    result = await flow.async_step_user(ACCOUNT)

    assert result["errors"] == {"base": error}


async def test_reauthentication_reloads_same_entry_and_preserves_data(
    config_flow,
    mocker,
):
    flow, _api = config_flow
    entry = mocker.MagicMock()
    entry.data = {**ACCOUNT, "preserved": "existing"}
    flow._get_reauth_entry = mocker.MagicMock(return_value=entry)
    flow.async_update_reload_and_abort = mocker.MagicMock(
        return_value={"type": "abort", "reason": "reauth_successful"}
    )

    form = await flow.async_step_reauth(entry.data)
    result = await flow.async_step_reauth_confirm({"password": "new-password"})

    assert form["step_id"] == "reauth_confirm"
    assert result["reason"] == "reauth_successful"
    flow.async_update_reload_and_abort.assert_called_once_with(
        entry, data_updates={**entry.data, "password": "new-password"}
    )
    flow.async_set_unique_id.assert_not_awaited()


async def test_failed_reauthentication_does_not_update_entry(config_flow, mocker):
    flow, api = config_flow
    entry = mocker.MagicMock()
    entry.data = ACCOUNT.copy()
    flow._get_reauth_entry = mocker.MagicMock(return_value=entry)
    flow.async_update_reload_and_abort = mocker.MagicMock()
    api.authenticate.side_effect = DeLonghiAuthenticationError("sanitized")

    result = await flow.async_step_reauth_confirm({"password": "wrong"})

    assert result["errors"]["base"] == "invalid_auth"
    assert entry.data == ACCOUNT
    flow.async_update_reload_and_abort.assert_not_called()


async def test_default_and_allowed_scan_intervals(options_flow):
    result = await options_flow.async_step_init()
    assert result["data_schema"]({})["scan_interval"] == 60

    for value in (5, 15, 300):
        result = await options_flow.async_step_init({"scan_interval": value})
        assert result["data"] == {"scan_interval": value}


@pytest.mark.parametrize("value", (4, 301, "invalid"))
async def test_invalid_scan_intervals_do_not_create_options(options_flow, value):
    result = await options_flow.async_step_init({"scan_interval": value})
    assert result["errors"]["base"] == "invalid_scan_interval"
