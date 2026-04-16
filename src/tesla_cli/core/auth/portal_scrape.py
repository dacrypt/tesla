"""Tesla ownership portal session capture and scrape helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from tesla_cli.core.auth.tesla_web_auth import get_page_text, wait_for_manual_tesla_interaction
from tesla_cli.core.config import CONFIG_DIR

log = logging.getLogger("tesla-cli.portal-scrape")

PORTAL_SESSION_FILE = CONFIG_DIR / "state" / "tesla_portal_storage.json"


def has_portal_session() -> bool:
    return PORTAL_SESSION_FILE.exists()


def save_portal_session(storage_state: dict[str, Any]) -> None:
    PORTAL_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORTAL_SESSION_FILE.write_text(json.dumps(storage_state, default=str, indent=2))
    PORTAL_SESSION_FILE.chmod(0o600)


def load_portal_session() -> dict[str, Any] | None:
    if not PORTAL_SESSION_FILE.exists():
        return None
    try:
        return json.loads(PORTAL_SESSION_FILE.read_text())
    except Exception:
        return None


def _extract_portal_data(page: Any) -> dict[str, Any]:
    return page.evaluate("""() => {
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


def capture_portal_session_and_data(
    *,
    context: Any,
    page: Any,
    reservation_number: str = "",
    timeout: int = 420,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture Tesla portal session and scrape data using an authenticated context."""
    portal_url = (
        f"https://www.tesla.com/teslaaccount/order-details/{reservation_number}"
        if reservation_number
        else "https://www.tesla.com/teslaaccount"
    )
    page.goto(portal_url, timeout=30000)
    if wait_for_manual_tesla_interaction(
        page=page,
        success_check=lambda: "auth.tesla.com" not in page.url,
        timeout_seconds=timeout,
        log=log,
        context="Tesla portal",
    ):
        page.wait_for_timeout(5000)
        data = _extract_portal_data(page)
        if not data:
            raise RuntimeError("Tesla portal loaded but no window.Tesla.App data was found.")
        storage_state = context.storage_state()
        return data, storage_state
    raise RuntimeError(
        "Tesla portal session capture timed out. Complete login/MFA/captcha in the visible browser window and retry."
    )


def scrape_portal_with_session(
    *,
    reservation_number: str = "",
    timeout: int = 90,
) -> dict[str, Any]:
    """Use a persisted Tesla portal session to refresh portal data without credentials."""
    from patchright.sync_api import sync_playwright

    storage_state = load_portal_session()
    if not storage_state:
        raise RuntimeError("No saved Tesla portal session. Start interactive Tesla auth first.")

    portal_url = (
        f"https://www.tesla.com/teslaaccount/order-details/{reservation_number}"
        if reservation_number
        else "https://www.tesla.com/teslaaccount"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=storage_state,
        )
        page = context.new_page()
        try:
            page.goto(portal_url, timeout=30000)
            if "auth.tesla.com" in page.url:
                raise RuntimeError("Tesla portal session expired. Start interactive Tesla auth again.")
            page.wait_for_timeout(min(timeout, 15) * 1000)
            data = _extract_portal_data(page)
            if not data:
                page_text = get_page_text(page)
                raise RuntimeError(
                    f"Tesla portal session loaded but no portal data was exposed. Page says: {page_text[:200]}"
                )
            save_portal_session(context.storage_state())
            return data
        finally:
            try:
                browser.close()
            except Exception:
                pass
