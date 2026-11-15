"""Offline regression tests for the De'Longhi API client."""

import json

import aiohttp
import pytest

from custom_components.delonghi_comfort.api import (
    DeLonghiAPI,
    DeLonghiAuthenticationError,
    DeLonghiConnectionError,
    DeLonghiProtocolError,
)


def response_context(data=None, *, text=None, headers=None, status=200, mocker):
    """Build an aiohttp-style response context without network access."""
    response = mocker.MagicMock()
    response.text = mocker.AsyncMock(
        return_value=text if text is not None else json.dumps(data)
    )
    response.headers = headers or {}
    response.status = status
    context = mocker.MagicMock()
    context.__aenter__ = mocker.AsyncMock(return_value=response)
    context.__aexit__ = mocker.AsyncMock(return_value=False)
    return context


def make_api(page, mocker):
    """Create an API client with a canned authentication exchange."""
    session = mocker.MagicMock()
    session.get.side_effect = [
        response_context(
            headers={"Location": "https://example.invalid/?context=test"},
            mocker=mocker,
        ),
        response_context(
            {"ucid": "test", "gmid": "test", "gmidTicket": "test"}, mocker=mocker
        ),
        response_context(text=page, mocker=mocker),
        response_context(
            headers={"Location": "https://example.invalid/?code=test"},
            mocker=mocker,
        ),
    ]
    session.post.side_effect = [
        response_context(
            {"statusCode": 200, "sessionInfo": {"login_token": "test-login"}},
            mocker=mocker,
        ),
        response_context(
            {"UID": "test-user", "UIDSignature": "test", "signatureTimestamp": 0},
            mocker=mocker,
        ),
        response_context({"access_token": "test-idp"}, mocker=mocker),
        response_context(
            {"access_token": "test-access", "refresh_token": "test-refresh"},
            mocker=mocker,
        ),
    ]
    return DeLonghiAPI("test@example.invalid", "test-password", session)


@pytest.mark.parametrize(
    "page",
    (
        "const consentObj2Sig = 'test-signature';",
        'const consentObj2Sig = "test-signature";',
        'const  consentObj2Sig="test-signature";',
    ),
)
async def test_authentication_accepts_supported_signature_formats(page, mocker):
    api = make_api(page, mocker)

    assert await api.authenticate()
    assert api.access_token == "test-access"
    assert api.refresh_token == "test-refresh"
    assert api.session.get.call_args.kwargs["params"]["sig"] == "test-signature"


async def test_missing_signature_stops_without_logging_page(mocker):
    api = make_api("<html>private-page-content</html>", mocker)

    with pytest.raises(DeLonghiProtocolError) as error:
        await api.authenticate()

    assert "Consent signature not found" in str(error.value)
    assert "private-page-content" not in str(error.value)
    assert api.session.get.call_count == 3
    assert api.session.post.call_count == 2


async def test_invalid_credentials_do_not_expose_vendor_details(mocker):
    api = make_api("unused", mocker)
    api.session.post.side_effect = [
        response_context(
            {
                "statusCode": 403,
                "errorCode": 403043,
                "errorDetails": "private-value",
            },
            mocker=mocker,
        )
    ]

    with pytest.raises(DeLonghiAuthenticationError) as error:
        await api.authenticate()

    assert "private-value" not in str(error.value)
    assert api.session.post.call_count == 1


async def test_missing_context_stops_before_login(mocker):
    api = make_api("unused", mocker)
    api.session.get.side_effect = [
        response_context(
            headers={"Location": "https://example.invalid/"},
            mocker=mocker,
        )
    ]

    with pytest.raises(DeLonghiProtocolError):
        await api.authenticate()

    api.session.post.assert_not_called()


async def test_login_transport_error_does_not_expose_url(mocker):
    api = make_api("unused", mocker)
    api.session.get.side_effect = aiohttp.ClientConnectionError("private-url")

    with pytest.raises(DeLonghiConnectionError) as error:
        await api.authenticate()

    assert "private-url" not in str(error.value)


@pytest.fixture
def api_client(mocker):
    """Create a client with mocked HTTP session and valid tokens."""
    session = mocker.MagicMock()
    api = DeLonghiAPI("test@example.invalid", "test-password", session)
    api.access_token = "test-access"
    api.refresh_token = "test-refresh"
    return api


async def test_empty_devices_are_distinct_from_failed_requests(api_client, mocker):
    api_client.session.request.return_value = response_context([], mocker=mocker)
    assert await api_client.get_devices() == []

    api_client.session.request.return_value = response_context(
        status=503, mocker=mocker
    )
    with pytest.raises(DeLonghiConnectionError):
        await api_client.get_devices()


@pytest.mark.parametrize(
    ("status", "error"),
    (
        (400, DeLonghiProtocolError),
        (403, DeLonghiAuthenticationError),
        (429, DeLonghiConnectionError),
        (500, DeLonghiConnectionError),
    ),
)
async def test_http_failure_classification(api_client, mocker, status, error):
    api_client.session.request.return_value = response_context(
        status=status, mocker=mocker
    )

    with pytest.raises(error):
        await api_client.get_devices()


@pytest.mark.parametrize(
    "data",
    ({}, None, [None], [{"device": {}}]),
)
async def test_invalid_device_shapes_are_rejected(api_client, mocker, data):
    api_client.session.request.return_value = response_context(data, mocker=mocker)

    with pytest.raises(DeLonghiProtocolError):
        await api_client.get_devices()


async def test_invalid_json_does_not_expose_response(api_client, mocker):
    api_client.session.request.return_value = response_context(
        text="<private>not JSON",
        mocker=mocker,
    )

    with pytest.raises(DeLonghiProtocolError) as error:
        await api_client.get_devices()

    assert "private" not in str(error.value)


async def test_unknown_property_shape_is_preserved(api_client, mocker):
    api_client.session.request.return_value = response_context(
        [{"property": {"name": "future_property", "value": {"future": "value"}}}],
        mocker=mocker,
    )
    assert len(await api_client.get_device_properties("test-dsn")) == 1


@pytest.mark.parametrize(
    "data",
    ({}, [{"property": {"name": "room_temp"}}], [{"property": None}]),
)
async def test_invalid_property_shapes_are_rejected(api_client, mocker, data):
    api_client.session.request.return_value = response_context(data, mocker=mocker)

    with pytest.raises(DeLonghiProtocolError):
        await api_client.get_device_properties("test-dsn")


async def test_refresh_rotates_tokens_and_retries_once(api_client, mocker):
    api_client.session.request.side_effect = [
        response_context(status=401, mocker=mocker),
        response_context([], mocker=mocker),
    ]
    api_client.session.post.return_value = response_context(
        {"access_token": "new-access", "refresh_token": "new-refresh"},
        mocker=mocker,
    )

    assert await api_client.get_devices() == []
    assert api_client.access_token == "new-access"
    assert api_client.refresh_token == "new-refresh"
    assert (
        api_client.session.request.call_args.kwargs["headers"]["Authorization"]
        == "auth_token new-access"
    )
    assert api_client.session.post.call_count == 1


async def test_second_unauthorized_response_requires_reauthentication(
    api_client, mocker
):
    api_client.session.request.side_effect = [
        response_context(status=401, mocker=mocker),
        response_context(status=401, mocker=mocker),
    ]
    api_client.session.post.return_value = response_context(
        {"access_token": "new-access"},
        mocker=mocker,
    )

    with pytest.raises(DeLonghiAuthenticationError):
        await api_client.get_devices()

    assert api_client.session.request.call_count == 2
    assert api_client.session.post.call_count == 1


async def test_refresh_service_failure_does_not_trigger_full_login(api_client, mocker):
    api_client.session.request.return_value = response_context(
        status=401, mocker=mocker
    )
    api_client.session.post.return_value = response_context(status=503, mocker=mocker)

    with pytest.raises(DeLonghiConnectionError):
        await api_client.get_devices()

    api_client.session.get.assert_not_called()
    assert api_client.session.request.call_count == 1


async def test_transport_timeout_is_not_an_empty_device_list(api_client):
    api_client.session.request.side_effect = TimeoutError("private-url")

    with pytest.raises(DeLonghiConnectionError) as error:
        await api_client.get_devices()

    assert "private-url" not in str(error.value)


async def test_command_failure_is_not_reported_as_success(api_client, mocker):
    api_client.session.request.return_value = response_context(
        status=503, mocker=mocker
    )
    with pytest.raises(DeLonghiConnectionError):
        await api_client.set_device_property("test-dsn", "set_status", 2)

    api_client.session.request.return_value = response_context([], mocker=mocker)
    with pytest.raises(DeLonghiProtocolError):
        await api_client.set_device_property("test-dsn", "set_status", 2)
