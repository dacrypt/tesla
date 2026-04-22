"""Unit tests for send_place — pure mock, no real backend."""

from __future__ import annotations

from unittest.mock import MagicMock

from tesla_cli.core.nav.dispatch import send_place


def test_send_place_calls_backend_share() -> None:
    backend = MagicMock()
    backend.share.return_value = {"result": True}

    out = send_place(backend, "5YJ3000000000", "Calle 100 #15-20, Bogotá")

    backend.share.assert_called_once_with(
        "5YJ3000000000", "Calle 100 #15-20, Bogotá", locale="en-US"
    )
    assert out == {"result": True}


def test_send_place_with_lat_lon_string() -> None:
    backend = MagicMock()
    backend.share.return_value = {"result": True}

    send_place(backend, "VIN", "4.71,-74.07")

    backend.share.assert_called_once_with("VIN", "4.71,-74.07", locale="en-US")


def test_send_place_custom_locale() -> None:
    backend = MagicMock()
    backend.share.return_value = {"result": True}

    send_place(backend, "VIN", "Bogotá", locale="es-CO")

    backend.share.assert_called_once_with("VIN", "Bogotá", locale="es-CO")


def test_send_place_returns_backend_response() -> None:
    backend = MagicMock()
    expected = {"result": True, "queued": False}
    backend.share.return_value = expected

    assert send_place(backend, "VIN", "addr") is expected
