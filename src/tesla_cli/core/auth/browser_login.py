"""Automated Tesla login via headless browser (patchright).

Uses patchright (undetectable Playwright fork) to automate Tesla OAuth.
Tesla uses hCaptcha on the login page — patchright can sometimes bypass it
due to its undetectable nature, but it may fail if hCaptcha triggers.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
import urllib.parse
from typing import Any

import httpx

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
    timeout: int = 90,
) -> dict[str, Any]:
    """Automate Tesla login in browser via patchright.

    Returns: {access_token, refresh_token, token_type, expires_in}
    """
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
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            log.info("Opening Tesla login...")
            page.goto(auth_url, timeout=timeout * 1000)

            # Wait for email input
            log.info("Waiting for email field...")
            email_input = page.wait_for_selector('input#identity, input[name="identity"]', timeout=20000)
            if not email_input:
                raise Exception("Email input not found")

            # Fill email
            email_input.fill(email)
            page.wait_for_timeout(500)

            # Click Next
            next_btn = page.query_selector('button:has-text("Next")')
            if next_btn and next_btn.is_visible():
                next_btn.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_timeout(3000)

            # Wait for password field
            log.info("Waiting for password field...")
            password_input = page.wait_for_selector(
                'input#credential, input[name="credential"], input[type="password"]',
                timeout=15000,
            )
            if not password_input:
                raise Exception("Password input not found")

            password_input.fill(password)
            page.wait_for_timeout(500)

            # Submit
            submit_btn = page.query_selector('button:has-text("Sign In"), button:has-text("Submit"), button[type="submit"]')
            if submit_btn and submit_btn.is_visible():
                submit_btn.click()
            else:
                page.keyboard.press("Enter")

            # Wait for result
            log.info("Waiting for auth result...")
            deadline = time.monotonic() + timeout

            while time.monotonic() < deadline:
                url = page.url

                # Success
                if "void/callback" in url and "code=" in url:
                    parsed = urllib.parse.urlparse(url)
                    qs = urllib.parse.parse_qs(parsed.query)
                    code = qs.get("code", [""])[0]
                    if code:
                        log.info("Auth code captured!")
                        browser.close()
                        return _exchange_code(code, client_id, verifier)

                # MFA
                mfa_el = page.query_selector('input#credential, input[name="credential"]')
                page_text = page.text_content("body") or ""
                if mfa_el and mfa_el.is_visible() and ("passcode" in page_text.lower() or "verification" in page_text.lower()):
                    if mfa_code:
                        log.info("Filling MFA...")
                        mfa_el.fill(mfa_code)
                        btn = page.query_selector('button:has-text("Verify"), button:has-text("Submit"), button[type="submit"]')
                        if btn:
                            btn.click()
                        page.wait_for_timeout(3000)
                    else:
                        browser.close()
                        raise Exception("MFA_REQUIRED")

                # Check for error messages
                for sel in ['.error-message', '.form-error', '[class*="error"]', '[class*="Error"]']:
                    err_el = page.query_selector(sel)
                    if err_el and err_el.is_visible():
                        txt = err_el.inner_text().strip()
                        if txt and len(txt) > 5 and "captcha" not in txt.lower():
                            browser.close()
                            raise Exception(f"Tesla: {txt}")

                page.wait_for_timeout(2000)

            browser.close()
            raise Exception("Login timed out. Tesla may require manual captcha completion.")

        except Exception:
            try:
                browser.close()
            except Exception:
                pass
            raise


def _exchange_code(code: str, client_id: str, verifier: str) -> dict[str, Any]:
    """Exchange auth code for tokens."""
    r = httpx.post(TESLA_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": VOID_CALLBACK,
    }, timeout=30)
    r.raise_for_status()
    return r.json()


def full_login(
    email: str,
    password: str,
    mfa_code: str | None = None,
    fleet_client_id: str | None = None,
) -> dict[str, Any]:
    """Get both Owner API and Fleet API tokens in one flow."""
    result: dict[str, Any] = {"email": email}

    # Owner API token (for orders)
    log.info("Getting Owner API token...")
    order_tokens = browser_login(
        email, password, mfa_code,
        client_id="ownerapi",
        scopes="openid email offline_access",
    )
    result["order"] = order_tokens

    # Fleet API token (for vehicle data)
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
            log.warning("Fleet token failed: %s", exc)
            result["fleet"] = None
    else:
        result["fleet"] = None

    return result
