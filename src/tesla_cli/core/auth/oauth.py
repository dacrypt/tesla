"""Tesla OAuth2 + PKCE authentication flow.

Two methods:
1. PKCE flow with Tesla's void callback — user copies redirect URL back to terminal
2. Direct refresh token — user pastes token obtained elsewhere (browser, TeslaMate, etc.)

Used for order tracking auth and Fleet API auth.

Note on the ownership portal (client_id='ownership'):
Tesla's ownership portal uses a server-side callback redirect_uri that
auto-consumes the auth code, making PKCE impossible from a CLI.
The void callback is NOT registered for the ownership client_id.
Delivery data is instead obtained via browser scraping (see order.py).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
from typing import Any

import httpx

from tesla_cli.core.exceptions import AuthenticationError

# Tesla OAuth2 endpoints
AUTH_BASE = "https://auth.tesla.com/oauth2/v3"
AUTHORIZE_URL = f"{AUTH_BASE}/authorize"
TOKEN_URL = f"{AUTH_BASE}/token"

# Tesla's registered void callback (works with ownerapi client_id)
VOID_REDIRECT_URI = "https://auth.tesla.com/void/callback"

# Tesla app client IDs
DEFAULT_CLIENT_ID = "ownerapi"
DEFAULT_SCOPES = "openid email offline_access"

# Fleet API scopes — request every scope tesla-cli can use, so the token
# covers vehicle reads, commands, location, charging, Powerwall/solar reads
# and commands, and account profile. Individual backends still honour
# whatever the user's Tesla Developer app has enabled, but asking for more
# than the app provides is a no-op, not an error.
#
# vehicle_location was split out of vehicle_device_data in late 2024 for GPS
# privacy; without it /api/1/vehicles/{vin}/vehicle_data silently drops
# drive_state (including latitude/longitude) from the response.
FLEET_SCOPES = (
    "openid email offline_access "
    "user_data "
    "vehicle_device_data vehicle_location "
    "vehicle_cmds vehicle_charging_cmds "
    "energy_device_data energy_cmds"
)


def build_pkce_authorization(
    client_id: str | None = None,
    scopes: str | None = None,
    redirect_uri: str = VOID_REDIRECT_URI,
) -> tuple[str, str, str]:
    """Return ``(auth_url, code_verifier, state)`` for an OAuth2 + PKCE login."""
    client_id = client_id or DEFAULT_CLIENT_ID
    scopes = scopes or DEFAULT_SCOPES
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}", verifier, state


def complete_pkce_login(
    redirect_url_or_code: str, client_id: str | None, verifier: str
) -> dict[str, Any]:
    """Exchange the pasted redirect URL (or bare code) for tokens."""
    if not redirect_url_or_code.strip():
        raise AuthenticationError("No URL provided.")
    code = _extract_code_from_url(redirect_url_or_code.strip())
    return _exchange_code(code, client_id or DEFAULT_CLIENT_ID, verifier, VOID_REDIRECT_URI)


def login_with_refresh_token(token: str, client_id: str | None = None) -> dict[str, Any]:
    """Validate a user-supplied refresh token and return the token set."""
    token = token.strip()
    if not token:
        raise AuthenticationError("No token provided.")
    try:
        token_data = refresh_access_token(token, client_id)
    except httpx.HTTPStatusError as e:
        raise AuthenticationError(f"Invalid token: {e.response.status_code} {e.response.text}")
    if "refresh_token" not in token_data:
        token_data["refresh_token"] = token
    return token_data


def _extract_code_from_url(url: str) -> str:
    """Extract the authorization code from a redirect URL or raw code."""
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)

    if "code" in qs:
        return qs["code"][0]

    # Maybe they pasted just the code
    if url.startswith("NA_") or len(url) > 40:
        return url

    raise AuthenticationError(
        "No se encontró el código en la URL.\n"
        "Asegúrate de copiar la URL completa de la barra de direcciones."
    )


def _exchange_code(code: str, client_id: str, verifier: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(TOKEN_URL, data=payload)
        if resp.status_code != 200:
            raise AuthenticationError(f"Token exchange failed: {resp.status_code}\n{resp.text}")
        return resp.json()


def get_client_credentials_token(
    client_id: str,
    client_secret: str,
    scopes: str | None = None,
) -> dict[str, Any]:
    """Get an access token via client_credentials grant (server-to-server, no user).

    Required for Fleet API partner registration.
    """
    scopes = scopes or "openid vehicle_device_data vehicle_cmds vehicle_charging_cmds"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scopes,
        "audience": "https://fleet-api.prd.na.vn.cloud.tesla.com",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(TOKEN_URL, data=payload)
        if resp.status_code != 200:
            raise AuthenticationError(
                f"Error obteniendo client_credentials token: {resp.status_code}\n{resp.text}"
            )
        return resp.json()


def register_fleet_partner(
    client_id: str,
    client_secret: str,
    region: str = "na",
) -> dict[str, Any]:
    """Register partner account in a Fleet API region (one-time per app per region).

    Tesla requires this before any user can use the Fleet API with the app.
    Calls POST /api/1/partner_accounts with the app's registered domain.
    """
    from tesla_cli.core.backends.fleet import FLEET_API_REGIONS

    base_url = FLEET_API_REGIONS.get(region, FLEET_API_REGIONS["na"])

    # Get client_credentials token (not user token)
    token_data = get_client_credentials_token(client_id, client_secret)
    access_token = token_data["access_token"]

    # Load registered domain from config
    from tesla_cli.core.config import load_config

    cfg = load_config()
    raw_domain = getattr(cfg.fleet, "domain", None) or ""
    # Strip any https:// prefix — Tesla expects bare domain (e.g. mytesla.example.com)
    domain = raw_domain.removeprefix("https://").removeprefix("http://").rstrip("/")
    if not domain:
        raise AuthenticationError(
            "No fleet domain configured. Set one with:\n"
            "  tesla config set fleet-domain <your-domain>\n"
            "The domain must serve your app's public key at\n"
            "  https://<domain>/.well-known/appspecific/com.tesla.3p.public-key.pem\n"
            "See docs/fleet-signed-setup.md for setup options."
        )

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{base_url}/api/1/partner_accounts",
            json={"domain": domain},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code not in (200, 204):
            raise AuthenticationError(
                f"Partner registration failed: {resp.status_code}\n{resp.text}"
            )
        return resp.json() if resp.content else {"registered": True}


def refresh_access_token(refresh_token: str, client_id: str | None = None) -> dict[str, Any]:
    """Use a refresh token to get a new access token."""
    client_id = client_id or DEFAULT_CLIENT_ID
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(TOKEN_URL, data=payload)
        resp.raise_for_status()
        return resp.json()
