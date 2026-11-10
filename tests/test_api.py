"""Offline regression tests for the De'Longhi API client."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock

import aiohttp

from custom_components.delonghi_comfort.api import (
    DeLonghiAPI,
    DeLonghiAuthenticationError,
    DeLonghiConnectionError,
    DeLonghiProtocolError,
)


def response_context(data=None, *, text=None, headers=None, status=200):
    """Build an aiohttp-style response context without network access."""
    response = MagicMock()
    response.text = AsyncMock(return_value=text if text is not None else json.dumps(data))
    response.headers = headers or {}
    response.status = status
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    return context


class ConsentSignatureTests(unittest.IsolatedAsyncioTestCase):
    """Exercise signature extraction through the actual authentication flow."""

    def make_api(self, page):
        session = MagicMock()
        session.get.side_effect = [
            response_context(headers={"Location": "https://example.invalid/?context=test"}),
            response_context({"ucid": "test", "gmid": "test", "gmidTicket": "test"}),
            response_context(text=page),
            response_context(headers={"Location": "https://example.invalid/?code=test"}),
        ]
        session.post.side_effect = [
            response_context(
                {"statusCode": 200, "sessionInfo": {"login_token": "test-login"}}
            ),
            response_context(
                {"UID": "test-user", "UIDSignature": "test", "signatureTimestamp": 0}
            ),
            response_context({"access_token": "test-idp"}),
            response_context(
                {"access_token": "test-access", "refresh_token": "test-refresh"}
            ),
        ]
        return DeLonghiAPI("test@example.invalid", "test-password", session)

    async def test_supported_quotes_and_spacing(self):
        for page in (
            "const consentObj2Sig = 'test-signature';",
            'const consentObj2Sig = "test-signature";',
            'const  consentObj2Sig="test-signature";',
        ):
            with self.subTest(page=page):
                api = self.make_api(page)
                self.assertTrue(await api.authenticate())
                self.assertEqual(api.access_token, "test-access")
                self.assertEqual(api.refresh_token, "test-refresh")
                self.assertEqual(
                    api.session.get.call_args.kwargs["params"]["sig"], "test-signature"
                )

    async def test_missing_signature_stops_without_logging_page(self):
        api = self.make_api("<html>private-page-content</html>")
        with self.assertRaises(DeLonghiProtocolError) as error:
            await api.authenticate()
        self.assertIn("Consent signature not found", str(error.exception))
        self.assertNotIn("private-page-content", str(error.exception))
        self.assertEqual(api.session.get.call_count, 3)
        self.assertEqual(api.session.post.call_count, 2)

    async def test_invalid_credentials_do_not_expose_vendor_details(self):
        api = self.make_api("unused")
        api.session.post.side_effect = [
            response_context(
                {"statusCode": 403, "errorCode": 403043, "errorDetails": "private-value"}
            )
        ]
        with self.assertRaises(DeLonghiAuthenticationError) as error:
            await api.authenticate()
        self.assertNotIn("private-value", str(error.exception))
        self.assertEqual(api.session.post.call_count, 1)

    async def test_missing_context_stops_before_login(self):
        api = self.make_api("unused")
        api.session.get.side_effect = [
            response_context(headers={"Location": "https://example.invalid/"})
        ]
        with self.assertRaises(DeLonghiProtocolError):
            await api.authenticate()
        api.session.post.assert_not_called()

    async def test_login_transport_error_does_not_expose_url(self):
        api = self.make_api("unused")
        api.session.get.side_effect = aiohttp.ClientConnectionError("private-url")
        with self.assertRaises(DeLonghiConnectionError) as error:
            await api.authenticate()
        self.assertNotIn("private-url", str(error.exception))


class APIRequestTests(unittest.IsolatedAsyncioTestCase):
    """Distinguish unavailable service, invalid data and expired credentials."""

    def setUp(self):
        self.session = MagicMock()
        self.api = DeLonghiAPI("test@example.invalid", "test-password", self.session)
        self.api.access_token = "test-access"
        self.api.refresh_token = "test-refresh"

    async def test_empty_devices_are_distinct_from_failed_requests(self):
        self.session.request.return_value = response_context([])
        self.assertEqual(await self.api.get_devices(), [])
        self.session.request.return_value = response_context(status=503)
        with self.assertRaises(DeLonghiConnectionError):
            await self.api.get_devices()

    async def test_http_failure_classification(self):
        for status, error in (
            (400, DeLonghiProtocolError),
            (403, DeLonghiAuthenticationError),
            (429, DeLonghiConnectionError),
            (500, DeLonghiConnectionError),
        ):
            with self.subTest(status=status):
                self.session.request.return_value = response_context(status=status)
                with self.assertRaises(error):
                    await self.api.get_devices()

    async def test_json_and_device_shape_validation(self):
        for data in ({}, None, [None], [{"device": {}}]):
            with self.subTest(data=data):
                self.session.request.return_value = response_context(data)
                with self.assertRaises(DeLonghiProtocolError):
                    await self.api.get_devices()
        self.session.request.return_value = response_context(text="<private>not JSON")
        with self.assertRaises(DeLonghiProtocolError) as error:
            await self.api.get_devices()
        self.assertNotIn("private", str(error.exception))

    async def test_property_shape_validation_and_unknown_property(self):
        self.session.request.return_value = response_context(
            [{"property": {"name": "future_property", "value": {"future": "value"}}}]
        )
        self.assertEqual(len(await self.api.get_device_properties("test-dsn")), 1)
        for data in ({}, [{"property": {"name": "room_temp"}}], [{"property": None}]):
            self.session.request.return_value = response_context(data)
            with self.assertRaises(DeLonghiProtocolError):
                await self.api.get_device_properties("test-dsn")

    async def test_refresh_rotates_tokens_and_retries_once(self):
        self.session.request.side_effect = [
            response_context(status=401),
            response_context([]),
        ]
        self.session.post.return_value = response_context(
            {"access_token": "new-access", "refresh_token": "new-refresh"}
        )
        self.assertEqual(await self.api.get_devices(), [])
        self.assertEqual(self.api.access_token, "new-access")
        self.assertEqual(self.api.refresh_token, "new-refresh")
        self.assertEqual(
            self.session.request.call_args.kwargs["headers"]["Authorization"],
            "auth_token new-access",
        )
        self.assertEqual(self.session.post.call_count, 1)

    async def test_second_unauthorized_response_requires_reauthentication(self):
        self.session.request.side_effect = [
            response_context(status=401),
            response_context(status=401),
        ]
        self.session.post.return_value = response_context({"access_token": "new-access"})
        with self.assertRaises(DeLonghiAuthenticationError):
            await self.api.get_devices()
        self.assertEqual(self.session.request.call_count, 2)
        self.assertEqual(self.session.post.call_count, 1)

    async def test_refresh_service_failure_does_not_trigger_full_login(self):
        self.session.request.return_value = response_context(status=401)
        self.session.post.return_value = response_context(status=503)
        with self.assertRaises(DeLonghiConnectionError):
            await self.api.get_devices()
        self.session.get.assert_not_called()
        self.assertEqual(self.session.request.call_count, 1)

    async def test_transport_timeout_is_not_an_empty_device_list(self):
        self.session.request.side_effect = TimeoutError("private-url")
        with self.assertRaises(DeLonghiConnectionError) as error:
            await self.api.get_devices()
        self.assertNotIn("private-url", str(error.exception))

    async def test_command_failure_is_not_reported_as_success(self):
        self.session.request.return_value = response_context(status=503)
        with self.assertRaises(DeLonghiConnectionError):
            await self.api.set_device_property("test-dsn", "set_status", 2)
        self.session.request.return_value = response_context([])
        with self.assertRaises(DeLonghiProtocolError):
            await self.api.set_device_property("test-dsn", "set_status", 2)
