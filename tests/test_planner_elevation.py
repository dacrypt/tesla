"""Tests for tesla_cli.core.planner.elevation."""

from __future__ import annotations

import re

import pytest
from pytest_httpx import HTTPXMock

from tesla_cli.core.planner.elevation import (
    ElevationError,
    _sample_polyline,
    get_elevation_profile,
)

OE_URL_RE = re.compile(r"^https://api\.open-elevation\.com/api/v1/lookup$")


def test_sample_polyline_returns_input_when_shorter_than_samples() -> None:
    poly = [(0.0, 0.0), (1.0, 1.0)]
    assert _sample_polyline(poly, samples=50) == poly


def test_sample_polyline_returns_evenly_spaced_points() -> None:
    poly = [(float(i), 0.0) for i in range(100)]
    sampled = _sample_polyline(poly, samples=5)
    assert len(sampled) == 5
    # First and last should be preserved
    assert sampled[0] == (0.0, 0.0)
    assert sampled[-1] == (99.0, 0.0)


def test_get_elevation_profile_returns_elevations(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=OE_URL_RE,
        method="POST",
        json={
            "results": [
                {"latitude": 0.0, "longitude": 0.0, "elevation": 100.0},
                {"latitude": 1.0, "longitude": 1.0, "elevation": 250.0},
            ]
        },
    )
    poly = [(0.0, 0.0), (1.0, 1.0)]
    elevs = get_elevation_profile(poly, samples=2)
    assert elevs == [100.0, 250.0]


def test_get_elevation_profile_raises_on_http_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OE_URL_RE, status_code=503)
    with pytest.raises(ElevationError):
        get_elevation_profile([(0.0, 0.0), (1.0, 1.0)], samples=2)


def test_get_elevation_profile_raises_on_rate_limit(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OE_URL_RE, status_code=429)
    with pytest.raises(ElevationError, match="rate-limited"):
        get_elevation_profile([(0.0, 0.0), (1.0, 1.0)], samples=2)


def test_get_elevation_profile_raises_on_count_mismatch(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=OE_URL_RE,
        method="POST",
        json={"results": [{"elevation": 50.0}]},  # fewer than requested
    )
    with pytest.raises(ElevationError):
        get_elevation_profile([(0.0, 0.0), (1.0, 1.0)], samples=2)


def test_get_elevation_profile_empty_polyline_returns_empty() -> None:
    assert get_elevation_profile([], samples=10) == []
