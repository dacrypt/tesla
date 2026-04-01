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
import webbrowser
from typing import Any

import httpx
from rich.prompt import Prompt

from tesla_cli.exceptions import AuthenticationError
from tesla_cli.output import console

# Tesla OAuth2 endpoints
AUTH_BASE = "https://auth.tesla.com/oauth2/v3"
AUTHORIZE_URL = f"{AUTH_BASE}/authorize"
TOKEN_URL = f"{AUTH_BASE}/token"

# Tesla's registered void callback (works with ownerapi client_id)
VOID_REDIRECT_URI = "https://auth.tesla.com/void/callback"

# Tesla app client IDs
DEFAULT_CLIENT_ID = "ownerapi"
DEFAULT_SCOPES = "openid email offline_access"


def run_tesla_oauth_flow(
    client_id: str | None = None,
    scopes: str | None = None,
) -> dict[str, Any]:
    """Run Tesla auth. Returns dict with access_token and refresh_token."""
    console.print(
        "\n[bold]Tesla Authentication[/bold]\n"
        "\nElige método:\n"
        "  [cyan]1[/cyan] - Login via browser (OAuth2 + PKCE)\n"
        "  [cyan]2[/cyan] - Pegar refresh token directamente\n"
    )
    method = Prompt.ask("Método", choices=["1", "2"], default="1")

    if method == "1":
        return _oauth_pkce_flow(client_id, scopes)
    else:
        return _refresh_token_flow(client_id)


def _oauth_pkce_flow(
    client_id: str | None = None,
    scopes: str | None = None,
) -> dict[str, Any]:
    """OAuth2 + PKCE flow using Tesla's void callback.

    1. Opens browser for Tesla login
    2. Tesla redirects to a void page with ?code= in the URL
    3. User copies that URL and pastes it here
    4. We extract the code and exchange it for tokens
    """
    client_id = client_id or DEFAULT_CLIENT_ID
    scopes = scopes or DEFAULT_SCOPES

    # Generate PKCE verifier and challenge
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": VOID_REDIRECT_URI,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    console.print("\n[bold]Abriendo browser para login de Tesla...[/bold]")
    console.print(
        "\nDespués de hacer login, Tesla te redirige a una página en blanco.\n"
        "[bold yellow]Copia la URL completa de esa página[/bold yellow] y pégala aquí.\n"
        "La URL se ve algo así: https://auth.tesla.com/void/callback?code=...&state=...\n"
    )
    webbrowser.open(auth_url)

    # User pastes the redirect URL
    redirect_url = Prompt.ask("\nPega la URL de redirect aquí")
    if not redirect_url.strip():
        raise AuthenticationError("No URL provided.")

    code = _extract_code_from_url(redirect_url.strip())

    # Exchange code for tokens
    console.print("[dim]Intercambiando código por tokens...[/dim]")
    return _exchange_code(code, client_id, verifier, VOID_REDIRECT_URI)


def _refresh_token_flow(client_id: str | None = None) -> dict[str, Any]:
    """User provides a refresh token directly.

    How to get a refresh token:
    1. Go to tesla.com and login
    2. Open browser DevTools (F12) → Network tab
    3. Look for requests to auth.tesla.com with token responses
    4. Or use another tool (TeslaMate, Tessie, etc.) to export it
    """
    console.print(
        "\n[bold]Refresh Token Directo[/bold]\n"
        "\nCómo obtener tu refresh token:\n"
        "  1. Ve a [link=https://tesla.com]tesla.com[/link] y haz login\n"
        "  2. Abre DevTools (F12) → pestaña Network\n"
        "  3. Busca requests a auth.tesla.com que contengan tokens\n"
        "  4. O expórtalo desde TeslaMate, Tessie, u otra herramienta\n"
    )
    token = Prompt.ask("Refresh token", password=True)
    if not token.strip():
        raise AuthenticationError("No token provided.")

    # Validate by refreshing
    console.print("[dim]Validando refresh token...[/dim]")
    try:
        token_data = refresh_access_token(token.strip(), client_id)
    except httpx.HTTPStatusError as e:
        raise AuthenticationError(f"Token inválido: {e.response.status_code} {e.response.text}")

    # Return with the original refresh token included
    if "refresh_token" not in token_data:
        token_data["refresh_token"] = token.strip()

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


def _exchange_code(
    code: str, client_id: str, verifier: str, redirect_uri: str
) -> dict[str, Any]:
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
            raise AuthenticationError(
                f"Error intercambiando código: {resp.status_code}\n{resp.text}"
            )
        return resp.json()


def refresh_access_token(
    refresh_token: str, client_id: str | None = None
) -> dict[str, Any]:
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
