"""Shared HTTP helper: safe transport retries and per-class rate limits."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from tesla_cli.core.backends import http as http_mod
from tesla_cli.core.backends.http import HttpBackendMixin, _limiter_for, send_with_retry
from tesla_cli.core.exceptions import NetworkError


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(http_mod.time, "sleep", lambda s: None)


def _ok(json_body=None):
    return httpx.Response(200, json=json_body or {"response": {"ok": True}})


def _client(*effects):
    client = MagicMock(spec=httpx.Client)
    client.request.side_effect = list(effects)
    return client


def test_connect_error_retried_for_post():
    """The request never reached Tesla, so even a command is safe to resend."""
    client = _client(httpx.ConnectError("refused"), _ok())
    assert send_with_retry(client, "POST", "/x", max_retries=2).status_code == 200
    assert client.request.call_count == 2


def test_read_timeout_retried_for_get():
    client = _client(httpx.ReadTimeout("slow"), _ok())
    assert send_with_retry(client, "GET", "/x", max_retries=2).status_code == 200


def test_read_timeout_not_retried_for_post():
    """A command may already have executed: never send it twice."""
    client = _client(httpx.ReadTimeout("slow"), _ok())
    with pytest.raises(NetworkError):
        send_with_retry(client, "POST", "/command/actuate_trunk", max_retries=3)
    assert client.request.call_count == 1


def test_gives_up_after_max_retries():
    client = _client(*[httpx.ConnectError("down")] * 4)
    with pytest.raises(NetworkError):
        send_with_retry(client, "GET", "/x", max_retries=3)
    assert client.request.call_count == 4


def test_limiter_classes():
    assert _limiter_for("GET", "/api/1/vehicles/1/vehicle_data") is http_mod._data_limiter
    assert _limiter_for("POST", "/api/1/vehicles/1/command/honk_horn") is http_mod._command_limiter
    assert _limiter_for("POST", "/api/1/vehicles/1/wake_up") is http_mod._wake_limiter


def test_polling_does_not_starve_commands(monkeypatch):
    """Exhausting the data bucket must not block commands."""
    data = http_mod._TokenBucket(max_tokens=3, refill_rate=0)
    commands = http_mod._TokenBucket(max_tokens=3, refill_rate=0)
    monkeypatch.setattr(http_mod, "_data_limiter", data)
    monkeypatch.setattr(http_mod, "_command_limiter", commands)
    while _limiter_for("GET", "/vehicle_data").acquire(timeout=0):
        pass
    assert _limiter_for("POST", "/command/door_lock").acquire(timeout=0)


class _Backend(HttpBackendMixin):
    def __init__(self, client):
        self._client = client


def test_mixin_maps_network_error_after_retries():
    backend = _Backend(_client(*[httpx.ConnectError("down")] * 4))
    with pytest.raises(NetworkError):
        backend._get("/api/1/vehicles")


def test_mixin_recovers_from_transient_network_error():
    backend = _Backend(_client(httpx.ConnectError("blip"), _ok({"response": [1, 2]})))
    assert backend._get("/api/1/vehicles") == [1, 2]


def test_owner_backend_uses_shared_helper():
    from tesla_cli.core.backends.owner import OwnerApiVehicleBackend

    assert issubclass(OwnerApiVehicleBackend, HttpBackendMixin)


def test_order_locale_from_config_and_args():
    from tesla_cli.core.backends.order import OrderBackend
    from tesla_cli.core.config import Config

    cfg = Config()
    cfg.order.country = "co"
    cfg.order.language = "ES"
    with patch("tesla_cli.core.config.load_config", return_value=cfg):
        assert OrderBackend()._locale() == ("CO", "es")
    assert OrderBackend(country="de", language="de")._locale() == ("DE", "de")


def test_order_locale_defaults_to_us_english():
    from tesla_cli.core.backends.order import OrderBackend
    from tesla_cli.core.config import Config

    with patch("tesla_cli.core.config.load_config", return_value=Config()):
        assert OrderBackend()._locale() == ("US", "en")
