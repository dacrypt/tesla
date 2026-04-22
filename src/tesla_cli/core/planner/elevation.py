"""open-elevation client for polyline elevation profile lookup.

open-elevation is a free, no-key public API:
    https://open-elevation.com/

Privacy: sampled polyline points are sent to open-elevation when this module is
used. `--no-elevation` on `nav plan` opts out entirely.
"""

from __future__ import annotations

import httpx

OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"


class ElevationError(Exception):
    """open-elevation call failed (network, HTTP >= 400, or parse error)."""


def _sample_polyline(
    polyline: list[tuple[float, float]], samples: int
) -> list[tuple[float, float]]:
    """Evenly sample `samples` points from the polyline by cumulative distance."""
    if samples <= 0 or not polyline:
        return []
    if len(polyline) <= samples:
        return list(polyline)
    # Evenly-spaced indices along the polyline (approximation — good enough for
    # highway-scale elevation sampling).
    n = len(polyline)
    step = (n - 1) / (samples - 1) if samples > 1 else 0
    return [polyline[min(int(round(i * step)), n - 1)] for i in range(samples)]


def get_elevation_profile(
    polyline: list[tuple[float, float]],
    samples: int = 50,
    api_key: str | None = None,  # unused; kept for call-site symmetry
    timeout_s: float = 30.0,
) -> list[float]:
    """Return sampled elevations (meters) along the polyline.

    Raises ElevationError on any upstream failure. The caller decides whether
    to swallow (opt-out) or propagate.
    """
    pts = _sample_polyline(polyline, samples)
    if not pts:
        return []
    body = {"locations": [{"latitude": la, "longitude": lo} for la, lo in pts]}
    try:
        r = httpx.post(
            OPEN_ELEVATION_URL,
            json=body,
            timeout=timeout_s,
            headers={"User-Agent": "tesla-cli"},
        )
    except httpx.HTTPError as exc:
        raise ElevationError(f"open-elevation request failed: {exc}") from exc
    if r.status_code == 429:
        raise ElevationError("open-elevation rate-limited")
    if r.status_code >= 400:
        raise ElevationError(f"open-elevation HTTP {r.status_code}")
    try:
        data = r.json()
    except ValueError as exc:
        raise ElevationError(f"open-elevation returned invalid JSON: {exc}") from exc
    results = data.get("results") or []
    if len(results) != len(pts):
        raise ElevationError(
            f"open-elevation returned {len(results)} elevations for {len(pts)} points"
        )
    try:
        return [float(x.get("elevation", 0.0)) for x in results]
    except (TypeError, ValueError) as exc:
        raise ElevationError(f"open-elevation malformed result: {exc}") from exc
