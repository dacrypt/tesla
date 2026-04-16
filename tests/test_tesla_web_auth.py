"""Tests for Tesla web auth manual-step helpers."""

from __future__ import annotations

from tesla_cli.core.auth.tesla_web_auth import needs_manual_tesla_interaction


def test_needs_manual_tesla_interaction_for_passcode_page():
    assert needs_manual_tesla_interaction(
        "https://auth.tesla.com/oauth2/v3/authorize",
        "Enter the passcode from your authenticator app",
    )


def test_needs_manual_tesla_interaction_for_captcha_page():
    assert needs_manual_tesla_interaction(
        "https://auth.tesla.com/oauth2/v3/authorize",
        "Please complete the captcha security check",
    )


def test_needs_manual_tesla_interaction_false_outside_auth_domain():
    assert not needs_manual_tesla_interaction(
        "https://www.tesla.com/teslaaccount",
        "passcode required",
    )
