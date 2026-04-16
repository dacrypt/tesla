"""Helpers for Tesla web auth flows that may require manual user interaction."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

MANUAL_MARKERS = (
    "passcode",
    "verification code",
    "verification",
    "captcha",
    "security check",
    "human",
    "robot",
    "challenge",
)


def get_page_text(page: Any) -> str:
    """Best-effort body text extraction from a Playwright page."""
    try:
        return page.text_content("body") or ""
    except Exception:
        return ""


def needs_manual_tesla_interaction(url: str, page_text: str) -> bool:
    """Detect whether Tesla is asking the user to solve MFA/captcha manually."""
    if "auth.tesla.com" not in (url or ""):
        return False
    normalized = (page_text or "").lower()
    return any(marker in normalized for marker in MANUAL_MARKERS)


def wait_for_manual_tesla_interaction(
    *,
    page: Any,
    success_check: Callable[[], bool],
    timeout_seconds: int,
    log: logging.Logger,
    context: str,
) -> bool:
    """Keep the visible browser open while the user solves MFA/captcha."""
    deadline = time.monotonic() + timeout_seconds
    warned = False
    while time.monotonic() < deadline:
        if success_check():
            return True
        url = getattr(page, "url", "")
        if not warned and needs_manual_tesla_interaction(url, get_page_text(page)):
            warned = True
            log.warning(
                "Manual Tesla auth step detected for %s. Complete it in the visible browser window; waiting up to %ss.",
                context,
                timeout_seconds,
            )
        try:
            page.wait_for_timeout(2000)
        except Exception:
            time.sleep(2)
    return success_check()
