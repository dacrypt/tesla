"""Tests for FleetSignedBackend (T2.0, T2.1, T2.2).

Covers:
  * test_unmapped_command_raises       — T2.0 regression: no silent fallback.
  * test_auth_key_idempotent           — T2.1 idempotency: key files not rewritten.
  * test_handshake_session_closed_on_error
                                        — T2.2 regression: aiohttp session closed
                                         when handshake raises.

These tests never touch the network nor the keyring (tokens are patched via
the ``tesla_cli.core.auth.tokens.get_token`` boundary).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("aiohttp", reason="tesla-fleet-api optional dep")
pytest.importorskip("tesla_fleet_api", reason="tesla-fleet-api optional dep")


# ---------------------------------------------------------------------------
# T2.0 — unmapped command must raise, not silently fall back.
# ---------------------------------------------------------------------------


def test_unmapped_command_raises(monkeypatch):
    """An unknown command name must raise BackendNotSupportedError instead of
    being forwarded to the unsigned Fleet API (which would silently succeed
    on 2024.26+ firmware while the car ignores the request)."""
    from tesla_cli.core.backends import fleet_signed as fs_mod
    from tesla_cli.core.backends.fleet_signed import FleetSignedBackend
    from tesla_cli.core.exceptions import BackendNotSupportedError

    backend = FleetSignedBackend()

    # Empty the command map so *any* command name is "unmapped".
    monkeypatch.setattr(fs_mod, "_COMMAND_MAP", {})

    with pytest.raises(BackendNotSupportedError) as excinfo:
        backend.command("5YJ3E1EA0JF000000", "unknown_cmd")

    assert "signed command 'unknown_cmd' not mapped" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T2.1 — `tesla config auth fleet-signed` must not regenerate keys on
# subsequent invocations.
# ---------------------------------------------------------------------------


def test_auth_key_idempotent(monkeypatch, tmp_path):
    """Running the auth flow twice must reuse the same key pair — the
    private-key file's mtime must not change between invocations."""
    # Redirect ~/.tesla-cli/keys to an isolated tmp dir.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    keys_dir = fake_home / ".tesla-cli" / "keys"
    keys_dir.mkdir(parents=True)
    priv = keys_dir / "private-key.pem"
    pub = keys_dir / "public-key.pem"

    # Seed a fake key pair so the idempotency branch triggers.
    priv.write_bytes(b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n")
    pub.write_bytes(b"-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n")
    os.chmod(priv, 0o600)

    mtime_before = priv.stat().st_mtime_ns

    # Patch the heavy dependencies so we only exercise steps (a) + (b).
    # Step (c) should fail fast (preflight httpx.get returns a non-200), which
    # is exactly what we want: we just need step (b) to run without
    # overwriting the existing files.
    from tesla_cli.cli.commands import config_cmd as cc

    # _require_fleet_api success
    monkeypatch.setattr("tesla_cli.core.backends.fleet_signed._require_fleet_api", lambda: None)

    # Preset fleet.domain on the cfg object load_config() returns so the
    # interactive prompt never fires under pytest. The real user's config
    # is never mutated (we replace the call, not the file).
    from tesla_cli.core.config import Config

    def _fake_load_config():
        _fake = Config()
        _fake.fleet.domain = "test.example.invalid"
        return _fake

    from tesla_cli.cli.commands import config_cmd as _cc_for_patch

    monkeypatch.setattr(_cc_for_patch, "load_config", _fake_load_config)
    monkeypatch.setattr(_cc_for_patch, "save_config", lambda _cfg: None)

    # Fake an httpx.get that returns a 404 so we exit after step (c).
    class _FakeResp:
        status_code = 404
        text = "not found"

    fake_httpx = MagicMock()
    fake_httpx.get.return_value = _FakeResp()
    monkeypatch.setitem(__import__("sys").modules, "httpx", fake_httpx)

    # First invocation — should hit the "reuse" branch.
    import typer

    with pytest.raises(typer.Exit):
        cc._auth_fleet_signed()

    mtime_after_first = priv.stat().st_mtime_ns
    assert mtime_after_first == mtime_before, "First run should not touch the file"

    # Second invocation — same expectation.
    with pytest.raises(typer.Exit):
        cc._auth_fleet_signed()

    mtime_after_second = priv.stat().st_mtime_ns
    assert mtime_after_second == mtime_before, "Second run must be a no-op on keys"


# ---------------------------------------------------------------------------
# T2.2 — if VehicleSigned.handshake() raises, the aiohttp ClientSession
# must be awaited-closed before the exception propagates.
# ---------------------------------------------------------------------------


def test_handshake_session_closed_on_error(monkeypatch):
    """Regression: a failing handshake used to leak the aiohttp session.
    After T2.2 the session.close() coroutine must be awaited even when
    handshake() raises."""
    from tesla_cli.core.backends import fleet_signed as fs_mod
    from tesla_cli.core.backends.fleet_signed import FleetSignedBackend

    backend = FleetSignedBackend()

    # Stub token lookup — must be non-None to clear the AuthenticationError
    # guard in _get_vehicle.
    monkeypatch.setattr(fs_mod.tokens, "get_token", lambda key: "fake-access-token")

    # Stub load_config so cfg.fleet.region resolves without touching disk.
    fake_cfg = MagicMock()
    fake_cfg.fleet.region = "na"
    monkeypatch.setattr(fs_mod, "load_config", lambda: fake_cfg)

    # Build a MagicMock aiohttp.ClientSession where .close() is an AsyncMock
    # so we can assert it was awaited.
    session_close = AsyncMock()
    fake_session = MagicMock()
    fake_session.close = session_close

    fake_aiohttp = MagicMock()
    fake_aiohttp.ClientSession = MagicMock(return_value=fake_session)

    # Stub TeslaFleetApi so no real HTTP client is constructed.
    fake_fleet_api_mod = MagicMock()
    fake_fleet_api_mod.TeslaFleetApi = MagicMock(return_value=MagicMock())

    # Stub VehicleSigned so we control the handshake.
    fake_vehicle = MagicMock()
    fake_vehicle.handshake = AsyncMock(side_effect=RuntimeError("handshake boom"))
    fake_signed_mod = MagicMock()
    fake_signed_mod.VehicleSigned = MagicMock(return_value=fake_vehicle)

    import sys

    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)
    monkeypatch.setitem(sys.modules, "tesla_fleet_api", fake_fleet_api_mod)
    monkeypatch.setitem(sys.modules, "tesla_fleet_api.tesla.vehicle.signed", fake_signed_mod)

    with pytest.raises(RuntimeError, match="handshake boom"):
        asyncio.run(backend._get_vehicle("5YJ3E1EA0JF000000"))

    # The session opened inside _get_vehicle must have been closed.
    session_close.assert_awaited()
    # And the backend must have cleared its _session reference so a retry
    # doesn't reuse a closed session.
    assert backend._session is None
