"""Tests for tesla_cli.core.nav.geocode."""

from __future__ import annotations

import logging
import re

import pytest
from pytest_httpx import HTTPXMock

from tesla_cli.core.nav.geocode import GeocodeError, batch_geocode, geocode

LATLON_404_MSG = (
    "route create: address 'Nowheresville, Atlantis' could not be geocoded "
    "by Nominatim (404). Retry with a different spelling or use "
    "'lat,lon' syntax."
)
LATLON_429_MSG = (
    "route create: Nominatim rate limit (429). "
    "Wait 60s and retry, or use 'lat,lon' for immediate input."
)


def test_lat_lon_short_circuit_skips_network(httpx_mock: HTTPXMock) -> None:
    wp = geocode("4.6487,-74.0672")
    assert wp.lat == pytest.approx(4.6487)
    assert wp.lon == pytest.approx(-74.0672)
    assert wp.geocode_provider == "user"
    assert wp.raw_address == "4.6487,-74.0672"
    # httpx_mock with no registered responses would error on any real call
    assert httpx_mock.get_requests() == []


def test_lat_lon_with_whitespace_short_circuits(httpx_mock: HTTPXMock) -> None:
    wp = geocode("4.6487, -74.0672")
    assert wp.geocode_provider == "user"
    assert wp.lat == pytest.approx(4.6487)
    assert wp.lon == pytest.approx(-74.0672)
    assert httpx_mock.get_requests() == []


def test_nominatim_success_returns_waypoint(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://nominatim.openstreetmap.org/search?format=json&q=Centro%20Andino&limit=1",
        json=[{"lat": "4.6670", "lon": "-74.0540"}],
    )
    wp = geocode("Centro Andino")
    assert wp.geocode_provider == "nominatim"
    assert wp.lat == pytest.approx(4.667)
    assert wp.lon == pytest.approx(-74.054)


def test_nominatim_404_raises_verbatim_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://nominatim.openstreetmap.org/search?format=json&q=Nowheresville%2C%20Atlantis&limit=1",
        status_code=404,
    )
    with pytest.raises(GeocodeError) as exc:
        geocode("Nowheresville, Atlantis")
    assert str(exc.value) == LATLON_404_MSG


def test_nominatim_empty_result_raises_404_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://nominatim.openstreetmap.org/search?format=json&q=Nowheresville%2C%20Atlantis&limit=1",
        json=[],
    )
    with pytest.raises(GeocodeError) as exc:
        geocode("Nowheresville, Atlantis")
    assert str(exc.value) == LATLON_404_MSG


def test_nominatim_429_raises_verbatim_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://nominatim.openstreetmap.org/search?format=json&q=somewhere&limit=1",
        status_code=429,
    )
    with pytest.raises(GeocodeError) as exc:
        geocode("somewhere")
    assert str(exc.value) == LATLON_429_MSG


def test_batch_caps_at_max_calls(httpx_mock: HTTPXMock) -> None:
    # 20 distinct addresses; only 10 should reach the network.
    # Register a single catch-all response reusable for every match.
    addresses = [f"addr-{i}" for i in range(20)]
    httpx_mock.add_response(
        url=re.compile(r"https://nominatim\.openstreetmap\.org/search.*"),
        json=[{"lat": "1.0", "lon": "2.0"}],
        is_reusable=True,
    )
    waypoints = batch_geocode(addresses, max_calls=10, warn_at=5)
    assert len(waypoints) == 10
    assert len(httpx_mock.get_requests()) == 10


def test_batch_short_circuits_do_not_count_toward_cap(httpx_mock: HTTPXMock) -> None:
    # mix 10 lat/lon short-circuits + 3 real addresses — all should resolve
    addresses = [f"{i}.0,{i}.0" for i in range(10)] + ["a", "b", "c"]
    for addr in ["a", "b", "c"]:
        httpx_mock.add_response(
            url=f"https://nominatim.openstreetmap.org/search?format=json&q={addr}&limit=1",
            json=[{"lat": "1.0", "lon": "2.0"}],
        )
    waypoints = batch_geocode(addresses, max_calls=10, warn_at=5)
    assert len(waypoints) == 13
    assert len(httpx_mock.get_requests()) == 3


def test_batch_warns_at_threshold(httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture) -> None:
    addresses = [f"addr-{i}" for i in range(5)]
    for addr in addresses:
        httpx_mock.add_response(
            url=f"https://nominatim.openstreetmap.org/search?format=json&q={addr}&limit=1",
            json=[{"lat": "1.0", "lon": "2.0"}],
        )
    with caplog.at_level(logging.WARNING, logger="tesla_cli.core.nav.geocode"):
        batch_geocode(addresses, max_calls=10, warn_at=5)
    warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warn_records) == 1
    assert "approaching Nominatim fair-use limit" in warn_records[0].getMessage()
