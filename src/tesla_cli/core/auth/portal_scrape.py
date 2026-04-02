"""Tesla ownership portal scraper.

Logs into tesla.com/teslaaccount via patchright, navigates to order details,
and extracts window.Tesla.App.* data (delivery, registration, documents, etc.)

This is the ONLY way to get detailed order data that the Tesla mobile app shows
(documents, registration status, financing details, delivery specifics).
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("tesla-cli.portal-scrape")


def scrape_portal(
    email: str,
    password: str,
    mfa_code: str | None = None,
    reservation_number: str = "",
    timeout: int = 90,
) -> dict[str, Any]:
    """Login to Tesla portal and extract all order/account data.

    Returns dict with all window.Tesla.App.* data found.
    """
    from patchright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            # 1. Navigate to account
            log.info("Opening Tesla account page...")
            page.goto("https://www.tesla.com/teslaaccount", timeout=timeout * 1000)
            page.wait_for_timeout(3000)

            # 2. Login if needed
            if "auth.tesla.com" in page.url:
                log.info("Logging in...")
                email_el = page.wait_for_selector("input#identity", timeout=15000)
                if email_el:
                    email_el.fill(email)
                next_btn = page.query_selector('button:has-text("Next")')
                if next_btn:
                    next_btn.click()
                page.wait_for_timeout(3000)

                pwd_el = page.wait_for_selector(
                    'input#credential, input[type="password"]', timeout=10000
                )
                if pwd_el:
                    pwd_el.fill(password)
                submit = page.query_selector('button:has-text("Sign In"), button[type="submit"]')
                if submit:
                    submit.click()
                page.wait_for_timeout(5000)

                # MFA
                page_text = page.text_content("body") or ""
                if "auth.tesla.com" in page.url or "passcode" in page_text.lower():
                    if mfa_code:
                        log.info("Filling MFA code...")
                        mfa_el = page.query_selector("input#credential, input[name='credential']")
                        if mfa_el:
                            mfa_el.fill(mfa_code)
                            verify = page.query_selector(
                                'button:has-text("Verify"), button:has-text("Submit"), button[type="submit"]'
                            )
                            if verify:
                                verify.click()
                            page.wait_for_timeout(10000)
                    else:
                        browser.close()
                        raise Exception("MFA_REQUIRED")

            # 3. Navigate to order details
            if reservation_number:
                log.info("Navigating to order details...")
                page.goto(
                    f"https://www.tesla.com/teslaaccount/order-details/{reservation_number}",
                    timeout=30000,
                )
                page.wait_for_timeout(8000)

            # 4. Extract ALL Tesla.App data
            log.info("Extracting portal data...")
            data = page.evaluate("""() => {
                const result = {};
                if (window.Tesla && window.Tesla.App) {
                    for (const [key, value] of Object.entries(window.Tesla.App)) {
                        try { result[key] = JSON.parse(JSON.stringify(value)); } catch {}
                    }
                }
                if (window.__NEXT_DATA__) {
                    try { result.__NEXT_DATA__ = window.__NEXT_DATA__.props?.pageProps; } catch {}
                }
                return result;
            }""")

            log.info("Extracted %d data sections from portal.", len(data))
            browser.close()
            return data

        except Exception:
            try:
                browser.close()
            except Exception:
                pass
            raise
