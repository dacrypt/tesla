"""Interactive Tesla auth capture via visible browser.

This flow does not persist Tesla account credentials. It opens Tesla's real
auth forms in a visible browser, the user completes login / MFA / captcha,
and we capture the resulting tokens plus portal session state.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import urllib.parse
from typing import Any

import httpx

from tesla_cli.core.auth.portal_scrape import capture_portal_session_and_data
from tesla_cli.core.auth.tesla_web_auth import wait_for_manual_tesla_interaction

log = logging.getLogger("tesla-cli.browser-login")

TESLA_AUTH_URL = "https://auth.tesla.com/oauth2/v3/authorize"
TESLA_TOKEN_URL = "https://auth.tesla.com/oauth2/v3/token"
VOID_CALLBACK = "https://auth.tesla.com/void/callback"


def _build_auth_url(client_id: str, scopes: str) -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    state = secrets.token_urlsafe(32)
    auth_url = f"{TESLA_AUTH_URL}?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": VOID_CALLBACK,
            "response_type": "code",
            "scope": scopes,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return auth_url, verifier


def _exchange_code(code: str, client_id: str, verifier: str) -> dict[str, Any]:
    r = httpx.post(
        TESLA_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": VOID_CALLBACK,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _capture_auth_code(page: Any, auth_url: str, context_label: str, timeout: int = 300) -> str:
    page.goto(auth_url, timeout=timeout * 1000)
    if wait_for_manual_tesla_interaction(
        page=page,
        success_check=lambda: "void/callback" in page.url and "code=" in page.url,
        timeout_seconds=timeout,
        log=log,
        context=context_label,
    ):
        parsed = urllib.parse.urlparse(page.url)
        code = urllib.parse.parse_qs(parsed.query).get("code", [""])[0]
        if code:
            return code
    raise RuntimeError(
        f"{context_label} timed out. Complete Tesla login / MFA / captcha in the visible browser window and retry."
    )


def interactive_login_and_capture(
    *,
    fleet_client_id: str | None = None,
    reservation_number: str = "",
    timeout: int = 420,
) -> dict[str, Any]:
    """Capture owner tokens, optional fleet tokens, and portal session interactively."""
    from patchright.sync_api import sync_playwright

    result: dict[str, Any] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        try:
            owner_url, owner_verifier = _build_auth_url("ownerapi", "openid email offline_access")
            owner_code = _capture_auth_code(page, owner_url, "Tesla owner login", timeout=timeout)
            result["order"] = _exchange_code(owner_code, "ownerapi", owner_verifier)

            if fleet_client_id:
                fleet_url, fleet_verifier = _build_auth_url(
                    fleet_client_id,
                    "openid email offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds",
                )
                fleet_code = _capture_auth_code(
                    page, fleet_url, "Tesla fleet login", timeout=timeout
                )
                result["fleet"] = _exchange_code(fleet_code, fleet_client_id, fleet_verifier)
            else:
                result["fleet"] = None

            portal_data, storage_state = capture_portal_session_and_data(
                context=context,
                page=page,
                reservation_number=reservation_number,
                timeout=timeout,
            )
            result["portal"] = portal_data
            result["portal_storage_state"] = storage_state
            result["portal_sections"] = len(portal_data)
            result["portal_keys"] = list(portal_data.keys())

            return result
        finally:
            try:
                browser.close()
            except Exception:
                pass


def browser_login(
    email: str | None = None,
    password: str | None = None,
    mfa_code: str | None = None,
    client_id: str = "ownerapi",
    scopes: str = "openid email offline_access",
    timeout: int = 90,
) -> dict[str, Any]:
    """Backward-compatible wrapper kept for old integration tests.

    It now opens the browser and lets the user complete Tesla auth manually.
    """
    del email, password, mfa_code
    from patchright.sync_api import sync_playwright

    auth_url, verifier = _build_auth_url(client_id, scopes)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        try:
            code = _capture_auth_code(page, auth_url, "Tesla auth", timeout=timeout)
            return _exchange_code(code, client_id, verifier)
        finally:
            try:
                browser.close()
            except Exception:
                pass


def full_login(
    email: str | None = None,
    password: str | None = None,
    mfa_code: str | None = None,
    fleet_client_id: str | None = None,
    reservation_number: str = "",
) -> dict[str, Any]:
    """Backward-compatible entrypoint for existing callers."""
    del email, password, mfa_code
    return interactive_login_and_capture(
        fleet_client_id=fleet_client_id,
        reservation_number=reservation_number,
    )
