"""Offline regression tests for the De'Longhi API client."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from custom_components.delonghi_comfort.api import DeLonghiAPI


def response_context(data=None, *, text=None, headers=None):
    """Build an aiohttp-style response context without network access."""
    response = MagicMock()
    response.text = AsyncMock(return_value=text if text is not None else json.dumps(data))
    response.headers = headers or {}
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
        with self.assertLogs(
            "custom_components.delonghi_comfort.api", level="ERROR"
        ) as logs:
            self.assertFalse(await api.authenticate())
        self.assertIn("Consent signature not found", logs.output[0])
        self.assertNotIn("private-page-content", "\n".join(logs.output))
        self.assertEqual(api.session.get.call_count, 3)
        self.assertEqual(api.session.post.call_count, 2)
