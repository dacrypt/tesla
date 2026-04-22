"""REST endpoints for the native EV route planner (Phase 3).

Routes:
    POST /api/nav/plan                 — plan a route (Phase 1 default, Phase 2 if SoC
                                          flags set, graph A* if alternatives >= 2)
    POST /api/nav/plan/save            — persist a plan as a NavStore Route
    GET  /api/nav/plan/{name}/export   — export a saved Route as GPX or KML

No route data is transmitted to any upstream logging / analytics sink.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from tesla_cli.core.auth import tokens
from tesla_cli.core.config import load_config
from tesla_cli.core.nav.route import NavStore, Route, Waypoint
from tesla_cli.core.planner.chargers import (
    ChargerAuthError,
    ChargerLookupError,
    find_chargers_near_point,
)
from tesla_cli.core.planner.export import to_gpx, to_kml
from tesla_cli.core.planner.models import PlannedRoute
from tesla_cli.core.planner.mvp import plan_route
from tesla_cli.core.planner.routing import (
    RoutingAuthError,
    RoutingError,
    RoutingRateLimitError,
    get_engine,
)

router = APIRouter()


class PlanRequest(BaseModel):
    origin: str  # address or "lat,lon"
    destination: str
    car: str | None = None
    stops_every_km: float = 150.0
    network: str = "any"
    min_power_kw: float | None = None
    router: str = "openroute"
    soc_start: float = 0.8  # 0.0-1.0
    soc_target: float = 0.2
    min_arrival_soc: float = 0.10
    battery_kwh: float = 75.0
    use_elevation: bool = True
    use_weather: bool = True
    alternatives: int = 1  # 1 = Phase 1 algo; >=2 = graph A*


class PlanResponse(BaseModel):
    plan: PlannedRoute | None = None
    alternatives: list[PlannedRoute] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SaveRequest(BaseModel):
    name: str
    plan: PlannedRoute


def _parse_endpoint(raw: str) -> tuple[str, tuple[float, float]]:
    """Accept 'lat,lon' short-circuit or geocode the string via Nominatim."""
    import re

    latlon_re = re.compile(r"^-?\d+(\.\d+)?,\s*-?\d+(\.\d+)?$")
    if latlon_re.match(raw.strip()):
        lat_s, lon_s = raw.strip().split(",", 1)
        try:
            return raw, (float(lat_s), float(lon_s.strip()))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"bad coords: {raw}") from exc
    from tesla_cli.core.nav.geocode import GeocodeError, geocode

    try:
        wp = geocode(raw)
    except GeocodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return raw, (wp.lat, wp.lon)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.post("/plan", response_model=PlanResponse)
def plan_endpoint(req: PlanRequest) -> PlanResponse:
    """Plan an EV route with charger stops.

    - `alternatives == 1` → Phase 1 / Phase 2 linear planner (default).
    - `alternatives >= 2` → graph-based A* with N ranked alternatives.
    """
    cfg = load_config()
    warnings: list[str] = []

    origin_addr, origin_ll = _parse_endpoint(req.origin)
    dest_addr, dest_ll = _parse_endpoint(req.destination)

    # Routing engine
    try:
        engine = get_engine(req.router, cfg)
    except RoutingAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # OCM key
    ocm_key = (
        cfg.planner.openchargemap_key
        or tokens.get_token(tokens.PLANNER_OPENCHARGEMAP_KEY)
        or ""
    )
    if not ocm_key:
        raise HTTPException(
            status_code=401,
            detail=(
                "OpenChargeMap API key not configured. Get one free at "
                "https://openchargemap.org/site/profile/applications"
            ),
        )

    def charger_finder(lat: float, lon: float):
        return find_chargers_near_point(
            lat,
            lon,
            ocm_key,
            radius_km=10.0,
            network=req.network,
            min_power_kw=req.min_power_kw,
        )

    # Phase selection
    from tesla_cli.core.planner.car_models import resolve_car_model

    car_alias = req.car or cfg.planner.default_car_model
    resolved_model_id = resolve_car_model(car_alias)

    use_phase2 = (
        req.alternatives >= 2
        or req.soc_target != 0.2
        or req.min_arrival_soc != 0.10
        or req.battery_kwh != 75.0
        or not req.use_elevation
        or not req.use_weather
    )

    try:
        primary_plan = _build_linear_plan(
            req=req,
            cfg=cfg,
            origin_addr=origin_addr,
            origin_ll=origin_ll,
            dest_addr=dest_addr,
            dest_ll=dest_ll,
            engine=engine,
            charger_finder=charger_finder,
            resolved_model_id=resolved_model_id,
            car_alias=car_alias,
            use_phase2=use_phase2,
        )
    except RoutingAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RoutingRateLimitError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RoutingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ChargerAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ChargerLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    alternatives: list[PlannedRoute] = []
    if req.alternatives >= 2:
        alternatives = _build_graph_alternatives(
            req=req,
            cfg=cfg,
            primary_plan=primary_plan,
            resolved_model_id=resolved_model_id,
            car_alias=car_alias,
            origin_ll=origin_ll,
            dest_ll=dest_ll,
            warnings=warnings,
        )

    return PlanResponse(plan=primary_plan, alternatives=alternatives, warnings=warnings)


def _build_linear_plan(
    *,
    req: PlanRequest,
    cfg,
    origin_addr: str,
    origin_ll: tuple[float, float],
    dest_addr: str,
    dest_ll: tuple[float, float],
    engine,
    charger_finder,
    resolved_model_id: str | None,
    car_alias: str | None,
    use_phase2: bool,
) -> PlannedRoute:
    """Build the primary PlannedRoute (Phase 1 MVP or Phase 2 SoC-aware)."""
    if use_phase2:
        from tesla_cli.core.planner.calibrated import plan_with_soc
        from tesla_cli.core.planner.consumption import get_model
        from tesla_cli.core.planner.elevation import ElevationError, get_elevation_profile
        from tesla_cli.core.planner.weather import WeatherAuthError, get_ambient_temp

        consumption_model = get_model(resolved_model_id)

        fetch_elev = None
        if req.use_elevation:

            def fetch_elev(poly):  # pragma: no cover - network path
                try:
                    return get_elevation_profile(poly)
                except ElevationError:
                    return []

        fetch_temp = None
        if req.use_weather:
            owm_key = (
                cfg.planner.openweather_key
                or tokens.get_token(tokens.PLANNER_WEATHER_KEY)
                or ""
            )
            if owm_key:

                def fetch_temp(lat, lon):  # pragma: no cover - network path
                    try:
                        return get_ambient_temp(lat, lon, owm_key)
                    except WeatherAuthError:
                        return None

        return plan_with_soc(
            origin_address=origin_addr,
            origin_latlon=origin_ll,
            destination_address=dest_addr,
            destination_latlon=dest_ll,
            routing=engine,
            charger_finder=charger_finder,
            consumption_model=consumption_model,
            initial_soc_kwh=req.soc_start * req.battery_kwh,
            battery_kwh=req.battery_kwh,
            target_soc_kwh=req.soc_target * req.battery_kwh,
            min_arrival_soc_kwh=req.min_arrival_soc * req.battery_kwh,
            stops_every_km=req.stops_every_km,
            car_model_alias=car_alias,
            initial_soc_frac=req.soc_start,
            emit_abrp_link=True,
            fetch_elevation=fetch_elev,
            fetch_temp=fetch_temp,
        )
    return plan_route(
        origin_address=origin_addr,
        origin_latlon=origin_ll,
        destination_address=dest_addr,
        destination_latlon=dest_ll,
        routing=engine,
        charger_finder=charger_finder,
        stops_every_km=req.stops_every_km,
        car_model_alias=car_alias,
        initial_soc=req.soc_start,
        emit_abrp_link=True,
    )


def _build_graph_alternatives(
    *,
    req: PlanRequest,
    cfg,
    primary_plan: PlannedRoute,
    resolved_model_id: str | None,
    car_alias: str | None,
    origin_ll: tuple[float, float],
    dest_ll: tuple[float, float],
    warnings: list[str],
) -> list[PlannedRoute]:
    """Build graph-based alternatives (Phase 3). Never raises — swallows to warnings."""
    try:
        from tesla_cli.core.planner.consumption import get_model
        from tesla_cli.core.planner.graph import plan_alternatives

        model = get_model(resolved_model_id)
        alt_sequences = plan_alternatives(
            origin=origin_ll,
            destination=dest_ll,
            chargers=primary_plan.stops,
            consumption_model=model,
            initial_soc_kwh=req.soc_start * req.battery_kwh,
            battery_kwh=req.battery_kwh,
            target_soc_kwh=req.soc_target * req.battery_kwh,
            min_arrival_soc_kwh=req.min_arrival_soc * req.battery_kwh,
            max_alternatives=req.alternatives,
        )
        if not alt_sequences:
            warnings.append(
                "graph planner returned no feasible alternatives — falling back to primary plan"
            )
            return []

        out: list[PlannedRoute] = []
        for seq in alt_sequences:
            alt_plan = primary_plan.model_copy(update={"stops": list(seq)})
            out.append(alt_plan)
        return out
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"alternatives unavailable: {exc}")
        return []


@router.post("/plan/save")
def plan_save(req: SaveRequest) -> dict:
    """Persist a PlannedRoute as a NavStore Route."""
    import re

    if not re.match(r"^[a-z0-9_-]{1,32}$", req.name):
        raise HTTPException(status_code=400, detail="invalid route name")
    store = NavStore()
    store.save_route(req.plan.to_nav_route(req.name))
    return {"ok": True, "name": req.name, "stops": len(req.plan.stops)}


@router.get("/plan/{name}/export")
def plan_export(name: str, fmt: str = Query("gpx", pattern="^(gpx|kml)$")) -> Response:
    """Export a saved Route as GPX or KML."""
    import re

    if not re.match(r"^[a-z0-9_-]{1,32}$", name):
        raise HTTPException(status_code=400, detail="invalid route name")
    store = NavStore()
    route = store.get_route(name)
    if route is None:
        raise HTTPException(status_code=404, detail=f"no route named '{name}'")

    plan = _route_to_minimal_plan(route)
    if fmt == "gpx":
        body = to_gpx(plan)
        media = "application/gpx+xml"
    else:
        body = to_kml(plan)
        media = "application/vnd.google-earth.kml+xml"
    return Response(
        content=body,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{name}.{fmt}"',
        },
    )


def _route_to_minimal_plan(route: Route) -> PlannedRoute:
    """Project a NavStore Route to a minimal PlannedRoute for export.

    The nav Route does not carry SoC or distance info, so we synthesize a
    PlannedRoute using the first waypoint as origin and the last as destination;
    remaining waypoints become charging stops.
    """
    if not route.waypoints:
        raise HTTPException(status_code=400, detail="route has no waypoints")
    wps: list[Waypoint] = route.waypoints
    if len(wps) == 1:
        origin = destination = wps[0]
        stops: list[Waypoint] = []
    else:
        origin = wps[0]
        destination = wps[-1]
        stops = wps[1:-1]
    from tesla_cli.core.planner.models import ChargerSuggestion

    charger_stops = [
        ChargerSuggestion(
            ocm_id=i + 1,
            name=wp.raw_address,
            lat=wp.lat,
            lon=wp.lon,
            network="unknown",
        )
        for i, wp in enumerate(stops)
    ]
    return PlannedRoute(
        origin_address=origin.raw_address,
        origin_latlon=(origin.lat, origin.lon),
        destination_address=destination.raw_address,
        destination_latlon=(destination.lat, destination.lon),
        total_distance_km=0.0,
        total_duration_min=0,
        stops=charger_stops,
        planned_at=route.created_at or _now_iso(),
        routing_provider="nav-store",
    )
