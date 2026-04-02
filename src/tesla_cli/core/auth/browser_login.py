"""Automated Tesla login via headless browser (patchright).

The user provides email + password in our app. We automate the full
Tesla OAuth login flow in a headless browser, capturing both the
Owner API token (for orders) and Fleet API token (for vehicle data).

Uses patchright (undetectable Playwright fork) to avoid bot detection.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

log = logging.getLogger("tesla-cli.browser-login")

TESLA_AUTH_URL = "https://auth.tesla.com/oauth2/v3/authorize"
TESLA_TOKEN_URL = "https://auth.tesla.com/oauth2/v3/token"
VOID_CALLBACK = "https://auth.tesla.com/void/callback"


def browser_login(
    email: str,
    password: str,
    mfa_code: str | None = None,
    client_id: str = "ownerapi",
    scopes: str = "openid email offline_access",
    timeout: int = 60,
) -> dict[str, Any]:
    """Automate Tesla login in headless browser.

    Returns: {access_token, refresh_token, token_type, expires_in, id_token}
    Raises: Exception on failure with descriptive message.
    """
    import hashlib
    import secrets
    import base64
    import urllib.parse

    from patchright.sync_api import sync_playwright

    # PKCE
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(32)

    auth_url = f"{TESLA_AUTH_URL}?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": VOID_CALLBACK,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            # Navigate to Tesla auth
            log.info("Opening Tesla login page...")
            page.goto(auth_url, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(2000)

            # Fill email
            log.info("Filling email...")
            email_input = page.wait_for_selector('input#form-input-identity', timeout=15000)
            if not email_input:
                raise Exception("Email input not found on Tesla login page")
            email_input.fill(email)
            page.wait_for_timeout(500)

            # Click "Next" or submit
            submit_btn = page.query_selector('button[type="submit"], button#form-submit-continue')
            if submit_btn:
                submit_btn.click()
                page.wait_for_timeout(2000)

            # Fill password
            log.info("Filling password...")
            password_input = page.wait_for_selector('input#form-input-credential', timeout=10000)
            if not password_input:
                raise Exception("Password input not found")
            password_input.fill(password)
            page.wait_for_timeout(500)

            # Submit login
            submit_btn = page.query_selector('button[type="submit"], button#form-submit-continue')
            if submit_btn:
                submit_btn.click()

            # Wait for redirect or MFA
            log.info("Waiting for auth result...")
            deadline = time.monotonic() + timeout

            while time.monotonic() < deadline:
                current_url = page.url

                # Success: redirected to void/callback with code
                if "void/callback" in current_url and "code=" in current_url:
                    parsed = urllib.parse.urlparse(current_url)
                    qs = urllib.parse.parse_qs(parsed.query)
                    code = qs.get("code", [""])[0]
                    if code:
                        log.info("Auth code captured!")
                        browser.close()
                        return _exchange_code(code, client_id, verifier)

                # MFA required
                mfa_input = page.query_selector('input[name="credential"], input#form-input-credential')
                if mfa_input and "passcode" in (page.content() or "").lower():
                    if mfa_code:
                        log.info("Filling MFA code...")
                        mfa_input.fill(mfa_code)
                        submit = page.query_selector('button[type="submit"]')
                        if submit:
                            submit.click()
                        page.wait_for_timeout(3000)
                    else:
                        browser.close()
                        raise Exception("MFA_REQUIRED")

                # Error on page
                error_el = page.query_selector('.error-message, .form-error, [data-testid="error"]')
                if error_el:
                    error_text = error_el.inner_text()
                    if error_text.strip():
                        browser.close()
                        raise Exception(f"Tesla login error: {error_text.strip()}")

                page.wait_for_timeout(1000)

            browser.close()
            raise Exception("Login timed out. Check credentials or try again.")

        except Exception:
            try:
                browser.close()
            except Exception:
                pass
            raise


def _exchange_code(code: str, client_id: str, verifier: str) -> dict[str, Any]:
    """Exchange auth code for tokens."""
    import httpx
    r = httpx.post(TESLA_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": VOID_CALLBACK,
    }, timeout=30)
    r.raise_for_status()
    return r.json()


def full_login(email: str, password: str, mfa_code: str | None = None, fleet_client_id: str | None = None) -> dict[str, Any]:
    """Full login: get both Owner API and Fleet API tokens.

    Returns: {
        order: {access_token, refresh_token, ...},
        fleet: {access_token, refresh_token, ...} | None,
        email: str,
    }
    """
    result: dict[str, Any] = {"email": email}

    # Step 1: Owner API token (for orders)
    log.info("Getting Owner API token...")
    order_tokens = browser_login(
        email, password, mfa_code,
        client_id="ownerapi",
        scopes="openid email offline_access",
    )
    result["order"] = order_tokens

    # Step 2: Fleet API token (for vehicle data) — if we have a client_id
    if fleet_client_id:
        log.info("Getting Fleet API token...")
        try:
            fleet_tokens = browser_login(
                email, password, mfa_code,
                client_id=fleet_client_id,
                scopes="openid email offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds",
            )
            result["fleet"] = fleet_tokens
        except Exception as exc:
            log.warning("Fleet token failed (order token still valid): %s", exc)
            result["fleet"] = None
    else:
        result["fleet"] = None

    return result
