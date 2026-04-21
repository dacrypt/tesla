"""Regression tests for vehicle backend behaviour.

Covers:
  * vcp_403       — T2.3: fleet.py command() wraps 403 VCP error with verbatim §3.2 message.
  * tessie_vcp    — T1.4: tessie.py command() wraps any 403 into BackendNotSupportedError.
  * cached_vcp    — T1.4: cached.py command() re-raises BackendNotSupportedError and invalidates cache.
  * share_payload — T1.3 (merged): fleet.py share() sends correct payload shape.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tesla_cli.core.exceptions import ApiError, BackendNotSupportedError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VIN = "5YJ3E1EA0JF000000"

_VCP_403_BODY = (
    '{"error":"Vehicle Command Protocol required","error_description":'
    '"Vehicle Command Protocol required for this vehicle"}'
)

_VCP_403_MARKER = "Vehicle Command Protocol"


# ---------------------------------------------------------------------------
# T2.3 — fleet.py 403 VCP message contains all 4 §3.2 verbatim lines
# ---------------------------------------------------------------------------


def test_fleet_vcp_403_raises_with_verbatim_message():
    """FleetBackend.command() must raise BackendNotSupportedError whose str()
    contains all four §3.2 handshake-failure guidance lines verbatim."""
    from tesla_cli.core.backends.fleet import FleetBackend

    backend = FleetBackend.__new__(FleetBackend)

    api_error = ApiError(403, _VCP_403_BODY)

    with (
        patch.object(backend, "_post", side_effect=api_error),
        pytest.raises(BackendNotSupportedError) as excinfo,
    ):
        backend.command(VIN, "door_lock")

    msg = str(excinfo.value)
    assert "Vehicle Command Protocol required. Run: tesla config auth fleet-signed" in msg
    assert "Then pair this VIN in the Tesla app under Manage Keys" in msg
    assert "Check status any time with: tesla doctor" in msg
    assert "To return to read-only Fleet API: tesla config set backend fleet" in msg


def test_fleet_vcp_403_non_vcp_body_reraises():
    """A plain 403 without the VCP marker must not be swallowed."""
    from tesla_cli.core.backends.fleet import FleetBackend

    backend = FleetBackend.__new__(FleetBackend)
    api_error = ApiError(403, '{"error":"Access denied"}')

    with patch.object(backend, "_post", side_effect=api_error), pytest.raises(ApiError) as excinfo:
        backend.command(VIN, "door_lock")

    assert excinfo.value.status_code == 403


# ---------------------------------------------------------------------------
# T1.4 — tessie.py 403 wrapping
# ---------------------------------------------------------------------------


def test_tessie_vcp_403_wraps_to_backend_not_supported():
    """TessieBackend.command() must convert any 403 into BackendNotSupportedError."""
    from tesla_cli.core.backends.tessie import TessieBackend

    backend = TessieBackend.__new__(TessieBackend)
    api_error = ApiError(403, '{"error":"forbidden"}')

    with (
        patch.object(backend, "_post", side_effect=api_error),
        pytest.raises(BackendNotSupportedError) as excinfo,
    ):
        backend.command(VIN, "door_lock")

    msg = str(excinfo.value)
    assert "Vehicle Command Protocol required" in msg
    assert "tesla doctor" in msg


def test_tessie_non_403_reraises():
    """TessieBackend.command() must not swallow non-403 ApiErrors."""
    from tesla_cli.core.backends.tessie import TessieBackend

    backend = TessieBackend.__new__(TessieBackend)
    api_error = ApiError(500, "internal error")

    with patch.object(backend, "_post", side_effect=api_error), pytest.raises(ApiError) as excinfo:
        backend.command(VIN, "door_lock")

    assert excinfo.value.status_code == 500


# ---------------------------------------------------------------------------
# T1.4 — cached.py BackendNotSupportedError propagation + cache invalidation
# ---------------------------------------------------------------------------


def test_cached_vcp_invalidates_and_reraises():
    """CachedVehicleBackend.command() must invalidate cache and re-raise
    BackendNotSupportedError from the inner backend."""
    from tesla_cli.core.backends.cached import CachedVehicleBackend

    inner = MagicMock()
    inner.command.side_effect = BackendNotSupportedError(
        "Vehicle Command Protocol required. Check status with: tesla doctor",
        "fleet-signed",
    )
    cached = CachedVehicleBackend(inner, ttl=45)

    # Pre-seed cache so we can verify it is cleared
    cached._cache[f"vdata:{VIN}"] = ({"state": "online"}, 9999999999)
    assert f"vdata:{VIN}" in cached._cache

    with pytest.raises(BackendNotSupportedError):
        cached.command(VIN, "door_lock")

    assert f"vdata:{VIN}" not in cached._cache, "Cache must be invalidated after VCP error"


# ---------------------------------------------------------------------------
# T1.3 (merged) — share() payload lock-in
# ---------------------------------------------------------------------------


def test_fleet_share_sends_correct_payload():
    """FleetBackend.share() must send type='share_ext_content_raw' with the
    android.intent.extra.TEXT key in the value dict."""
    from tesla_cli.core.backends.fleet import FleetBackend

    backend = FleetBackend.__new__(FleetBackend)
    captured: dict = {}

    def fake_command(vin, cmd, **params):
        captured["vin"] = vin
        captured["cmd"] = cmd
        captured["params"] = params
        return {"result": True}

    with patch.object(backend, "command", side_effect=fake_command):
        backend.share(VIN, "1600 Amphitheatre Pkwy, Mountain View")

    assert captured["cmd"] == "share"
    params = captured["params"]
    assert params["type"] == "share_ext_content_raw"
    assert "android.intent.extra.TEXT" in params["value"]
    assert params["value"]["android.intent.extra.TEXT"] == "1600 Amphitheatre Pkwy, Mountain View"
    assert "locale" in params
    assert "timestamp_ms" in params
