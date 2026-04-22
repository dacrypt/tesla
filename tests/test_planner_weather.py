"""Tests for tesla_cli.core.planner.weather."""

from __future__ import annotations

import re

import pytest
from pytest_httpx import HTTPXMock

from tesla_cli.core.planner.weather import (
    WeatherAuthError,
    get_ambient_temp,
)

OWM_URL_RE = re.compile(r"^https://api\.openweathermap\.org/data/2\.5/weather.*")


def test_get_ambient_temp_returns_temp(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=OWM_URL_RE,
        json={"main": {"temp": 18.3}, "name": "Bogota"},
    )
    t = get_ambient_temp(4.71, -74.07, "fake-key")
    assert t == pytest.approx(18.3)


def test_get_ambient_temp_missing_key_raises_with_signup_url() -> None:
    with pytest.raises(WeatherAuthError, match="openweathermap.org"):
        get_ambient_temp(4.71, -74.07, api_key="")


def test_get_ambient_temp_auth_error_on_401(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OWM_URL_RE, status_code=401)
    with pytest.raises(WeatherAuthError):
        get_ambient_temp(4.71, -74.07, "bad-key")


def test_get_ambient_temp_returns_none_on_rate_limit(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OWM_URL_RE, status_code=429)
    assert get_ambient_temp(4.71, -74.07, "some-key") is None


def test_get_ambient_temp_returns_none_on_malformed_body(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=OWM_URL_RE, json={"unexpected": "shape"})
    assert get_ambient_temp(4.71, -74.07, "some-key") is None
