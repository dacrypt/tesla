"""Token storage on a machine with no keyring backend.

Headless Linux, Docker and CI runners have no Secret Service. `keyring` raises
NoKeyringError there, which used to propagate out of every optional-credential
lookup and turn "not configured" into a crash.
"""

from __future__ import annotations

from unittest.mock import patch

import keyring
import pytest

from tesla_cli.core.auth import tokens


class TestGetTokenWithoutBackend:
    def test_returns_none_instead_of_raising(self):
        with patch("keyring.get_password", side_effect=keyring.errors.NoKeyringError("no backend")):
            assert tokens.get_token(tokens.PLANNER_WEATHER_KEY) is None

    def test_locked_keyring_also_reads_as_unconfigured(self):
        """KeyringLocked is a KeyringError too -- don't crash the caller."""
        with patch("keyring.get_password", side_effect=keyring.errors.KeyringLocked("locked")):
            assert tokens.get_token(tokens.TESSIE_TOKEN) is None

    def test_has_token_is_false_without_backend(self):
        with patch("keyring.get_password", side_effect=keyring.errors.NoKeyringError("no backend")):
            assert tokens.has_token(tokens.FLEET_ACCESS_TOKEN) is False

    def test_unrelated_errors_still_propagate(self):
        """Only keyring failures are absorbed -- real bugs must stay visible."""
        with (
            patch("keyring.get_password", side_effect=ValueError("boom")),
            pytest.raises(ValueError),
        ):
            tokens.get_token(tokens.TESSIE_TOKEN)


class TestSetTokenWithoutBackend:
    def test_raises_with_actionable_hint(self):
        """A failed write must never be silent -- the credential would be lost."""
        with (
            patch("keyring.set_password", side_effect=keyring.errors.NoKeyringError("no backend")),
            pytest.raises(keyring.errors.NoKeyringError) as exc,
        ):
            tokens.set_token(tokens.TESSIE_TOKEN, "abc123")
        assert "PYTHON_KEYRING_BACKEND" in str(exc.value)


class TestDeleteTokenWithoutBackend:
    def test_is_a_noop_without_backend(self):
        with patch(
            "keyring.delete_password", side_effect=keyring.errors.NoKeyringError("no backend")
        ):
            tokens.delete_token(tokens.ORDER_ACCESS_TOKEN)  # must not raise
