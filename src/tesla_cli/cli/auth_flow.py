"""Interactive Tesla OAuth login for the terminal (prompts + browser).

The protocol pieces live in ``core/auth/oauth.py``; this module only handles
user interaction, keeping ``core/`` free of CLI dependencies.
"""

from __future__ import annotations

import webbrowser
from typing import Any

from rich.prompt import Prompt

from tesla_cli.cli.output import console
from tesla_cli.core.auth.oauth import (
    build_pkce_authorization,
    complete_pkce_login,
    login_with_refresh_token,
)


def run_tesla_oauth_flow(
    client_id: str | None = None,
    scopes: str | None = None,
) -> dict[str, Any]:
    """Run Tesla auth. Returns dict with access_token and refresh_token."""
    console.print(
        "\n[bold]Tesla Authentication[/bold]\n"
        "\nChoose method:\n"
        "  [cyan]1[/cyan] - Login via browser (OAuth2 + PKCE)\n"
        "  [cyan]2[/cyan] - Paste refresh token directly\n"
    )
    method = Prompt.ask("Method", choices=["1", "2"], default="1")
    if method == "1":
        return _oauth_pkce_flow(client_id, scopes)
    return _refresh_token_flow(client_id)


def _oauth_pkce_flow(client_id: str | None = None, scopes: str | None = None) -> dict[str, Any]:
    """Open Tesla login; the user pastes back the void-callback URL."""
    auth_url, verifier, _state = build_pkce_authorization(client_id, scopes)
    console.print("\n[bold]Opening browser for Tesla login...[/bold]")
    console.print(
        "\nAfter logging in, Tesla will redirect you to a blank page.\n"
        "[bold yellow]Copy the full URL from that page[/bold yellow] and paste it here.\n"
        "The URL looks like: https://auth.tesla.com/void/callback?code=...&state=...\n"
    )
    webbrowser.open(auth_url)
    redirect_url = Prompt.ask("\nPaste the redirect URL here")
    console.print("[dim]Exchanging code for tokens...[/dim]")
    return complete_pkce_login(redirect_url, client_id, verifier)


def _refresh_token_flow(client_id: str | None = None) -> dict[str, Any]:
    """User provides a refresh token directly."""
    console.print(
        "\n[bold]Direct Refresh Token[/bold]\n"
        "\nHow to get your refresh token:\n"
        "  1. Go to [link=https://tesla.com]tesla.com[/link] and log in\n"
        "  2. Open DevTools (F12) → Network tab\n"
        "  3. Look for requests to auth.tesla.com that contain tokens\n"
        "  4. Or export it from TeslaMate, Tessie, or another tool\n"
    )
    token = Prompt.ask("Refresh token", password=True)
    console.print("[dim]Validating refresh token...[/dim]")
    return login_with_refresh_token(token, client_id)
