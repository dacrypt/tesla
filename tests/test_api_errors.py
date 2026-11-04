"""Central mapping of backend errors to HTTP responses (api/errors.py)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tesla_cli.api.errors import upstream_http_error  # noqa: E402
from tesla_cli.core.config import Config  # noqa: E402
from tesla_cli.core.exceptions import (  # noqa: E402
    ApiError,
    AuthenticationError,
    BackendNotSupportedError,
    ConfigurationError,
    EndpointDeprecatedError,
    RateLimitError,
    VehicleAsleepError,
)
from tests.conftest import MOCK_VIN  # noqa: E402


@pytest.mark.parametrize(
    ("exc", "status"),
    [
        (VehicleAsleepError("zzz"), 503),
        (RateLimitError(), 429),
        (ApiError(429, "slow down"), 429),
        (EndpointDeprecatedError(), 412),
        (ApiError(412, "pre-delivery"), 412),
        (BackendNotSupportedError("signed commands"), 501),
        (AuthenticationError("token expired"), 424),
        (ConfigurationError("no VIN"), 400),
        (ApiError(500, "boom"), 502),
        (RuntimeError("HTTP 429: Too Many Requests"), 429),
        (RuntimeError("something else"), 502),
    ],
)
def test_status_mapping(exc, status):
    assert upstream_http_error(exc).status_code == status


def test_untyped_message_with_412_number_in_text_is_not_misclassified():
    """'4120 km' used to be read as HTTP 412 by the old substring checks."""
    assert upstream_http_error(RuntimeError("odometer 4120 km")).status_code == 502


def test_rate_limit_sets_retry_after():
    assert upstream_http_error(RateLimitError()).headers == {"Retry-After": "10"}


def test_tesla_auth_error_is_not_401():
    """401 means 'wrong API key for this server' to the dashboard."""
    assert upstream_http_error(AuthenticationError("expired")).status_code != 401


def test_long_details_truncated():
    assert len(upstream_http_error(RuntimeError("x" * 5000)).detail) <= 501


def test_default_status_override():
    assert upstream_http_error(RuntimeError("x"), default_status=500).status_code == 500


@pytest.fixture
def client_with():
    started: list = []

    def _make(side_effect) -> TestClient:
        cfg = Config()
        cfg.general.default_vin = MOCK_VIN
        backend = MagicMock()
        backend.command.side_effect = side_effect
        for target, value in [
            ("tesla_cli.api.app.load_config", cfg),
            ("tesla_cli.api.routes.security.load_config", cfg),
            ("tesla_cli.api.routes.security.get_vehicle_backend", backend),
            ("tesla_cli.api.routes.security.resolve_vin", MOCK_VIN),
        ]:
            p = patch(target, return_value=value)
            p.start()
            started.append(p)
        return TestClient(create_app(), raise_server_exceptions=False)

    yield _make
    for p in started:
        p.stop()


@pytest.mark.parametrize(
    ("exc", "status"),
    [
        (RateLimitError(), 429),
        (EndpointDeprecatedError(), 412),
        (BackendNotSupportedError("signed"), 501),
    ],
)
def test_route_uses_central_mapping(client_with, exc, status):
    client = client_with(exc)
    r = client.post("/api/security/lock")
    assert r.status_code == status


def test_uncaught_typed_error_handled_globally():
    """A TeslaCliError escaping a route becomes a mapped response, not a 500."""
    app = create_app()

    @app.get("/api/_boom")
    def _boom():
        raise BackendNotSupportedError("feature")

    r = TestClient(app, raise_server_exceptions=False).get("/api/_boom")
    assert r.status_code == 501
