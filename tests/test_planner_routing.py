"""Tests for tesla_cli.core.planner.routing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pytest_httpx import HTTPXMock

from tesla_cli.core.planner.routing import (
    OpenRouteServiceEngine,
    OsrmEngine,
    RoutingAuthError,
    RoutingError,
    RoutingRateLimitError,
    get_engine,
)

ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"


def _ors_geojson(coords, distance_m=300000.0, duration_s=18000.0) -> dict:
    return {
        "features": [
            {
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "summary": {"distance": distance_m, "duration": duration_s},
                },
            }
        ]
    }


def test_ors_empty_key_raises_auth_with_signup_url() -> None:
    with pytest.raises(RoutingAuthError) as exc:
        OpenRouteServiceEngine("")
    msg = str(exc.value)
    assert "openrouteservice.org" in msg
    assert "tesla config set planner-openroute-key" in msg


def test_ors_success_returns_polyline_distance_duration(httpx_mock: HTTPXMock) -> None:
    coords = [[-74.07, 4.71], [-74.5, 5.3], [-75.58, 6.24]]  # [lon,lat]
    httpx_mock.add_response(url=ORS_URL, method="POST", json=_ors_geojson(coords))
    engine = OpenRouteServiceEngine("fake-key")
    out = engine.compute_route((4.71, -74.07), (6.24, -75.58))
    assert out["polyline"] == [(4.71, -74.07), (5.3, -74.5), (6.24, -75.58)]
    assert out["total_distance_km"] == pytest.approx(300.0)
    assert out["total_duration_min"] == 300


def test_ors_401_raises_auth_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=ORS_URL, method="POST", status_code=401)
    engine = OpenRouteServiceEngine("bad")
    with pytest.raises(RoutingAuthError) as exc:
        engine.compute_route((0.0, 0.0), (1.0, 1.0))
    assert "tesla config set" in str(exc.value)


def test_ors_429_raises_rate_limit(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=ORS_URL, method="POST", status_code=429)
    engine = OpenRouteServiceEngine("k")
    with pytest.raises(RoutingRateLimitError) as exc:
        engine.compute_route((0.0, 0.0), (1.0, 1.0))
    assert "rate-limited" in str(exc.value)


def test_ors_500_raises_routing_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=ORS_URL, method="POST", status_code=500, text="boom")
    engine = OpenRouteServiceEngine("k")
    with pytest.raises(RoutingError):
        engine.compute_route((0.0, 0.0), (1.0, 1.0))


def test_osrm_success_parses_route(httpx_mock: HTTPXMock) -> None:
    # OSRM URL has coords baked in
    httpx_mock.add_response(
        url=(
            "https://router.project-osrm.org/route/v1/driving/"
            "-74.07,4.71;-75.58,6.24"
            "?overview=simplified&geometries=geojson&alternatives=false&steps=false"
        ),
        method="GET",
        json={
            "code": "Ok",
            "routes": [
                {
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-74.07, 4.71], [-75.58, 6.24]],
                    },
                    "distance": 415000.0,
                    "duration": 28800.0,
                }
            ],
        },
    )
    engine = OsrmEngine()
    out = engine.compute_route((4.71, -74.07), (6.24, -75.58))
    assert out["total_distance_km"] == pytest.approx(415.0)
    assert out["total_duration_min"] == 480
    assert out["polyline"] == [(4.71, -74.07), (6.24, -75.58)]


def test_osrm_no_route_raises_routing_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=(
            "https://router.project-osrm.org/route/v1/driving/"
            "-74.07,4.71;-75.58,6.24"
            "?overview=simplified&geometries=geojson&alternatives=false&steps=false"
        ),
        method="GET",
        json={"code": "NoRoute", "message": "no path found"},
    )
    engine = OsrmEngine()
    with pytest.raises(RoutingError) as exc:
        engine.compute_route((4.71, -74.07), (6.24, -75.58))
    assert "no path" in str(exc.value).lower() or "no route" in str(exc.value).lower()


def test_get_engine_bogus_raises_value_error() -> None:
    cfg = SimpleNamespace(
        planner=SimpleNamespace(openroute_key=None, osrm_base_url="https://router.project-osrm.org")
    )
    with pytest.raises(ValueError):
        get_engine("bogus", cfg)


def test_get_engine_osrm_builds_engine() -> None:
    cfg = SimpleNamespace(
        planner=SimpleNamespace(openroute_key=None, osrm_base_url="https://router.project-osrm.org")
    )
    engine = get_engine("osrm", cfg)
    assert engine.name == "osrm"
