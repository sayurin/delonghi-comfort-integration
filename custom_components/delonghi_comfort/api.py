"""API client for De'Longhi Comfort devices."""

import asyncio
import base64
import json
import re
import urllib.parse
from datetime import datetime
from typing import Any

import aiohttp
from homeassistant.exceptions import HomeAssistantError

SDK_BUILD = 16650

API_KEY = "3_e5qn7USZK-QtsIso1wCelqUKAK_IVEsYshRIssQ-X-k55haiZXmKWDHDRul2e5Y2"

CLIENT_ID = "1S8q1WJEs-emOB43Z0-66WnL"

CLIENT_SECRET = "lmnceiD0B-4KPNN5ZS6WuWU70j9V5BCuSlz2OPsvHkyLryhMkJkPvKsivfTq3RfNYj8GpCELtOBvhaDIzKcBtg"

AUTHORIZATION_HEADER = (
    "Basic " + base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
)

APP_ID = "DeLonghiComfort2-mw-id"

APP_SECRET = "DeLonghiComfort2-Yg4miiqiNcf0Or-EhJwRh7ACfBY"

BROWSER_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 13_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/79.0.3945.73 Mobile/15E148 Safari/604.1"

TOKEN_USER_AGENT = "DeLonghiComfort/3 CFNetwork/1568.300.101 Darwin/24.2.0"

API_USER_AGENT = "DeLonghiComfort/5.1.1 (iPhone; iOS 18.2; Scale/3.00)"

# The consent page has used both single and double quotes for this literal.
_CONSENT_SIG_RE = re.compile(r"""const\s+consentObj2Sig\s*=\s*(["'])(.*?)\1""")
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class DeLonghiError(HomeAssistantError):
    """An API operation could not be completed."""


class DeLonghiAuthenticationError(DeLonghiError):
    """The account credentials or session are no longer valid."""


class DeLonghiConnectionError(DeLonghiError):
    """The service could not be reached or is temporarily unavailable."""


class DeLonghiProtocolError(DeLonghiError):
    """The service returned an unexpected response."""


class DeLonghiAPI:
    """API client for De'Longhi Comfort devices."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        language: str = "en",
    ) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.language = language
        self.session = session
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self._auth_lock = asyncio.Lock()

    @staticmethod
    def _check_status(response: aiohttp.ClientResponse) -> None:
        """Classify HTTP failures without exposing a URL or response body."""
        if response.status in (401, 403):
            raise DeLonghiAuthenticationError("De'Longhi authentication expired or denied")
        if response.status == 429 or response.status >= 500:
            raise DeLonghiConnectionError("De'Longhi service is temporarily unavailable")
        if response.status >= 400:
            raise DeLonghiProtocolError("De'Longhi rejected the API request")

    async def _read_json(self, response: aiohttp.ClientResponse) -> Any:
        """Read JSON without putting API responses in exception messages."""
        self._check_status(response)
        try:
            return json.loads(await response.text())
        except (ValueError, UnicodeError):
            raise DeLonghiProtocolError("De'Longhi returned invalid JSON") from None

    @staticmethod
    def _require_string(data: dict[str, Any], key: str) -> str:
        """Reject absent and empty tokens rather than sending them to another endpoint."""
        if not isinstance(data, dict):
            raise DeLonghiProtocolError("De'Longhi returned an incomplete authentication response")
        value = data[key]
        if not isinstance(value, str) or not value:
            raise DeLonghiProtocolError("De'Longhi returned an incomplete authentication response")
        return value

    def get_query_param(self, url: str, param: str) -> str | None:
        """Extract query parameter from URL."""
        query = urllib.parse.urlparse(url).query
        params = urllib.parse.parse_qs(query)
        return params.get(param, [None])[0]

    async def authenticate(self) -> bool:
        """Authenticate with the De'Longhi API."""
        async with self._auth_lock:
            self.access_token = await self._get_new_access_token()
        return True
    async def _get_new_access_token(self) -> str:
        """Get a new access token through the full authentication flow."""

        
        # Thanks to https://github.com/duckwc/ECAMpy for the code to token convertion
        # Thanks to https://github.com/rtfpessoa/delonghi-comfort-client, for the cli code to implement the authentication flow
        try:
            # Step 1: Start authentication process
            async with self.session.get(
                f"https://fidm.eu1.gigya.com/oidc/op/v1.0/{API_KEY}/authorize",
                headers={"User-Agent": BROWSER_USER_AGENT},
                params={
                    "client_id": CLIENT_ID,
                    "response_type": "code",
                    "redirect_uri": "https://google.it",
                    "scope": "openid email profile UID comfort en alexa",
                    "nonce": str(int(datetime.now().timestamp())),
                },
                allow_redirects=False,
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                self._check_status(response)
                context = self.get_query_param(response.headers["Location"], "context")
                if not context:
                    raise DeLonghiProtocolError("De'Longhi did not provide an authentication context")

            # Step 2: Fetch Gigya session data
            async with self.session.get(
                "https://socialize.eu1.gigya.com/socialize.getIDs",
                headers={"User-Agent": BROWSER_USER_AGENT},
                params={
                    "APIKey": API_KEY,
                    "includeTicket": "true",
                    "pageURL": "https://aylaopenid.delonghigroup.com/",
                    "sdk": "js_latest",
                    "sdkBuild": SDK_BUILD,
                    "format": "json",
                },
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                data = await self._read_json(response)

            ucid = self._require_string(data, "ucid")
            gmid = self._require_string(data, "gmid")
            gmid_ticket = self._require_string(data, "gmidTicket")

            # Step 3: Login
            risk_context_json = json.dumps(
                {
                    "b0": 4494,
                    "b1": [0, 2, 2, 0],
                    "b2": 2,
                    "b3": [],
                    "b4": 2,
                    "b5": 1,
                    "b6": BROWSER_USER_AGENT,
                    "b7": [
                        {
                            "name": "PDF Viewer",
                            "filename": "internal-pdf-viewer",
                            "length": 2,
                        },
                        {
                            "name": "Chrome PDF Viewer",
                            "filename": "internal-pdf-viewer",
                            "length": 2,
                        },
                        {
                            "name": "Chromium PDF Viewer",
                            "filename": "internal-pdf-viewer",
                            "length": 2,
                        },
                        {
                            "name": "Microsoft Edge PDF Viewer",
                            "filename": "internal-pdf-viewer",
                            "length": 2,
                        },
                        {
                            "name": "WebKit built-in PDF",
                            "filename": "internal-pdf-viewer",
                            "length": 2,
                        },
                    ],
                    "b8": datetime.now().strftime("%H:%M:%S"),
                    "b9": 0,
                    "b10": {"state": "denied"},
                    "b11": False,
                    "b13": [5, "440|956|24", False, True],
                }
            )

            async with self.session.post(
                "https://accounts.eu1.gigya.com/accounts.login",
                headers={"User-Agent": BROWSER_USER_AGENT},
                data={
                    "loginID": self.username,
                    "password": self.password,
                    "sessionExpiration": 7884009,
                    "targetEnv": "jssdk",
                    "include": "profile,data,emails,subscriptions,preferences",
                    "includeUserInfo": "true",
                    "loginMode": "standard",
                    "lang": self.language,
                    "riskContext": urllib.parse.quote(risk_context_json),
                    "APIKey": API_KEY,
                    "source": "showScreenSet",
                    "sdk": "js_latest",
                    "authMode": "cookie",
                    "pageURL": "https://aylaopenid.delonghigroup.com/",
                    "gmid": gmid,
                    "ucid": ucid,
                    "sdkBuild": SDK_BUILD,
                    "format": "json",
                },
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                login_data = await self._read_json(response)

            if not isinstance(login_data, dict):
                raise DeLonghiProtocolError("De'Longhi returned an invalid login response")
            if login_data.get("statusCode") != 200:
                if login_data.get("errorCode") in (403042, 403043):
                    raise DeLonghiAuthenticationError("De'Longhi rejected the account credentials")
                raise DeLonghiProtocolError("De'Longhi login could not be completed")

            login_token = self._require_string(login_data["sessionInfo"], "login_token")

            # Step 4: Get user info
            async with self.session.post(
                "https://socialize.eu1.gigya.com/socialize.getUserInfo",
                headers={"User-Agent": BROWSER_USER_AGENT},
                data={
                    "enabledProviders": "*",
                    "APIKey": API_KEY,
                    "sdk": "js_latest",
                    "login_token": login_token,
                    "authMode": "cookie",
                    "pageURL": "https://aylaopenid.delonghigroup.com/",
                    "gmid": gmid,
                    "ucid": ucid,
                    "sdkBuild": SDK_BUILD,
                    "format": "json",
                },
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                user_data = await self._read_json(response)

            user_uid = self._require_string(user_data, "UID")
            user_uid_signature = self._require_string(user_data, "UIDSignature")
            user_signature_timestamp = user_data["signatureTimestamp"]

            # Step 5: Consent
            async with self.session.get(
                "https://aylaopenid.delonghigroup.com/OIDCConsentPage.php",
                headers={"User-Agent": BROWSER_USER_AGENT},
                params={
                    "lang": self.language,
                    "context": context,
                    "clientID": CLIENT_ID,
                    "scope": "openid+email+profile+UID+comfort+en+alexa",
                    "UID": user_uid,
                    "UIDSignature": user_uid_signature,
                    "signatureTimestamp": user_signature_timestamp,
                },
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                self._check_status(response)
                consent_text = await response.text()

            if not (match := _CONSENT_SIG_RE.search(consent_text)) or not match.group(2):
                raise DeLonghiProtocolError("Consent signature not found in consent page")
            signature = match.group(2)

            # Step 6: Authorization
            async with self.session.get(
                f"https://fidm.eu1.gigya.com/oidc/op/v1.0/{API_KEY}/authorize/continue",
                headers={"User-Agent": BROWSER_USER_AGENT},
                params={
                    "context": context,
                    "login_token": login_token,
                    "consent": json.dumps(
                        {
                            "scope": "openid email profile UID comfort en alexa",
                            "clientID": CLIENT_ID,
                            "context": context,
                            "UID": user_uid,
                            "consent": True,
                        },
                        separators=(",", ":"),
                    ),
                    "sig": signature,
                    "gmidTicket": gmid_ticket,
                },
                allow_redirects=False,
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                self._check_status(response)
                code = self.get_query_param(response.headers["Location"], "code")
                if not code:
                    raise DeLonghiProtocolError("De'Longhi did not provide an authorization code")

            # Step 7: Get IDP access token
            async with self.session.post(
                f"https://fidm.eu1.gigya.com/oidc/op/v1.0/{API_KEY}/token",
                headers={
                    "User-Agent": TOKEN_USER_AGENT,
                    "Authorization": AUTHORIZATION_HEADER,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": "https://google.it",
                },
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                token_data = await self._read_json(response)

            idp_token = self._require_string(token_data, "access_token")

            # Step 8: Exchange IDP token for Ayla token
            async with self.session.post(
                "https://user-field-eu.aylanetworks.com/api/v1/token_sign_in",
                headers={"User-Agent": TOKEN_USER_AGENT},
                data={
                    "app_id": APP_ID,
                    "app_secret": APP_SECRET,
                    "token": idp_token,
                },
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                ayla_data = await self._read_json(response)

            access_token = self._require_string(ayla_data, "access_token")
            self.refresh_token = self._require_string(ayla_data, "refresh_token")
            return access_token

        except (aiohttp.ClientError, TimeoutError):
            raise DeLonghiConnectionError("Unable to connect to De'Longhi authentication service") from None
        except (KeyError, TypeError, ValueError):
            raise DeLonghiProtocolError("De'Longhi returned an incomplete authentication response") from None

    async def refresh_access_token(self) -> str:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            return await self._get_new_access_token()

        try:
            async with self.session.post(
                "https://user-field-eu.aylanetworks.com/users/refresh_token.json",
                headers={
                    "User-Agent": TOKEN_USER_AGENT,
                    "Content-Type": "application/json",
                },
                json={"user": {"refresh_token": self.refresh_token}},
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                if response.status in (401, 403):
                    return await self._get_new_access_token()
                data = await self._read_json(response)
                new_access_token = self._require_string(data, "access_token")
                if "refresh_token" in data:
                    self.refresh_token = self._require_string(data, "refresh_token")
                return new_access_token
        except (aiohttp.ClientError, TimeoutError):
            raise DeLonghiConnectionError("Unable to refresh De'Longhi session") from None
        except (KeyError, TypeError, ValueError):
            raise DeLonghiProtocolError("De'Longhi returned an incomplete token response") from None

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get all devices associated with the account."""
        response = await self._get_request("apiv1/devices.json")
        if not isinstance(response, list) or any(
            not isinstance(item, dict)
            or not isinstance(item.get("device"), dict)
            or not isinstance(item["device"].get("dsn"), str)
            or not item["device"]["dsn"]
            for item in response
        ):
            raise DeLonghiProtocolError("De'Longhi returned an invalid device list")
        return response

    async def get_device_properties(self, dsn: str) -> list[dict[str, Any]]:
        """Get device properties by DSN."""
        response = await self._get_request(f"apiv1/dsns/{dsn}/properties.json")
        if not isinstance(response, list) or any(
            not isinstance(item, dict)
            or not isinstance(item.get("property"), dict)
            or not isinstance(item["property"].get("name"), str)
            or "value" not in item["property"]
            for item in response
        ):
            raise DeLonghiProtocolError("De'Longhi returned an invalid property list")
        return response

    async def _request(
        self, method: str, path: str, data: dict[str, Any] | None = None
    ) -> Any:
        """Retry an expired session once and propagate sanitized failures."""
        if not self.access_token:
            async with self._auth_lock:
                if not self.access_token:
                    self.access_token = await self._get_new_access_token()
        try:
            for attempt in range(2):
                token = self.access_token
                headers = {
                    "User-Agent": API_USER_AGENT,
                    "Authorization": f"auth_token {token}",
                    "Accept": "application/json",
                }
                async with self.session.request(
                    method,
                    f"https://ads-eu.aylanetworks.com/{path}",
                    headers=headers,
                    json=data,
                    timeout=_REQUEST_TIMEOUT,
                ) as response:
                    if response.status != 401 or attempt:
                        result = await self._read_json(response)
                        if method == "POST" and not isinstance(result, dict):
                            raise DeLonghiProtocolError("De'Longhi returned an invalid command response")
                        return result
                async with self._auth_lock:
                    if self.access_token == token:
                        self.access_token = await self.refresh_access_token()
        except (aiohttp.ClientError, TimeoutError):
            raise DeLonghiConnectionError("Unable to communicate with De'Longhi service") from None

    async def _get_request(self, path: str) -> Any:
        """Make a GET request to the API."""
        return await self._request("GET", path)

    async def _post_request(
        self, path: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Make a POST request to the API."""
        return await self._request("POST", path, data)

    async def set_device_property(self, dsn: str, propName: str, value: Any) -> bool:
        """Set a device property by DSN and property name."""
        await self._post_request(
            f"apiv1/dsns/{dsn}/properties/{propName}/datapoints.json",
            {"datapoint": {"value": value}},
        )
        return True
