"""Nominatim geocoder with `"lat,lon"` short-circuit and fair-use caps.

Caller enforces the 10-call hard cap and 5-call warn threshold via
`batch_geocode`. Error strings for 404/429 are verbatim per the plan —
the CLI layer asserts them literally.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from urllib.parse import quote

import httpx

from tesla_cli import __version__
from tesla_cli.core.nav.route import Waypoint

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
LATLON_RE = re.compile(r"^-?\d+(\.\d+)?,\s*-?\d+(\.\d+)?$")

logger = logging.getLogger(__name__)


class GeocodeError(Exception):
    """Raised when a raw_address cannot be resolved."""


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_circuit(raw_address: str) -> Waypoint | None:
    if not LATLON_RE.match(raw_address.strip()):
        return None
    lat_s, lon_s = raw_address.strip().split(",", 1)
    return Waypoint(
        raw_address=raw_address,
        lat=float(lat_s),
        lon=float(lon_s.strip()),
        geocode_provider="user",
        geocode_at=_now_iso(),
    )


def geocode(raw_address: str) -> Waypoint:
    """Resolve a raw address. Bypasses Nominatim for `"lat,lon"` inputs."""
    short = _short_circuit(raw_address)
    if short is not None:
        return short

    headers = {"User-Agent": f"tesla-cli/{__version__}"}
    url = f"{NOMINATIM_URL}?format=json&q={quote(raw_address)}&limit=1"
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, headers=headers)

    if resp.status_code == 429:
        raise GeocodeError(
            "route create: Nominatim rate limit (429). "
            "Wait 60s and retry, or use 'lat,lon' for immediate input."
        )
    if resp.status_code == 404 or (resp.status_code == 200 and not resp.json()):
        raise GeocodeError(
            f"route create: address '{raw_address}' could not be geocoded "
            "by Nominatim (404). Retry with a different spelling or use "
            "'lat,lon' syntax."
        )
    resp.raise_for_status()
    payload = resp.json()
    first = payload[0]
    return Waypoint(
        raw_address=raw_address,
        lat=float(first["lat"]),
        lon=float(first["lon"]),
        geocode_provider="nominatim",
        geocode_at=_now_iso(),
    )


def batch_geocode(
    addresses: list[str],
    max_calls: int = 10,
    warn_at: int = 5,
) -> list[Waypoint]:
    """Geocode addresses in order, counting only real network calls.

    Short-circuited `"lat,lon"` inputs do not count toward the cap.
    Stops once `max_calls` network calls have been made. Emits a WARN
    via `logging` the moment the `warn_at` threshold is reached.
    """
    waypoints: list[Waypoint] = []
    network_calls = 0
    warned = False
    for addr in addresses:
        short = _short_circuit(addr)
        if short is not None:
            waypoints.append(short)
            continue
        if network_calls >= max_calls:
            break
        network_calls += 1
        if network_calls >= warn_at and not warned:
            logger.warning(
                "warning: %d geocode calls approaching Nominatim fair-use limit",
                network_calls,
            )
            warned = True
        waypoints.append(geocode(addr))
    return waypoints
