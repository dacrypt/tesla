"""Phase 1 MVP planner: route -> interp every N km -> closest charger per interp."""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlencode

from tesla_cli.core.planner.car_models import resolve_car_model
from tesla_cli.core.planner.models import ChargerSuggestion, PlannedRoute
from tesla_cli.core.planner.routing import RoutingEngine

_EARTH_R_KM = 6371.0


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_R_KM * math.asin(math.sqrt(h))


def _cumulative_distances(polyline: list[tuple[float, float]]) -> list[float]:
    out = [0.0]
    for i in range(1, len(polyline)):
        out.append(out[-1] + _haversine_km(polyline[i - 1], polyline[i]))
    return out


def _interp_points(
    polyline: list[tuple[float, float]], every_km: float
) -> list[tuple[float, float]]:
    """Return polyline points at approximate every_km intervals (excluding start/end)."""
    if len(polyline) < 2:
        return []
    cum = _cumulative_distances(polyline)
    total = cum[-1]
    if total <= every_km:
        return []  # short route, no stops needed
    out: list[tuple[float, float]] = []
    target = every_km
    i = 0
    while target < total:
        while i < len(cum) - 1 and cum[i + 1] < target:
            i += 1
        if i >= len(cum) - 1:
            break
        seg_span = cum[i + 1] - cum[i]
        seg_frac = (target - cum[i]) / max(seg_span, 1e-9)
        (la1, lo1), (la2, lo2) = polyline[i], polyline[i + 1]
        out.append((la1 + (la2 - la1) * seg_frac, lo1 + (lo2 - lo1) * seg_frac))
        target += every_km
    return out


def build_abrp_link(
    origin: tuple[float, float],
    destination: tuple[float, float],
    car_model: str | None,
    initial_soc: float | None,
) -> str | None:
    """Build an ABRP deep link. Returns None when no car_model is resolved."""
    if not car_model:
        return None
    params: dict[str, str] = {
        "from_lat": f"{origin[0]:.6f}",
        "from_lon": f"{origin[1]:.6f}",
        "to_lat": f"{destination[0]:.6f}",
        "to_lon": f"{destination[1]:.6f}",
        "car_model": car_model,
    }
    if initial_soc is not None:
        params["initial_soc"] = str(int(initial_soc * 100))
    return f"https://abetterrouteplanner.com/?{urlencode(params)}"


def plan_route(
    *,
    origin_address: str,
    origin_latlon: tuple[float, float],
    destination_address: str,
    destination_latlon: tuple[float, float],
    routing: RoutingEngine,
    charger_finder: Callable[[float, float], list[ChargerSuggestion]],
    stops_every_km: float = 150.0,
    car_model_alias: str | None = None,
    initial_soc: float | None = None,
    emit_abrp_link: bool = True,
) -> PlannedRoute:
    """Plan a route: routing -> interp -> closest charger per interp."""
    # 1. Compute the route
    route = routing.compute_route(origin_latlon, destination_latlon)
    polyline: list[tuple[float, float]] = route["polyline"]
    total_km = float(route["total_distance_km"])
    total_min = int(route["total_duration_min"])

    # 2. Interpolate stops
    interp_points = _interp_points(polyline, stops_every_km)

    # 3. For each interp, find closest charger
    stops: list[ChargerSuggestion] = []
    seen_ocm_ids: set[int] = set()
    for idx, pt in enumerate(interp_points):
        try:
            candidates = charger_finder(pt[0], pt[1])
        except Exception as exc:  # noqa: BLE001
            print(f"charger lookup failed at interp {idx + 1}: {exc}", file=sys.stderr)
            continue
        if not candidates:
            print(
                f"no chargers found near interp {idx + 1} ({pt[0]:.4f},{pt[1]:.4f})",
                file=sys.stderr,
            )
            continue
        # Pick closest to interp, skipping ones already added (avoid duplicates)
        candidates.sort(key=lambda c: _haversine_km(pt, (c.lat, c.lon)))
        picked = next((c for c in candidates if c.ocm_id not in seen_ocm_ids), None)
        if picked is None:
            continue
        picked.distance_from_route_km = _haversine_km(pt, (picked.lat, picked.lon))
        picked.interp_index = idx + 1
        seen_ocm_ids.add(picked.ocm_id)
        stops.append(picked)

    car_model = resolve_car_model(car_model_alias)
    abrp_link = None
    if emit_abrp_link:
        abrp_link = build_abrp_link(origin_latlon, destination_latlon, car_model, initial_soc)

    return PlannedRoute(
        origin_address=origin_address,
        origin_latlon=origin_latlon,
        destination_address=destination_address,
        destination_latlon=destination_latlon,
        total_distance_km=total_km,
        total_duration_min=total_min,
        stops=stops,
        car_model=car_model,
        initial_soc=initial_soc,
        abrp_deep_link=abrp_link,
        planned_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        routing_provider=routing.name,
    )
