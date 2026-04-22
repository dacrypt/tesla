"""Multi-stop navigation — `tesla nav` sub-app (v4.9.2, manual-advance).

See: .omc/plans/nav-route-telemetry.md

Design notes:
- CRUD for routes + places, stored in `~/.tesla-cli/nav.toml`.
- `route go` blocks until trip complete or Ctrl-C; exit codes:
    0 = trip complete, 130 = SIGINT, 1 = API error, 2 = auto-advance unavailable.
- Auto-advance via real telemetry deferred to v4.9.2.1 (see ArrivalSource
  protocol in `core/nav/arrival.py`). v4.9.2 ships `NullArrivalSource` and a
  guaranteed-shipping `nav route next` manual-advance command.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import typer

from tesla_cli.cli.commands.vehicle import _with_wake
from tesla_cli.cli.output import console, render_success
from tesla_cli.core.auth import tokens
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.nav.arrival import ArrivalDetector, NullArrivalSource
from tesla_cli.core.nav.geocode import GeocodeError, batch_geocode, geocode
from tesla_cli.core.nav.importers import (
    detect_and_parse,
    parse_gpx,
    parse_kml,
    parse_takeout_csv,
    parse_takeout_geojson,
)
from tesla_cli.core.nav.route import NavStore, Place, Route
from tesla_cli.core.planner.chargers import (
    ChargerAuthError,
    ChargerLookupError,
    find_chargers_near_point,
    probe_taxonomy,
)
from tesla_cli.core.planner.mvp import plan_route
from tesla_cli.core.planner.routing import (
    RoutingAuthError,
    RoutingError,
    RoutingRateLimitError,
    get_engine,
)

nav_app = typer.Typer(name="nav", help="Multi-stop navigation (routes + places, v4.9.2).")

route_app = typer.Typer(help="Multi-stop navigation routes (manual-advance, v4.9.2).")
place_app = typer.Typer(help="Named-address book for reuse in routes.")
consumption_app = typer.Typer(help="Consumption model calibration (Phase 2).")

nav_app.add_typer(route_app, name="route")
nav_app.add_typer(place_app, name="place")
nav_app.add_typer(consumption_app, name="consumption")


VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")
_NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise typer.BadParameter(f"Invalid name '{name}' — must match ^[a-z0-9_-]{{1,32}}$")


def _dispatch_share(vin: str, raw_address: str) -> None:
    """Send one waypoint to the car via the signed `share` command."""
    from tesla_cli.core.nav.dispatch import send_place

    _with_wake(lambda b, v: send_place(b, v, raw_address), vin)


# ─── route sub-app ───────────────────────────────────────────────────────────


@route_app.command("create", help="Create a new named route from addresses or 'lat,lon' pairs.")
def route_create(
    name: str = typer.Argument(..., help="Route name (a-z, 0-9, _, -; 1-32 chars)."),
    addresses: list[str] = typer.Argument(  # noqa: B008
        ..., help="Waypoint addresses or 'lat,lon' pairs, in order."
    ),
    max_geocode: int = typer.Option(
        10,
        "--max-geocode",
        help="Hard cap on Nominatim geocode calls for this route (default 10).",
    ),
) -> None:
    _validate_name(name)
    if len(addresses) < 1:
        raise typer.BadParameter("At least one waypoint required.")

    # Count network-bound inputs up front for the hard cap.
    store = NavStore()
    place_lookup = {p.alias: p.raw_address for p in store.list_places()}
    resolved_raw: list[str] = [place_lookup.get(a, a) for a in addresses]
    network_addrs = [
        a for a in resolved_raw if not re.match(r"^-?\d+(\.\d+)?,\s*-?\d+(\.\d+)?$", a.strip())
    ]
    if len(network_addrs) > max_geocode:
        console.print(
            f"[red]route create: too many unresolved addresses "
            f"({len(network_addrs)} > {max_geocode}). Pre-geocode with 'lat,lon' "
            "syntax or split into multiple routes.[/red]",
            markup=True,
        )
        raise typer.Exit(1)

    try:
        waypoints = batch_geocode(resolved_raw, max_calls=max_geocode, warn_at=5)
    except GeocodeError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc

    if len(waypoints) < len(resolved_raw):
        console.print("[red]route create: cap reached before all addresses resolved[/red]")
        raise typer.Exit(1)

    route = Route(name=name, waypoints=waypoints, created_at=_now_iso())
    store.save_route(route)
    render_success(f"Route '{name}' saved with {len(waypoints)} waypoint(s).")


@route_app.command("list", help="List all saved routes.")
def route_list() -> None:
    store = NavStore()
    routes = store.list_routes()
    if not routes:
        console.print("[dim]No routes saved.[/dim]")
        return
    for r in routes:
        console.print(f"  {r.name} — {len(r.waypoints)} waypoint(s), created {r.created_at}")


@route_app.command("show", help="Show waypoints of a saved route without re-geocoding.")
def route_show(name: str = typer.Argument(..., help="Route name.")) -> None:
    _validate_name(name)
    store = NavStore()
    route = store.get_route(name)
    if route is None:
        console.print(f"[red]No route named '{name}'[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{route.name}[/bold] (created {route.created_at})")
    for idx, wp in enumerate(route.waypoints, start=1):
        console.print(
            f"  {idx}. {wp.raw_address}  → ({wp.lat:.5f}, {wp.lon:.5f})  "
            f"[dim]{wp.geocode_provider} @ {wp.geocode_at}[/dim]"
        )


@route_app.command("delete", help="Delete a saved route.")
def route_delete(name: str = typer.Argument(..., help="Route name.")) -> None:
    _validate_name(name)
    store = NavStore()
    if store.get_route(name) is None:
        console.print(f"[red]No route named '{name}'[/red]")
        raise typer.Exit(1)
    store.delete_route(name)
    render_success(f"Route '{name}' deleted.")


@route_app.command(
    "verify",
    help="Re-geocode waypoints older than 30 days. Pass --write to save changes.",
)
def route_verify(
    name: str = typer.Argument(..., help="Route name."),
    write: bool = typer.Option(
        False,
        "--write",
        help=(
            "Write re-geocoded coords to nav.toml. Without this flag, only prints stale entries."
        ),
    ),
) -> None:
    _validate_name(name)
    store = NavStore()
    route = store.get_route(name)
    if route is None:
        console.print(f"[red]No route named '{name}'[/red]")
        raise typer.Exit(1)

    now = datetime.now(UTC)
    stale_idx: list[int] = []
    for i, wp in enumerate(route.waypoints):
        try:
            then = datetime.strptime(wp.geocode_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except ValueError:
            continue
        if (now - then).days > 30:
            stale_idx.append(i)

    if not stale_idx:
        console.print("no stale waypoints")
        return

    if not write:
        for i in stale_idx:
            wp = route.waypoints[i]
            try:
                then = datetime.strptime(wp.geocode_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
                days = (now - then).days
            except ValueError:
                days = 0
            console.print(f"stale: {wp.raw_address} (geocoded {days} days ago)")
        return

    # --write: re-geocode in place
    for i in stale_idx:
        try:
            route.waypoints[i] = geocode(route.waypoints[i].raw_address)
        except GeocodeError as exc:
            console.print(f"[red]{exc}[/red]", markup=True)
            raise typer.Exit(1) from exc
    store.save_route(route)
    console.print(f"wrote {len(stale_idx)} waypoint(s)")


@route_app.command(
    "go",
    help="Dispatch waypoints of a route in order; blocks until trip complete or Ctrl-C.",
)
def route_go(
    name: str = typer.Argument(..., help="Route name."),
    tolerance: int = typer.Option(
        150, "--tolerance", help="Arrival tolerance in meters (default 150)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print dispatch plan without calling the Tesla API."
    ),
    simulate_arrival_after: int | None = typer.Option(
        None,
        "--simulate-arrival-after",
        help="[TEST ONLY] Fire synthetic arrival after N seconds (no real telemetry).",
    ),
    start_from: int = typer.Option(
        1, "--start-from", help="Resume from waypoint index (1-based; default 1)."
    ),
    max_wait: int = typer.Option(
        45, "--max-wait", help="Per-waypoint max wait in minutes (default 45)."
    ),
    vin: str | None = VinOption,
) -> None:
    _validate_name(name)
    store = NavStore()
    route = store.get_route(name)
    if route is None:
        console.print(f"[red]No route named '{name}'[/red]")
        raise typer.Exit(1)
    total = len(route.waypoints)
    if not (1 <= start_from <= total):
        raise typer.BadParameter(f"--start-from must be in 1..{total}")

    if dry_run:
        for idx, wp in enumerate(route.waypoints[start_from - 1 :], start=start_from):
            console.print(f"Would send: [wp {idx}/{total}] {wp.raw_address}")
        console.print("[green]Trip complete (dry-run)[/green]")
        return

    if simulate_arrival_after is None:
        console.print(
            "[yellow]Auto-advance not available in v4.9.2.[/yellow] "
            "Use 'tesla nav route next <name>' between legs, "
            "or re-run with --simulate-arrival-after <seconds> for testing."
        )
        raise typer.Exit(2)

    v = _vin(vin)
    for idx, wp in enumerate(route.waypoints[start_from - 1 :], start=start_from):
        console.print(f"[wp {idx}/{total}] dispatching → {wp.raw_address}")
        try:
            _dispatch_share(v, wp.raw_address)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]dispatch failed: {exc}[/red]", markup=True)
            raise typer.Exit(1) from exc

        source = NullArrivalSource(simulate_after_seconds=simulate_arrival_after, target=wp)
        detector = ArrivalDetector(
            waypoint=wp,
            tolerance_meters=float(tolerance),
            source=source,
            max_wait_seconds=max_wait * 60.0,
        )
        try:
            arrived = detector.wait()
        except KeyboardInterrupt:
            console.print(
                f"[yellow]cancelled at waypoint {idx}/{total}[/yellow]",
                err=True,
            )
            raise typer.Exit(130) from None
        if not arrived:
            console.print(
                f"[red]arrival source lost at waypoint {idx}/{total}[/red]",
                err=True,
            )
            raise typer.Exit(2)

    console.print("[green]Trip complete[/green]")


@route_app.command("next", help="Manually dispatch the next un-visited waypoint of a route.")
def route_next(
    name: str = typer.Argument(..., help="Route name."),
    vin: str | None = VinOption,
) -> None:
    _validate_name(name)
    store = NavStore()
    route = store.get_route(name)
    if route is None:
        console.print(f"[red]No route named '{name}'[/red]")
        raise typer.Exit(1)
    total = len(route.waypoints)

    state = store.read_state(name)
    next_index = int(state.get("next_index", 1))
    if next_index > total:
        next_index = 1  # wrap / reset

    wp = route.waypoints[next_index - 1]
    v = _vin(vin)
    try:
        _dispatch_share(v, wp.raw_address)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]dispatch failed: {exc}[/red]", markup=True)
        raise typer.Exit(1) from exc

    new_index = next_index + 1
    if new_index > total:
        store.write_state(name, 1, _now_iso())
        console.print(
            f"[wp {next_index}/{total}] dispatched → {wp.raw_address}\n[green]Trip complete[/green]"
        )
    else:
        store.write_state(name, new_index, _now_iso())
        console.print(
            f"[wp {next_index}/{total}] dispatched → {wp.raw_address} "
            f"(next: tesla nav route next {name})"
        )


@route_app.command("export", help="Export a saved nav Route as GPX or KML.")
def route_export(
    name: str = typer.Argument(..., help="Route name."),
    fmt: str = typer.Option("gpx", "--format", "-f", help="gpx|kml"),
    output: Path | None = typer.Option(  # noqa: B008
        None, "--output", "-o", help="Output file path (defaults to stdout)"
    ),
) -> None:
    _validate_name(name)
    if fmt not in ("gpx", "kml"):
        console.print(f"[red]unknown format '{fmt}' — use gpx or kml[/red]")
        raise typer.Exit(1)
    store = NavStore()
    route = store.get_route(name)
    if route is None:
        console.print(f"[red]No route named '{name}'[/red]")
        raise typer.Exit(1)
    if not route.waypoints:
        console.print(f"[red]Route '{name}' has no waypoints[/red]")
        raise typer.Exit(1)

    # Project a NavStore Route into a minimal PlannedRoute for export.
    from tesla_cli.core.planner.export import to_gpx, to_kml
    from tesla_cli.core.planner.models import ChargerSuggestion, PlannedRoute

    wps = route.waypoints
    origin_wp = wps[0]
    dest_wp = wps[-1] if len(wps) > 1 else wps[0]
    stop_wps = wps[1:-1] if len(wps) > 2 else []
    stops = [
        ChargerSuggestion(
            ocm_id=i + 1,
            name=wp.raw_address,
            lat=wp.lat,
            lon=wp.lon,
            network="unknown",
        )
        for i, wp in enumerate(stop_wps)
    ]
    plan = PlannedRoute(
        origin_address=origin_wp.raw_address,
        origin_latlon=(origin_wp.lat, origin_wp.lon),
        destination_address=dest_wp.raw_address,
        destination_latlon=(dest_wp.lat, dest_wp.lon),
        total_distance_km=0.0,
        total_duration_min=0,
        stops=stops,
        planned_at=route.created_at or _now_iso(),
        routing_provider="nav-store",
    )
    body = to_gpx(plan) if fmt == "gpx" else to_kml(plan)

    if output is None:
        console.print(body)
    else:
        output.write_text(body)
        render_success(f"Exported {fmt.upper()} → {output}")


# ─── place sub-app ───────────────────────────────────────────────────────────


@place_app.command("save", help="Save a named place (alias + address).")
def place_save(
    alias: str = typer.Argument(..., help="Short alias (a-z, 0-9, _, -)."),
    address: str = typer.Argument(..., help="Address or 'lat,lon' pair."),
) -> None:
    _validate_name(alias)
    store = NavStore()
    store.save_place(Place(alias=alias, raw_address=address))
    render_success(f"Place '{alias}' saved → {address}")


@place_app.command("list", help="List all saved places.")
def place_list() -> None:
    store = NavStore()
    places = store.list_places()
    if not places:
        console.print("[dim]No places saved.[/dim]")
        return
    for p in places:
        console.print(f"  {p.alias} → {p.raw_address}")


@place_app.command("delete", help="Delete a saved place.")
def place_delete(alias: str = typer.Argument(..., help="Place alias.")) -> None:
    _validate_name(alias)
    store = NavStore()
    if store.get_place(alias) is None:
        console.print(f"[red]No place named '{alias}'[/red]")
        raise typer.Exit(1)
    store.delete_place(alias)
    render_success(f"Place '{alias}' deleted.")


@place_app.command(
    "import", help="Bulk-import places from Google Takeout CSV/GeoJSON, KML, or GPX."
)
def place_import(
    path: Path = typer.Argument(..., help="Path to source file"),  # noqa: B008
    fmt: str = typer.Option(
        "auto", "--format", "-f", help="auto|takeout-csv|takeout-geojson|kml|gpx"
    ),
    tag: str | None = typer.Option(None, "--tag", help="Extra tag applied to every imported place"),
    max_geocode: int = typer.Option(
        20, "--max-geocode", help="Max Nominatim calls for entries missing coords"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print summary, don't write nav.toml"),
) -> None:
    try:
        if fmt == "auto":
            places = detect_and_parse(path)
        elif fmt == "takeout-csv":
            places = parse_takeout_csv(path)
        elif fmt == "takeout-geojson":
            places = parse_takeout_geojson(path)
        elif fmt == "kml":
            places = parse_kml(path)
        elif fmt == "gpx":
            places = parse_gpx(path)
        else:
            console.print(
                f"[red]Unknown format '{fmt}'. Use: auto|takeout-csv|takeout-geojson|kml|gpx[/red]",
                markup=True,
            )
            raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc

    if tag is not None:
        for place in places:
            if place.tags is None:
                place.tags = []
            place.tags.append(tag)

    # Geocode entries missing coords, up to max_geocode
    needing_geo = [p for p in places if p.lat is None or p.lon is None]
    if needing_geo:
        if len(needing_geo) > max_geocode:
            skipped_geo = len(needing_geo) - max_geocode
            needing_geo = needing_geo[:max_geocode]
            console.print(
                f"[yellow]geocode cap reached: skipping {skipped_geo} place(s) without coords[/yellow]",
                markup=True,
            )
        addresses = [p.raw_address for p in needing_geo]
        try:
            geocoded = batch_geocode(addresses, max_calls=max_geocode, warn_at=5)
        except GeocodeError as exc:
            console.print(f"[red]{exc}[/red]", markup=True)
            raise typer.Exit(1) from exc
        for place, wp in zip(needing_geo, geocoded, strict=False):
            place.lat = wp.lat
            place.lon = wp.lon
        # Remove places that still lack coords after geocode cap
        places = [p for p in places if p.lat is not None or p.lon is not None]

    if dry_run:
        from collections import Counter

        source_counts = Counter(p.source or "unknown" for p in places)
        summary = ", ".join(f"{src}: {n}" for src, n in source_counts.items())
        console.print(f"Would import {len(places)} place(s) from {path}: {summary}")
        return

    store = NavStore()
    imported, updated, skipped = store.save_places_bulk(places)
    console.print(
        f"imported: {imported}, updated: {updated}, skipped: {skipped} (collisions with hand-created)"
    )


_LATLON_INPUT_RE = re.compile(r"^-?\d+(\.\d+)?,\s*-?\d+(\.\d+)?$")


def _resolve_endpoint(raw: str) -> tuple[str, tuple[float, float]]:
    """Resolve a user-supplied address or 'lat,lon' to (raw, (lat, lon))."""
    if _LATLON_INPUT_RE.match(raw.strip()):
        lat_s, lon_s = raw.strip().split(",", 1)
        return raw, (float(lat_s), float(lon_s.strip()))
    wp = geocode(raw)
    return raw, (wp.lat, wp.lon)


@nav_app.command("plan", help="Plan an EV route: auto-suggest charging stops along a route.")
def nav_plan(
    origin: str = typer.Argument(..., help="Start address or 'lat,lon'"),
    destination: str = typer.Argument(..., help="Destination address or 'lat,lon'"),
    stops_every: float = typer.Option(
        150.0, "--stops-every", help="Interpolation interval (km) — LATAM-safe default."
    ),
    network: str = typer.Option("any", "--network", help="tesla | ccs | any"),
    min_power: float | None = typer.Option(None, "--min-power", help="Minimum charger power (kW)"),
    radius: float = typer.Option(
        10.0, "--radius", help="Search radius around each interp point (km)"
    ),
    router: str | None = typer.Option(
        None, "--router", help="openroute | osrm (default: from config)"
    ),
    car: str | None = typer.Option(
        None, "--car", help="Car model alias (e.g. model_y_lr) or ABRP id"
    ),
    soc_start: float = typer.Option(0.8, "--soc-start", help="Initial SoC fraction (0.0-1.0)"),
    soc_target: float = typer.Option(
        0.2, "--soc-target", help="Target SoC at destination / after each charge (0.0-1.0)"
    ),
    min_arrival_soc: float = typer.Option(
        0.10, "--min-arrival-soc", help="Minimum SoC at arrival (0.0-1.0)"
    ),
    battery_kwh: float = typer.Option(
        75.0, "--battery-kwh", help="Usable battery pack capacity (kWh)"
    ),
    no_elevation: bool = typer.Option(False, "--no-elevation", help="Skip open-elevation lookup"),
    no_weather: bool = typer.Option(False, "--no-weather", help="Skip OpenWeatherMap lookup"),
    abrp_link: bool = typer.Option(
        True,
        "--abrp-link/--no-abrp-link",
        help="Emit ABRP deep link as second opinion.",
    ),
    save_as: str | None = typer.Option(
        None, "--save-as", help="Persist as a nav Route with this name"
    ),
    alternatives: int = typer.Option(
        1,
        "--alternatives",
        help="Number of ranked alternatives (>=2 activates graph A*).",
    ),
    export: str | None = typer.Option(
        None,
        "--export",
        help="After planning, write the plan as gpx|kml to <save-as>.<ext> "
        "or /tmp/plan.<ext> if no --save-as.",
    ),
    output_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    cfg = load_config()

    # Resolve endpoints
    try:
        origin_addr, origin_ll = _resolve_endpoint(origin)
        dest_addr, dest_ll = _resolve_endpoint(destination)
    except GeocodeError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc

    # Build routing engine
    router_name = router or cfg.planner.router
    try:
        engine = get_engine(router_name, cfg)
    except RoutingAuthError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc

    # Resolve OCM key (keyring > config)
    ocm_key = (
        cfg.planner.openchargemap_key or tokens.get_token(tokens.PLANNER_OPENCHARGEMAP_KEY) or ""
    )
    if not ocm_key:
        console.print(
            "[red]OpenChargeMap API key not configured. Get one free at "
            "https://openchargemap.org/site/profile/applications then run: "
            "tesla config set planner-openchargemap-key <KEY>[/red]",
            markup=True,
        )
        raise typer.Exit(1)

    def charger_finder(lat: float, lon: float):
        return find_chargers_near_point(
            lat,
            lon,
            ocm_key,
            radius_km=radius,
            network=network,
            min_power_kw=min_power,
        )

    car_alias = car or cfg.planner.default_car_model

    # Decide Phase 1 (MVP) vs Phase 2 (SoC-aware). We engage Phase 2 when any
    # SoC flag diverges from Phase-1 defaults OR when a calibrated model exists
    # for the resolved car_model id.
    from tesla_cli.core.planner.car_models import resolve_car_model
    from tesla_cli.core.planner.consumption import (
        CALIBRATION_FILE,
        get_model,
    )

    resolved_model_id = resolve_car_model(car_alias)
    calibrated_exists = False
    if resolved_model_id and CALIBRATION_FILE.exists():
        try:
            import tomllib as _tomllib
        except ImportError:  # pragma: no cover
            import tomli as _tomllib  # type: ignore[no-redef]
        try:
            _cal = _tomllib.loads(CALIBRATION_FILE.read_text())
            calibrated_exists = resolved_model_id in _cal
        except Exception:
            calibrated_exists = False

    phase2 = (
        soc_target != 0.2
        or min_arrival_soc != 0.10
        or battery_kwh != 75.0
        or no_elevation
        or no_weather
        or calibrated_exists
    )

    try:
        if phase2:
            from tesla_cli.core.planner.calibrated import plan_with_soc
            from tesla_cli.core.planner.elevation import ElevationError, get_elevation_profile
            from tesla_cli.core.planner.weather import WeatherAuthError, get_ambient_temp

            consumption_model = get_model(resolved_model_id)

            fetch_elev = None
            if not no_elevation:

                def fetch_elev(poly):
                    try:
                        return get_elevation_profile(poly)
                    except ElevationError:
                        return []

            fetch_temp = None
            if not no_weather:
                owm_key = (
                    cfg.planner.openweather_key
                    or tokens.get_token(tokens.PLANNER_WEATHER_KEY)
                    or ""
                )
                if owm_key:

                    def fetch_temp(lat, lon):
                        try:
                            return get_ambient_temp(lat, lon, owm_key)
                        except WeatherAuthError:
                            return None

            plan = plan_with_soc(
                origin_address=origin_addr,
                origin_latlon=origin_ll,
                destination_address=dest_addr,
                destination_latlon=dest_ll,
                routing=engine,
                charger_finder=charger_finder,
                consumption_model=consumption_model,
                initial_soc_kwh=soc_start * battery_kwh,
                battery_kwh=battery_kwh,
                target_soc_kwh=soc_target * battery_kwh,
                min_arrival_soc_kwh=min_arrival_soc * battery_kwh,
                stops_every_km=stops_every,
                car_model_alias=car_alias,
                initial_soc_frac=soc_start,
                emit_abrp_link=abrp_link,
                fetch_elevation=fetch_elev,
                fetch_temp=fetch_temp,
            )
        else:
            plan = plan_route(
                origin_address=origin_addr,
                origin_latlon=origin_ll,
                destination_address=dest_addr,
                destination_latlon=dest_ll,
                routing=engine,
                charger_finder=charger_finder,
                stops_every_km=stops_every,
                car_model_alias=car_alias,
                initial_soc=soc_start,
                emit_abrp_link=abrp_link,
            )
    except RoutingAuthError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc
    except RoutingRateLimitError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc
    except RoutingError as exc:
        console.print(f"[red]routing error: {exc}[/red]", markup=True)
        raise typer.Exit(1) from exc
    except ChargerAuthError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc

    if output_json:
        console.print(plan.model_dump_json(indent=2))
    else:
        from rich.table import Table

        header = (
            f"[bold]{origin_addr}[/bold] → [bold]{dest_addr}[/bold]  "
            f"({plan.total_distance_km:.1f} km, {plan.total_duration_min} min, "
            f"via {plan.routing_provider})"
        )
        if plan.total_energy_kwh is not None:
            header += f"  |  est. energy: {plan.total_energy_kwh:.1f} kWh"
        console.print(header)
        if phase2 and plan.consumption_source:
            console.print(f"[dim]consumption model: {plan.consumption_source}[/dim]")
        if not plan.stops:
            console.print("[dim]No intermediate stops needed.[/dim]")
        else:
            table = Table(show_header=True)
            table.add_column("#", justify="right")
            table.add_column("Charger")
            table.add_column("km", justify="right")
            table.add_column("kW", justify="right")
            if phase2:
                table.add_column("arr SoC (kWh)", justify="right")
                table.add_column("dep SoC (kWh)", justify="right")
                table.add_column("charge (min)", justify="right")
            else:
                table.add_column("Connectors")
            for i, s in enumerate(plan.stops, start=1):
                kw = f"{s.max_power_kw:.0f}" if s.max_power_kw is not None else "?"
                if phase2:
                    arr = f"{s.arrival_soc_kwh:.1f}" if s.arrival_soc_kwh is not None else "-"
                    dep = f"{s.departure_soc_kwh:.1f}" if s.departure_soc_kwh is not None else "-"
                    chg = f"{s.charge_duration_min}" if s.charge_duration_min is not None else "-"
                    table.add_row(
                        str(i), s.name, f"{s.distance_from_route_km:.2f}", kw, arr, dep, chg
                    )
                else:
                    conns = ", ".join(s.connection_types) if s.connection_types else ""
                    table.add_row(str(i), s.name, f"{s.distance_from_route_km:.2f}", kw, conns)
            console.print(table)
            if phase2:
                for s in plan.stops:
                    if s.soc_warning:
                        console.print(f"[yellow]warning @ {s.name}: {s.soc_warning}[/yellow]")
        if plan.abrp_deep_link:
            console.print(f"ABRP: {plan.abrp_deep_link}")

    if save_as:
        _validate_name(save_as)
        store = NavStore()
        store.save_route(plan.to_nav_route(save_as))
        render_success(f"Route '{save_as}' saved ({len(plan.stops)} stops).")

    # Graph-based alternatives (Phase 3) — only triggered when alternatives >= 2
    if alternatives >= 2:
        from tesla_cli.core.planner.consumption import get_model
        from tesla_cli.core.planner.graph import plan_alternatives

        model = get_model(resolved_model_id)
        alt_seqs = plan_alternatives(
            origin=origin_ll,
            destination=dest_ll,
            chargers=plan.stops,
            consumption_model=model,
            initial_soc_kwh=soc_start * battery_kwh,
            battery_kwh=battery_kwh,
            target_soc_kwh=soc_target * battery_kwh,
            min_arrival_soc_kwh=min_arrival_soc * battery_kwh,
            max_alternatives=alternatives,
        )
        if not alt_seqs:
            console.print("[yellow]No feasible alternatives returned by graph planner.[/yellow]")
        else:
            console.print(f"[bold]{len(alt_seqs)} alternative(s) via graph A*:[/bold]")
            for i, seq in enumerate(alt_seqs, start=1):
                names = " → ".join(s.name for s in seq) if seq else "(direct)"
                console.print(f"  alt {i}: {len(seq)} stop(s)  {names}")

    # GPX / KML export (Phase 3)
    if export:
        from pathlib import Path as _Path

        from tesla_cli.core.planner.export import to_gpx, to_kml

        fmt = export.lower()
        if fmt not in ("gpx", "kml"):
            console.print(f"[red]unknown export format '{export}' — use gpx or kml[/red]")
            raise typer.Exit(1)
        body = to_gpx(plan) if fmt == "gpx" else to_kml(plan)
        out_path = (
            _Path(f"./{save_as}.{fmt}") if save_as else _Path(f"/tmp/plan.{fmt}")
        )
        out_path.write_text(body)
        render_success(f"Exported {fmt.upper()} → {out_path}")


@nav_app.command(
    "plan-probe-taxonomy",
    help="Fetch current OpenChargeMap operator/connection IDs for verification.",
)
def nav_plan_probe_taxonomy(
    output_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    cfg = load_config()
    ocm_key = (
        cfg.planner.openchargemap_key or tokens.get_token(tokens.PLANNER_OPENCHARGEMAP_KEY) or ""
    )
    if not ocm_key:
        console.print(
            "[red]OpenChargeMap API key not configured. Get one free at "
            "https://openchargemap.org/site/profile/applications then run: "
            "tesla config set planner-openchargemap-key <KEY>[/red]",
            markup=True,
        )
        raise typer.Exit(1)
    try:
        result = probe_taxonomy(ocm_key)
    except ChargerAuthError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc
    except ChargerLookupError as exc:
        console.print(f"[red]{exc}[/red]", markup=True)
        raise typer.Exit(1) from exc

    if output_json:
        import json as _json

        console.print(_json.dumps(result, indent=2))
        return
    console.print("[bold]Tesla operators:[/bold]")
    for op in result["tesla_operators"]:
        console.print(f"  {op['ID']}: {op['Title']}")
    console.print("[bold]Connection types:[/bold]")
    for c in result["connection_types"]:
        console.print(f"  {c['ID']}: {c['Title']}")


@place_app.command("send", help="Send a saved place to the car via Tesla nav.")
def place_send(
    alias: str = typer.Argument(..., help="Place alias"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print address, don't call backend"),
    vin: str | None = VinOption,
) -> None:
    _validate_name(alias)
    store = NavStore()
    place = store.get_place(alias)
    if place is None:
        console.print(f"[red]No place named '{alias}'[/red]", markup=True)
        raise typer.Exit(1)

    if place.raw_address:
        address = place.raw_address
    elif place.lat is not None and place.lon is not None:
        address = f"{place.lat},{place.lon}"
    else:
        console.print(f"[red]place '{alias}' has no usable address or coords[/red]", markup=True)
        raise typer.Exit(1)

    if dry_run:
        console.print(f"Would send: {address}")
        return

    v = _vin(vin)
    _dispatch_share(v, address)
    render_success(f"Sent '{alias}' → {address}")


# ─── consumption sub-app (Phase 2) ────────────────────────────────────────────


@consumption_app.command("calibrate", help="Fit consumption coefficients from TeslaMate drives.")
def consumption_calibrate(
    car: str | None = typer.Option(
        None, "--car", help="Car model alias (e.g. model_y_lr) or ABRP id"
    ),
    days: int = typer.Option(90, "--days", help="Days of drive history to use"),
    battery_kwh: float = typer.Option(75.0, "--battery-kwh", help="Battery nominal capacity"),
    vin: str | None = VinOption,
) -> None:
    from tesla_cli.core.backends.teslaMate import TeslaMateBacked
    from tesla_cli.core.planner.car_models import resolve_car_model
    from tesla_cli.core.planner.consumption import fit_from_dataset, save_calibrated

    cfg = load_config()
    if not cfg.teslaMate.database_url:
        console.print(
            "[red]Requires TeslaMate. Install:\n"
            "  uv pip install tesla-cli[teslaMate]\n"
            "  tesla teslaMate connect postgresql://user:pass@host/teslaMate[/red]",
            markup=True,
        )
        raise typer.Exit(1)

    car_id = resolve_car_model(car or cfg.planner.default_car_model) or (
        car or cfg.planner.default_car_model or "baseline"
    )
    try:
        backend = TeslaMateBacked(cfg.teslaMate.database_url, car_id=cfg.teslaMate.car_id)
        segments = backend.get_calibration_dataset(days=days, vin=vin, battery_kwh=battery_kwh)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]TeslaMate query failed: {exc}[/red]", markup=True)
        raise typer.Exit(1) from exc

    if not segments:
        console.print("[yellow]No drive segments returned — nothing to fit.[/yellow]")
        raise typer.Exit(1)

    model = fit_from_dataset(car_id, segments)
    save_calibrated(model)
    console.print(
        f"[green]Fitted[/green] {car_id}: base={model.base_wh_per_km:.1f} Wh/km, "
        f"speed_gain={model.speed_gain:.2f}, elev={model.elevation_wh_per_100m:.1f}, "
        f"temp_factor={model.temp_factor_at_minus10:.2f}"
    )
    line = f"  samples={model.samples}"
    if model.r_squared is not None:
        line += f"  r2={model.r_squared:.3f}"
    if model.mape_pct is not None:
        line += f"  MAPE={model.mape_pct:.1f}%"
    console.print(line)


@consumption_app.command("show", help="Show the fitted or baseline consumption model.")
def consumption_show(
    car: str | None = typer.Option(
        None, "--car", help="Car model alias (e.g. model_y_lr) or ABRP id"
    ),
) -> None:
    from tesla_cli.core.planner.car_models import resolve_car_model
    from tesla_cli.core.planner.consumption import get_model

    cfg = load_config()
    car_id = resolve_car_model(car or cfg.planner.default_car_model)
    model = get_model(car_id)
    console.print(f"[bold]consumption model for {model.car_model}[/bold]  (source: {model.source})")
    console.print(f"  base_wh_per_km:         {model.base_wh_per_km:.1f}")
    console.print(f"  speed_gain (90→130):    {model.speed_gain:.3f}")
    console.print(f"  elevation_wh_per_100m:  {model.elevation_wh_per_100m:.1f}")
    console.print(f"  temp_factor_at_minus10: {model.temp_factor_at_minus10:.3f}")
    if model.samples:
        console.print(f"  samples:                {model.samples}")
    if model.r_squared is not None:
        console.print(f"  r_squared:              {model.r_squared:.3f}")
    if model.mape_pct is not None:
        console.print(f"  MAPE_pct:               {model.mape_pct:.1f}")
    if model.fitted_at:
        console.print(f"  fitted_at:              {model.fitted_at}")
