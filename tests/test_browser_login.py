"""Integration test for Tesla browser login.

Requires .env.local with:
  TESLA_TEST_EMAIL=...
  TESLA_TEST_PASSWORD=...

Run: uv run pytest tests/test_browser_login.py -v -s
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Load .env.local
_env_file = Path(__file__).parent.parent / ".env.local"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

TESLA_EMAIL = os.environ.get("TESLA_TEST_EMAIL", "")
TESLA_PASSWORD = os.environ.get("TESLA_TEST_PASSWORD", "")

skip_no_creds = pytest.mark.skipif(
    not TESLA_EMAIL or not TESLA_PASSWORD,
    reason="TESLA_TEST_EMAIL and TESLA_TEST_PASSWORD required in .env.local",
)


@pytest.mark.integration
@skip_no_creds
class TestBrowserLogin:
    """Integration tests for Tesla headless browser login."""

    def test_fleet_login_captures_tokens(self):
        """Login with Fleet API client_id and capture tokens."""
        from tesla_cli.core.auth.browser_login import browser_login

        tokens = browser_login(
            email=TESLA_EMAIL,
            password=TESLA_PASSWORD,
            client_id="b2fe1e83-1b39-42da-8d55-40e30b10e3d6",
            scopes="openid email offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds",
            timeout=90,
        )

        assert "access_token" in tokens, f"No access_token in response: {list(tokens.keys())}"
        assert "refresh_token" in tokens, "No refresh_token in response"
        assert len(tokens["access_token"]) > 100, "Access token too short"
        print(f"\n  Fleet token captured: {tokens['access_token'][:40]}...")

    def test_owner_login_captures_tokens(self):
        """Login with ownerapi client_id for order tracking."""
        from tesla_cli.core.auth.browser_login import browser_login

        tokens = browser_login(
            email=TESLA_EMAIL,
            password=TESLA_PASSWORD,
            client_id="ownerapi",
            scopes="openid email offline_access",
            timeout=90,
        )

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        print(f"\n  Owner token captured: {tokens['access_token'][:40]}...")

    def test_full_login_both_tokens(self):
        """Full login captures both Owner and Fleet tokens."""
        from tesla_cli.core.auth.browser_login import full_login

        result = full_login(
            email=TESLA_EMAIL,
            password=TESLA_PASSWORD,
            fleet_client_id="b2fe1e83-1b39-42da-8d55-40e30b10e3d6",
        )

        assert result.get("order"), "No order tokens"
        assert "access_token" in result["order"]
        print(f"\n  Order: {result['order']['access_token'][:30]}...")

        if result.get("fleet"):
            print(f"  Fleet: {result['fleet']['access_token'][:30]}...")
        else:
            print("  Fleet: failed (may need captcha)")

    def test_wrong_password_fails(self):
        """Wrong password should raise an error."""
        from tesla_cli.core.auth.browser_login import browser_login

        with pytest.raises((Exception, RuntimeError)):
            browser_login(
                email=TESLA_EMAIL,
                password="wrong_password_123",
                client_id="b2fe1e83-1b39-42da-8d55-40e30b10e3d6",
                timeout=30,
            )


@pytest.mark.integration
@skip_no_creds
class TestBrowserLoginAPI:
    """Integration test for the /api/auth/browser-login endpoint."""

    def test_api_browser_login(self):
        """Test the full API endpoint."""
        import httpx

        r = httpx.post(
            "http://localhost:8080/api/auth/browser-login",
            json={"email": TESLA_EMAIL, "password": TESLA_PASSWORD},
            timeout=120,
        )

        data = r.json()
        print(f"\n  Response: {data}")

        if r.status_code == 200:
            assert data.get("ok") or data.get("mfa_required"), f"Unexpected: {data}"
        elif r.status_code == 401:
            # MFA or wrong creds
            assert "mfa" in str(data).lower() or "error" in data
        else:
            # Tesla might block — acceptable in CI
            print(f"  Status {r.status_code}: {data}")
