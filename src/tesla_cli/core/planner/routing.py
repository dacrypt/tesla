"""Routing engines: OpenRouteService (BYOK) and OSRM (public demo / self-host).

Both engines return the same shape:
    {"polyline": [(lat, lon), ...], "total_distance_km": float, "total_duration_min": int}

References:
- OpenRouteService GeoJSON endpoint:
  https://openrouteservice.org/dev/#/api-docs/v2/directions/{profile}/geojson/post
- OSRM route service:
  http://project-osrm.org/docs/v5.24.0/api/#route-service
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class RoutingError(Exception):
    """Routing engine call failed (network, HTTP >= 400, or parse error)."""


class RoutingAuthError(RoutingError):
    """API key missing or rejected."""


class RoutingRateLimitError(RoutingError):
    """Upstream returned 429 — user should back off or self-host."""


class RoutingEngine(Protocol):
    name: str

    def compute_route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> dict[str, Any]:
        """Return {'polyline': list[(lat,lon)], 'total_distance_km': float, 'total_duration_min': int}."""


class OpenRouteServiceEngine:
    name = "openroute"

    def __init__(self, api_key: str, timeout_s: float = 30.0) -> None:
        if not api_key:
            raise RoutingAuthError(
                "OpenRouteService API key not configured. Get one free at "
                "https://openrouteservice.org/dev/#/signup then run: "
                "tesla config set planner-openroute-key <KEY>"
            )
        self._key = api_key
        self._timeout = timeout_s

    def compute_route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> dict[str, Any]:
        # GeoJSON endpoint: returns LineString coordinates as [[lon,lat], ...]
        url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
        body = {
            "coordinates": [[origin[1], origin[0]], [destination[1], destination[0]]],
            "instructions": False,
            "geometry_simplify": True,
            "preference": "fastest",
        }
        headers = {
            "Authorization": self._key,
            "Content-Type": "application/json",
            "User-Agent": "tesla-cli",
        }
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise RoutingError(f"OpenRouteService request failed: {exc}") from exc
        if r.status_code in (401, 403):
            raise RoutingAuthError(
                "OpenRouteService rejected the API key "
                "(check: tesla config set planner-openroute-key)"
            )
        if r.status_code == 429:
            raise RoutingRateLimitError(
                "OpenRouteService rate-limited (free tier: 2000/day). Try again later."
            )
        if r.status_code >= 400:
            raise RoutingError(f"OpenRouteService HTTP {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()
        except ValueError as exc:
            raise RoutingError(f"OpenRouteService returned invalid JSON: {exc}") from exc
        try:
            feature = data["features"][0]
            coords = feature["geometry"]["coordinates"]  # [[lon,lat],...]
            summary = feature["properties"]["summary"]
            distance_m = float(summary["distance"])
            duration_s = float(summary["duration"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RoutingError(f"OpenRouteService response malformed: {exc}") from exc
        polyline = [(float(lat), float(lon)) for lon, lat in coords]
        return {
            "polyline": polyline,
            "total_distance_km": distance_m / 1000.0,
            "total_duration_min": int(duration_s / 60),
        }


class OsrmEngine:
    name = "osrm"

    def __init__(
        self,
        base_url: str = "https://router.project-osrm.org",
        timeout_s: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    def compute_route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> dict[str, Any]:
        lon1, lat1 = origin[1], origin[0]
        lon2, lat2 = destination[1], destination[0]
        url = (
            f"{self._base}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
            "?overview=simplified&geometries=geojson&alternatives=false&steps=false"
        )
        try:
            r = httpx.get(url, timeout=self._timeout, headers={"User-Agent": "tesla-cli"})
        except httpx.HTTPError as exc:
            raise RoutingError(f"OSRM request failed: {exc}") from exc
        if r.status_code == 429:
            raise RoutingRateLimitError(
                "OSRM public demo rate-limited. "
                "Self-host: https://github.com/Project-OSRM/osrm-backend"
            )
        if r.status_code >= 400:
            raise RoutingError(f"OSRM HTTP {r.status_code}")
        try:
            data = r.json()
        except ValueError as exc:
            raise RoutingError(f"OSRM returned invalid JSON: {exc}") from exc
        if data.get("code") != "Ok" or not data.get("routes"):
            raise RoutingError(f"OSRM returned no route: {data.get('message', 'unknown')}")
        route = data["routes"][0]
        coords = route["geometry"]["coordinates"]  # [[lon,lat],...]
        polyline = [(float(lat), float(lon)) for lon, lat in coords]
        return {
            "polyline": polyline,
            "total_distance_km": float(route["distance"]) / 1000.0,
            "total_duration_min": int(float(route["duration"]) / 60),
        }


def get_engine(name: str, cfg) -> RoutingEngine:
    """Build a RoutingEngine by name, pulling key/url from config+keyring."""
    if name == "openroute":
        from tesla_cli.core.auth import tokens

        key = cfg.planner.openroute_key or tokens.get_token(tokens.PLANNER_OPENROUTE_KEY) or ""
        return OpenRouteServiceEngine(key)
    if name == "osrm":
        return OsrmEngine(base_url=cfg.planner.osrm_base_url or "https://router.project-osrm.org")
    raise ValueError(f"unknown routing engine: {name}")
