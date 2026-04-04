"""Tests for tesla_cli.core.auth modules (oauth, tokens, tessie).

Covers:
- oauth._extract_code_from_url
- oauth._exchange_code
- oauth.refresh_access_token
- oauth.get_client_credentials_token
- oauth.register_fleet_partner
- tokens.get_token / set_token / delete_token / has_token
- tessie.get_tessie_token
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# oauth._extract_code_from_url
# ---------------------------------------------------------------------------


class TestExtractCodeFromUrl:
    def test_full_redirect_url(self):
        from tesla_cli.core.auth.oauth import _extract_code_from_url

        url = "https://auth.tesla.com/void/callback?code=NA_ABC123&state=xyz"
        assert _extract_code_from_url(url) == "NA_ABC123"

    def test_multiple_query_params(self):
        from tesla_cli.core.auth.oauth import _extract_code_from_url

        url = "https://auth.tesla.com/void/callback?state=xyz&code=NA_DEF456&iss=auth.tesla.com"
        assert _extract_code_from_url(url) == "NA_DEF456"

    def test_raw_code_na_prefix(self):
        from tesla_cli.core.auth.oauth import _extract_code_from_url

        code = "NA_somereallylongauthcode"
        assert _extract_code_from_url(code) == code

    def test_raw_code_long_string(self):
        from tesla_cli.core.auth.oauth import _extract_code_from_url

        # Any string longer than 40 chars without a ?code= is returned as-is
        code = "a" * 41
        assert _extract_code_from_url(code) == code

    def test_short_invalid_string_raises(self):
        from tesla_cli.core.auth.oauth import _extract_code_from_url
        from tesla_cli.core.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            _extract_code_from_url("badcode")

    def test_url_without_code_param_raises(self):
        # URL has no ?code= and doesn't start with NA_ — but the URL itself is >40 chars so it
        # would be returned as-is by the raw-code branch. Use a short URL fragment instead.
        from tesla_cli.core.auth.oauth import _extract_code_from_url
        from tesla_cli.core.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            _extract_code_from_url("nocode")


# ---------------------------------------------------------------------------
# oauth._exchange_code
# ---------------------------------------------------------------------------


class TestExchangeCode:
    def test_success(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, VOID_REDIRECT_URI, _exchange_code

        token_response = {"access_token": "at_abc", "refresh_token": "rt_xyz", "expires_in": 3600}
        httpx_mock.add_response(url=TOKEN_URL, method="POST", json=token_response, status_code=200)

        result = _exchange_code("NA_CODE", "ownerapi", "verifier123", VOID_REDIRECT_URI)

        assert result["access_token"] == "at_abc"
        assert result["refresh_token"] == "rt_xyz"

    def test_failure_raises_authentication_error(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, VOID_REDIRECT_URI, _exchange_code
        from tesla_cli.core.exceptions import AuthenticationError

        httpx_mock.add_response(
            url=TOKEN_URL,
            method="POST",
            status_code=400,
            text="invalid_grant",
        )

        with pytest.raises(AuthenticationError, match="400"):
            _exchange_code("BAD_CODE", "ownerapi", "verifier123", VOID_REDIRECT_URI)

    def test_sends_correct_payload(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, VOID_REDIRECT_URI, _exchange_code

        httpx_mock.add_response(url=TOKEN_URL, method="POST", json={"access_token": "x"})

        _exchange_code("MY_CODE", "my_client", "my_verifier", VOID_REDIRECT_URI)

        request = httpx_mock.get_request()
        body = request.content.decode()
        assert "grant_type=authorization_code" in body
        assert "code=MY_CODE" in body
        assert "client_id=my_client" in body
        assert "code_verifier=my_verifier" in body


# ---------------------------------------------------------------------------
# oauth.refresh_access_token
# ---------------------------------------------------------------------------


class TestRefreshAccessToken:
    def test_success(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, refresh_access_token

        token_response = {"access_token": "new_at", "expires_in": 3600}
        httpx_mock.add_response(url=TOKEN_URL, method="POST", json=token_response, status_code=200)

        result = refresh_access_token("my_refresh_token")

        assert result["access_token"] == "new_at"

    def test_uses_default_client_id(self, httpx_mock):
        from tesla_cli.core.auth.oauth import DEFAULT_CLIENT_ID, TOKEN_URL, refresh_access_token

        httpx_mock.add_response(url=TOKEN_URL, method="POST", json={"access_token": "x"})

        refresh_access_token("rt_token")

        request = httpx_mock.get_request()
        body = request.content.decode()
        assert f"client_id={DEFAULT_CLIENT_ID}" in body

    def test_custom_client_id(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, refresh_access_token

        httpx_mock.add_response(url=TOKEN_URL, method="POST", json={"access_token": "x"})

        refresh_access_token("rt_token", client_id="custom_client")

        request = httpx_mock.get_request()
        body = request.content.decode()
        assert "client_id=custom_client" in body

    def test_failure_raises_http_status_error(self, httpx_mock):
        """refresh_access_token calls resp.raise_for_status(), so 401 raises HTTPStatusError."""
        import httpx as _httpx

        from tesla_cli.core.auth.oauth import TOKEN_URL, refresh_access_token

        httpx_mock.add_response(url=TOKEN_URL, method="POST", status_code=401, text="Unauthorized")

        with pytest.raises(_httpx.HTTPStatusError):
            refresh_access_token("bad_refresh_token")

    def test_sends_refresh_grant(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, refresh_access_token

        httpx_mock.add_response(url=TOKEN_URL, method="POST", json={"access_token": "x"})

        refresh_access_token("rt_abc")

        request = httpx_mock.get_request()
        body = request.content.decode()
        assert "grant_type=refresh_token" in body
        assert "refresh_token=rt_abc" in body


# ---------------------------------------------------------------------------
# oauth.get_client_credentials_token
# ---------------------------------------------------------------------------


class TestGetClientCredentialsToken:
    def test_success(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, get_client_credentials_token

        token_response = {"access_token": "cc_token", "token_type": "Bearer", "expires_in": 3600}
        httpx_mock.add_response(url=TOKEN_URL, method="POST", json=token_response, status_code=200)

        result = get_client_credentials_token("my_client_id", "my_secret")

        assert result["access_token"] == "cc_token"

    def test_sends_client_credentials_grant(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, get_client_credentials_token

        httpx_mock.add_response(url=TOKEN_URL, method="POST", json={"access_token": "x"})

        get_client_credentials_token("cid", "csecret", scopes="openid vehicle_device_data")

        request = httpx_mock.get_request()
        body = request.content.decode()
        assert "grant_type=client_credentials" in body
        assert "client_id=cid" in body
        assert "client_secret=csecret" in body

    def test_failure_raises_authentication_error(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, get_client_credentials_token
        from tesla_cli.core.exceptions import AuthenticationError

        httpx_mock.add_response(url=TOKEN_URL, method="POST", status_code=400, text="Bad Request")

        with pytest.raises(AuthenticationError, match="400"):
            get_client_credentials_token("cid", "csecret")

    def test_custom_scopes(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, get_client_credentials_token

        httpx_mock.add_response(url=TOKEN_URL, method="POST", json={"access_token": "x"})

        get_client_credentials_token("cid", "csecret", scopes="openid email")

        request = httpx_mock.get_request()
        body = request.content.decode()
        assert "scope=openid+email" in body or "scope=openid%20email" in body


# ---------------------------------------------------------------------------
# oauth.register_fleet_partner
# ---------------------------------------------------------------------------


PARTNER_URL = "https://fleet-api.prd.na.vn.cloud.tesla.com/api/1/partner_accounts"


class TestRegisterFleetPartner:
    def _mock_config(self):
        cfg = MagicMock()
        cfg.fleet.domain = "dacrypt.github.io"
        return cfg

    def test_success_returns_json(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, register_fleet_partner

        httpx_mock.add_response(
            url=TOKEN_URL,
            method="POST",
            json={"access_token": "cc_token"},
            status_code=200,
        )
        httpx_mock.add_response(
            url=PARTNER_URL,
            method="POST",
            json={"domain": "dacrypt.github.io", "registered": True},
            status_code=200,
        )

        with patch("tesla_cli.core.config.load_config", return_value=self._mock_config()):
            result = register_fleet_partner("cid", "csecret", region="na")

        assert result.get("registered") is True or "domain" in result

    def test_success_204_no_content(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, register_fleet_partner

        httpx_mock.add_response(
            url=TOKEN_URL,
            method="POST",
            json={"access_token": "cc_token"},
            status_code=200,
        )
        httpx_mock.add_response(
            url=PARTNER_URL,
            method="POST",
            status_code=204,
            content=b"",
        )

        with patch("tesla_cli.core.config.load_config", return_value=self._mock_config()):
            result = register_fleet_partner("cid", "csecret", region="na")

        assert result == {"registered": True}

    def test_partner_failure_raises_authentication_error(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, register_fleet_partner
        from tesla_cli.core.exceptions import AuthenticationError

        httpx_mock.add_response(
            url=TOKEN_URL,
            method="POST",
            json={"access_token": "cc_token"},
            status_code=200,
        )
        httpx_mock.add_response(
            url=PARTNER_URL,
            method="POST",
            status_code=422,
            text="Unprocessable Entity",
        )

        with patch("tesla_cli.core.config.load_config", return_value=self._mock_config()):
            with pytest.raises(AuthenticationError, match="422"):
                register_fleet_partner("cid", "csecret", region="na")

    def test_strips_https_prefix_from_domain(self, httpx_mock):
        from tesla_cli.core.auth.oauth import TOKEN_URL, register_fleet_partner

        httpx_mock.add_response(
            url=TOKEN_URL,
            method="POST",
            json={"access_token": "cc_token"},
            status_code=200,
        )
        httpx_mock.add_response(
            url=PARTNER_URL,
            method="POST",
            json={"registered": True},
            status_code=200,
        )

        cfg = MagicMock()
        cfg.fleet.domain = "https://dacrypt.github.io/"

        with patch("tesla_cli.core.config.load_config", return_value=cfg):
            register_fleet_partner("cid", "csecret", region="na")

        # Verify the partner_accounts request used the bare domain
        requests = httpx_mock.get_requests()
        partner_req = next(r for r in requests if "partner_accounts" in str(r.url))
        import json as _json

        body = _json.loads(partner_req.content)
        assert body["domain"] == "dacrypt.github.io"


# ---------------------------------------------------------------------------
# tokens.py
# ---------------------------------------------------------------------------


class TestGetToken:
    def test_returns_value_when_present(self):
        from tesla_cli.core.auth.tokens import SERVICE, get_token

        with patch("keyring.get_password", return_value="my_token") as mock_get:
            result = get_token("fleet-access-token")

        mock_get.assert_called_once_with(SERVICE, "fleet-access-token")
        assert result == "my_token"

    def test_returns_none_when_absent(self):
        from tesla_cli.core.auth.tokens import get_token

        with patch("keyring.get_password", return_value=None):
            result = get_token("missing-key")

        assert result is None


class TestSetToken:
    def test_calls_keyring_set_password(self):
        from tesla_cli.core.auth.tokens import SERVICE, set_token

        with patch("keyring.set_password") as mock_set:
            set_token("tessie-token", "abc123")

        mock_set.assert_called_once_with(SERVICE, "tessie-token", "abc123")


class TestDeleteToken:
    def test_deletes_existing_token(self):
        from tesla_cli.core.auth.tokens import SERVICE, delete_token

        with patch("keyring.delete_password") as mock_del:
            delete_token("order-access-token")

        mock_del.assert_called_once_with(SERVICE, "order-access-token")

    def test_swallows_password_delete_error(self):
        import keyring.errors

        from tesla_cli.core.auth.tokens import delete_token

        with patch("keyring.delete_password", side_effect=keyring.errors.PasswordDeleteError):
            # Should not raise
            delete_token("nonexistent-token")


class TestHasToken:
    def test_true_when_token_present(self):
        from tesla_cli.core.auth.tokens import has_token

        with patch("keyring.get_password", return_value="some_value"):
            assert has_token("fleet-refresh-token") is True

    def test_false_when_token_absent(self):
        from tesla_cli.core.auth.tokens import has_token

        with patch("keyring.get_password", return_value=None):
            assert has_token("fleet-refresh-token") is False


class TestTokenConstants:
    def test_expected_keys_defined(self):
        import tesla_cli.core.auth.tokens as tokens_mod

        assert tokens_mod.ORDER_ACCESS_TOKEN == "order-access-token"
        assert tokens_mod.ORDER_REFRESH_TOKEN == "order-refresh-token"
        assert tokens_mod.TESSIE_TOKEN == "tessie-token"
        assert tokens_mod.FLEET_ACCESS_TOKEN == "fleet-access-token"
        assert tokens_mod.FLEET_REFRESH_TOKEN == "fleet-refresh-token"
        assert tokens_mod.SERVICE == "tesla-cli"


# ---------------------------------------------------------------------------
# tessie.py
# ---------------------------------------------------------------------------


class TestGetTessieToken:
    def test_returns_token_when_present(self):
        from tesla_cli.core.auth.tessie import get_tessie_token

        with patch("keyring.get_password", return_value="tessie_abc"):
            result = get_tessie_token()

        assert result == "tessie_abc"

    def test_raises_when_no_token(self):
        from tesla_cli.core.auth.tessie import get_tessie_token
        from tesla_cli.core.exceptions import AuthenticationError

        with patch("keyring.get_password", return_value=None):
            with pytest.raises(AuthenticationError, match="Tessie not configured"):
                get_tessie_token()
