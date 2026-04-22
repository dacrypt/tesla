"""OpenWeatherMap client for ambient temperature lookup.

BYOK: the user provides their own free-tier API key (1000 calls/day).
Sign up: https://openweathermap.org/api
Store:  tesla config set planner-weather-key <KEY>

Privacy: waypoint lat/lon is sent to OpenWeatherMap when this module is used.
`--no-weather` on `nav plan` opts out entirely.
"""

from __future__ import annotations

import httpx

OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


class WeatherError(Exception):
    """OpenWeatherMap call failed (network, HTTP >= 400, or parse error)."""


class WeatherAuthError(WeatherError):
    """API key missing or rejected."""


def get_ambient_temp(lat: float, lon: float, api_key: str, timeout_s: float = 20.0) -> float | None:
    """Return current ambient temperature in °C at (lat, lon), or None on failure."""
    if not api_key:
        raise WeatherAuthError(
            "OpenWeatherMap API key not configured. Get one free at "
            "https://openweathermap.org/api then run: "
            "tesla config set planner-weather-key <KEY>"
        )
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
    }
    try:
        r = httpx.get(
            OWM_URL,
            params=params,
            timeout=timeout_s,
            headers={"User-Agent": "tesla-cli"},
        )
    except httpx.HTTPError:
        return None
    if r.status_code in (401, 403):
        raise WeatherAuthError("OpenWeatherMap rejected the API key")
    if r.status_code == 429:
        # fail-soft: caller can skip with --no-weather or retry later
        return None
    if r.status_code >= 400:
        return None
    try:
        data = r.json()
        return float(data["main"]["temp"])
    except (ValueError, KeyError, TypeError):
        return None
