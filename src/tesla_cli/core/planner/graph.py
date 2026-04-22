"""A* search over a charger graph with SoC as a state dimension.

Unlike Phase 1 (interp → nearest charger), this computes MULTIPLE candidate
routes by treating chargers within a corridor as graph nodes and SoC as part
of the state. Outputs ranked alternatives: fastest, fewest-stops, cheapest-charging.

IMPORTANT: This is a SPECULATIVE implementation of a genuine research problem
(EV routing with charge state). It is intentionally simplified and will need
calibration against real drives. Not a drop-in replacement for Phase 1's
mvp.plan_route — Phase 1 remains the default. Graph mode activates on
`tesla nav plan --alternatives N` (N >= 2).
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from tesla_cli.core.planner.consumption import ConsumptionModel, estimate_wh_per_km
from tesla_cli.core.planner.models import ChargerSuggestion
from tesla_cli.core.planner.mvp import _haversine_km

# Sentinel charger id for origin/destination pseudo-nodes
_ORIGIN_ID = -1
_DEST_ID = -2


@dataclass(frozen=True)
class _State:
    """Search state used for A* node expansion + dedupe."""

    charger_ocm_id: int  # _ORIGIN_ID / _DEST_ID or an OCM POI id
    soc_kwh_times_10: int  # discretized SoC (kWh * 10, rounded) for dedupe hashing
    stops_used: int


def _heuristic_minutes(
    from_pt: tuple[float, float],
    to_pt: tuple[float, float],
    avg_kmh: float = 80.0,
) -> float:
    """Haversine distance / avg speed — admissible lower bound on remaining minutes."""
    return _haversine_km(from_pt, to_pt) / max(avg_kmh, 1.0) * 60.0


def _edge_energy_kwh(
    *,
    from_pt: tuple[float, float],
    to_pt: tuple[float, float],
    model: ConsumptionModel,
    avg_speed_kmh: float,
) -> tuple[float, float]:
    """Return (distance_km, energy_kwh) for an edge between two points."""
    dist_km = _haversine_km(from_pt, to_pt)
    if dist_km <= 0:
        return 0.0, 0.0
    wh_per_km = estimate_wh_per_km(
        model,
        avg_speed_kmh=avg_speed_kmh,
        elevation_delta_m=0.0,
        ambient_temp_c=None,
        distance_km=dist_km,
    )
    return dist_km, (wh_per_km * dist_km) / 1000.0


def _charge_minutes(
    arrival_kwh: float, target_kwh: float, charge_power_kw: float
) -> float:
    """Simple linear charge-time model — 150 kW DC fast by default."""
    delta = max(0.0, target_kwh - max(arrival_kwh, 0.0))
    return (delta / max(charge_power_kw, 1.0)) * 60.0


def _effective_charge_power(c: ChargerSuggestion, default_kw: float = 150.0) -> float:
    """Estimated usable charge rate for this charger (kW)."""
    if c.max_power_kw is not None and c.max_power_kw > 0:
        return min(float(c.max_power_kw), 250.0)
    # Fallback: 50 kW for non-Tesla/CCS chargers without a reported rate
    return 50.0 if c.network != "tesla" else default_kw


def _run_a_star(
    *,
    origin: tuple[float, float],
    destination: tuple[float, float],
    chargers: list[ChargerSuggestion],
    consumption_model: ConsumptionModel,
    initial_soc_kwh: float,
    battery_kwh: float,
    target_soc_kwh: float,
    min_arrival_soc_kwh: float,
    avg_speed_kmh: float,
    forbidden_ids: set[int] | None = None,
) -> list[ChargerSuggestion] | None:
    """Run A* once from origin → destination. Returns ordered stop list or None."""
    forbidden_ids = forbidden_ids or set()
    nodes: dict[int, tuple[float, float]] = {_ORIGIN_ID: origin, _DEST_ID: destination}
    charger_by_id: dict[int, ChargerSuggestion] = {}
    for c in chargers:
        if c.ocm_id in forbidden_ids or c.ocm_id in (_ORIGIN_ID, _DEST_ID):
            continue
        nodes[c.ocm_id] = (c.lat, c.lon)
        charger_by_id[c.ocm_id] = c

    start = _State(
        charger_ocm_id=_ORIGIN_ID,
        soc_kwh_times_10=int(round(initial_soc_kwh * 10)),
        stops_used=0,
    )
    # (f_score, counter, state, path_of_charger_ids)
    counter = 0
    frontier: list[tuple[float, int, _State, tuple[int, ...]]] = []
    heapq.heappush(
        frontier,
        (_heuristic_minutes(origin, destination, avg_speed_kmh), counter, start, ()),
    )
    # g_score[state] = cost so far in minutes
    g_score: dict[_State, float] = {start: 0.0}
    # Safety cap — prevents runaway search on pathological inputs
    max_expansions = 2000
    expansions = 0

    while frontier and expansions < max_expansions:
        expansions += 1
        _, _, current, path = heapq.heappop(frontier)
        current_pt = nodes[current.charger_ocm_id]
        current_soc = current.soc_kwh_times_10 / 10.0

        # Goal: can we reach destination with >= min_arrival_soc_kwh?
        dist_km, energy_kwh = _edge_energy_kwh(
            from_pt=current_pt,
            to_pt=destination,
            model=consumption_model,
            avg_speed_kmh=avg_speed_kmh,
        )
        soc_after = current_soc - energy_kwh
        if soc_after >= min_arrival_soc_kwh:
            # Feasible final edge — return the path as ChargerSuggestion list.
            return [charger_by_id[cid] for cid in path if cid in charger_by_id]

        # Expand: try each remaining charger as the next stop
        for cid, c in charger_by_id.items():
            if cid in path:
                continue  # no revisiting
            c_pt = (c.lat, c.lon)
            dist_km, energy_kwh = _edge_energy_kwh(
                from_pt=current_pt,
                to_pt=c_pt,
                model=consumption_model,
                avg_speed_kmh=avg_speed_kmh,
            )
            arrival_soc = current_soc - energy_kwh
            if arrival_soc < min_arrival_soc_kwh:
                continue  # infeasible leg
            # Charge at this stop to target (simple policy)
            departure_soc = max(arrival_soc, min(target_soc_kwh, battery_kwh))
            charge_min = _charge_minutes(
                arrival_soc, departure_soc, _effective_charge_power(c)
            )
            drive_min = (dist_km / max(avg_speed_kmh, 1.0)) * 60.0
            edge_cost = drive_min + charge_min

            next_state = _State(
                charger_ocm_id=cid,
                soc_kwh_times_10=int(round(departure_soc * 10)),
                stops_used=current.stops_used + 1,
            )
            tentative_g = g_score[current] + edge_cost
            if tentative_g >= g_score.get(next_state, float("inf")):
                continue
            g_score[next_state] = tentative_g
            h = _heuristic_minutes(c_pt, destination, avg_speed_kmh)
            counter += 1
            heapq.heappush(
                frontier,
                (tentative_g + h, counter, next_state, path + (cid,)),
            )
    return None


def plan_alternatives(
    *,
    origin: tuple[float, float],
    destination: tuple[float, float],
    chargers: list[ChargerSuggestion],
    consumption_model: ConsumptionModel,
    initial_soc_kwh: float,
    battery_kwh: float,
    target_soc_kwh: float,
    min_arrival_soc_kwh: float,
    avg_speed_kmh: float = 80.0,
    max_alternatives: int = 3,
    k_best_strategy: str = "fastest",
) -> list[list[ChargerSuggestion]]:
    """Return a ranked list of alternative stop sequences.

    Approach (simplified Yen's k-shortest):
      1. Run A* once from origin to destination → primary path.
      2. For each stop in the primary path, re-run A* with that stop forbidden;
         collect up to `max_alternatives - 1` unique alternatives.
      3. De-dupe by stop-id sequence.

    If no feasible path exists, returns an empty list.
    """
    if max_alternatives <= 0:
        return []

    primary = _run_a_star(
        origin=origin,
        destination=destination,
        chargers=chargers,
        consumption_model=consumption_model,
        initial_soc_kwh=initial_soc_kwh,
        battery_kwh=battery_kwh,
        target_soc_kwh=target_soc_kwh,
        min_arrival_soc_kwh=min_arrival_soc_kwh,
        avg_speed_kmh=avg_speed_kmh,
    )
    if primary is None:
        return []

    alternatives: list[list[ChargerSuggestion]] = [primary]
    seen_signatures: set[tuple[int, ...]] = {tuple(s.ocm_id for s in primary)}

    # Perturb: forbid each stop in the primary and re-run
    for stop in primary:
        if len(alternatives) >= max_alternatives:
            break
        alt = _run_a_star(
            origin=origin,
            destination=destination,
            chargers=chargers,
            consumption_model=consumption_model,
            initial_soc_kwh=initial_soc_kwh,
            battery_kwh=battery_kwh,
            target_soc_kwh=target_soc_kwh,
            min_arrival_soc_kwh=min_arrival_soc_kwh,
            avg_speed_kmh=avg_speed_kmh,
            forbidden_ids={stop.ocm_id},
        )
        if alt is None:
            continue
        sig = tuple(s.ocm_id for s in alt)
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)
        alternatives.append(alt)

    # Optional rank by strategy (fastest is already the A* default)
    if k_best_strategy == "fewest_stops":
        alternatives.sort(key=len)
    elif k_best_strategy == "cheapest":
        # Proxy: fewer stops + lower total power weighting (slower charge = cheaper idle)
        alternatives.sort(
            key=lambda seq: (
                len(seq),
                sum(_effective_charge_power(s) for s in seq),
            )
        )

    return alternatives[:max_alternatives]
