"""SoC-aware planner that extends the Phase 1 MVP with consumption tracking.

Given a consumption model + elevation profile + ambient temperatures, this
planner walks the route segment-by-segment and computes:
    - energy (kWh) per segment
    - arrival SoC at each charger
    - departure SoC at each charger (== target_soc_kwh unless the battery is
      already above that, in which case no charge is needed)
    - charging time estimate (simple linear curve)
    - any "insufficient range" warnings when arrival SoC < min_arrival_soc_kwh
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from tesla_cli.core.planner.car_models import resolve_car_model
from tesla_cli.core.planner.consumption import ConsumptionModel, estimate_wh_per_km
from tesla_cli.core.planner.models import ChargerSuggestion, PlannedRoute
from tesla_cli.core.planner.mvp import (
    _haversine_km,
    _interp_points,
    build_abrp_link,
)
from tesla_cli.core.planner.routing import RoutingEngine


def _segment_elevation_delta(
    polyline: list[tuple[float, float]],
    elevations: list[float] | None,
    from_pt: tuple[float, float],
    to_pt: tuple[float, float],
) -> float:
    """Return net elevation change (m) between two points along the polyline.

    Uses nearest-sampled elevations if an elevation profile is supplied, else 0.0.
    """
    if not elevations or not polyline:
        return 0.0
    # Map (from_pt, to_pt) to nearest sample indices in `polyline`.
    # `elevations` is assumed to be evenly-sampled across `polyline`.
    n_poly = len(polyline)
    n_elev = len(elevations)
    if n_poly == 0 or n_elev == 0:
        return 0.0

    def _nearest_elev(pt: tuple[float, float]) -> float:
        best_i = 0
        best_d = float("inf")
        for i, p in enumerate(polyline):
            d = (p[0] - pt[0]) ** 2 + (p[1] - pt[1]) ** 2
            if d < best_d:
                best_d = d
                best_i = i
        # map poly index → elevations index
        idx = int(round(best_i * (n_elev - 1) / max(n_poly - 1, 1)))
        idx = max(0, min(n_elev - 1, idx))
        return elevations[idx]

    return _nearest_elev(to_pt) - _nearest_elev(from_pt)


def plan_with_soc(
    *,
    origin_address: str,
    origin_latlon: tuple[float, float],
    destination_address: str,
    destination_latlon: tuple[float, float],
    routing: RoutingEngine,
    charger_finder: Callable[[float, float], list[ChargerSuggestion]],
    consumption_model: ConsumptionModel,
    initial_soc_kwh: float,
    battery_kwh: float,
    target_soc_kwh: float,
    min_arrival_soc_kwh: float,
    stops_every_km: float = 150.0,
    car_model_alias: str | None = None,
    initial_soc_frac: float | None = None,
    emit_abrp_link: bool = True,
    fetch_elevation: Callable[[list[tuple[float, float]]], list[float]] | None = None,
    fetch_temp: Callable[[float, float], float | None] | None = None,
    charge_power_kw: float = 150.0,
) -> PlannedRoute:
    """Build a route with per-segment SoC tracking.

    Algorithm:
      1. Route origin → destination → polyline + distance/duration.
      2. Interpolate stops every `stops_every_km`; pick closest qualifying charger.
      3. Optionally fetch elevation profile + ambient temps.
      4. Walk each leg (origin → stop1, stop1 → stop2, ..., stopN → dest):
         - compute Wh/km via `estimate_wh_per_km` → energy_kwh.
         - update running SoC, tag stop with arrival/departure SoC.
         - if arrival < min_arrival_soc_kwh → warning on that stop.
      5. Return PlannedRoute with `total_energy_kwh` and `segments` populated.
    """
    route = routing.compute_route(origin_latlon, destination_latlon)
    polyline: list[tuple[float, float]] = route["polyline"]
    total_km = float(route["total_distance_km"])
    total_min = int(route["total_duration_min"])

    interp_points = _interp_points(polyline, stops_every_km)

    # Find a charger per interp point (mirrors the MVP behaviour)
    stops: list[ChargerSuggestion] = []
    seen_ids: set[int] = set()
    for idx, pt in enumerate(interp_points):
        try:
            candidates = charger_finder(pt[0], pt[1])
        except Exception:
            continue
        if not candidates:
            continue
        candidates.sort(key=lambda c: _haversine_km(pt, (c.lat, c.lon)))
        picked = next((c for c in candidates if c.ocm_id not in seen_ids), None)
        if picked is None:
            continue
        picked.distance_from_route_km = _haversine_km(pt, (picked.lat, picked.lon))
        picked.interp_index = idx + 1
        seen_ids.add(picked.ocm_id)
        stops.append(picked)

    # Optional enrichment
    elevations: list[float] | None = None
    if fetch_elevation is not None and polyline:
        try:
            elevations = fetch_elevation(polyline)
        except Exception:
            elevations = None

    avg_speed_kmh = (total_km / max(total_min, 1)) * 60.0 if total_min > 0 else 90.0

    # Segment endpoints: origin → stop1.lat/lon → ... → destination
    seg_points: list[tuple[str, tuple[float, float]]] = [(origin_address, origin_latlon)]
    for s in stops:
        seg_points.append((s.name, (s.lat, s.lon)))
    seg_points.append((destination_address, destination_latlon))

    segments: list[dict] = []
    current_soc = float(initial_soc_kwh)
    total_energy_kwh = 0.0

    for i in range(len(seg_points) - 1):
        from_name, from_pt = seg_points[i]
        to_name, to_pt = seg_points[i + 1]
        dist_km = _haversine_km(from_pt, to_pt)
        # Crude duration: scale proportional to distance vs total
        duration_min = int(total_min * (dist_km / total_km)) if total_km > 0 else 0
        elev_delta = _segment_elevation_delta(polyline, elevations, from_pt, to_pt)
        # Midpoint ambient temp (if provided)
        temp_c: float | None = None
        if fetch_temp is not None:
            midpoint = ((from_pt[0] + to_pt[0]) / 2.0, (from_pt[1] + to_pt[1]) / 2.0)
            try:
                temp_c = fetch_temp(midpoint[0], midpoint[1])
            except Exception:
                temp_c = None

        wh_per_km = estimate_wh_per_km(
            consumption_model,
            avg_speed_kmh=avg_speed_kmh,
            elevation_delta_m=elev_delta,
            ambient_temp_c=temp_c,
            distance_km=max(dist_km, 0.1),
        )
        energy_kwh = wh_per_km * dist_km / 1000.0
        soc_after = current_soc - energy_kwh
        total_energy_kwh += energy_kwh

        # Update downstream SoC fields on the stop (if this leg ends at a stop)
        if i < len(stops):
            stop = stops[i]
            stop.arrival_soc_kwh = round(soc_after, 2)
            if soc_after < min_arrival_soc_kwh:
                stop.soc_warning = (
                    f"insufficient range — arrival SoC {soc_after:.1f} kWh < "
                    f"minimum {min_arrival_soc_kwh:.1f} kWh; add an earlier stop "
                    "or start with more charge"
                )
            # Charge to target (or leave as-is if already above)
            departure = max(soc_after, min(target_soc_kwh, battery_kwh))
            stop.departure_soc_kwh = round(departure, 2)
            kwh_added = max(0.0, departure - max(soc_after, 0.0))
            stop.charge_duration_min = int(round(kwh_added / max(charge_power_kw, 1.0) * 60.0))
            current_soc = departure
        else:
            current_soc = soc_after

        segments.append(
            {
                "from": from_name,
                "to": to_name,
                "distance_km": round(dist_km, 2),
                "duration_min": duration_min,
                "energy_kwh": round(energy_kwh, 2),
                "soc_arrive_kwh": round(soc_after, 2),
                "elevation_delta_m": round(elev_delta, 1),
                "ambient_temp_c": temp_c,
            }
        )

    car_model = resolve_car_model(car_model_alias)
    abrp_link = (
        build_abrp_link(origin_latlon, destination_latlon, car_model, initial_soc_frac)
        if emit_abrp_link
        else None
    )

    return PlannedRoute(
        origin_address=origin_address,
        origin_latlon=origin_latlon,
        destination_address=destination_address,
        destination_latlon=destination_latlon,
        total_distance_km=total_km,
        total_duration_min=total_min,
        stops=stops,
        car_model=car_model,
        initial_soc=initial_soc_frac,
        abrp_deep_link=abrp_link,
        planned_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        routing_provider=routing.name,
        total_energy_kwh=round(total_energy_kwh, 2),
        segments=segments,
        consumption_source=consumption_model.source,
    )
