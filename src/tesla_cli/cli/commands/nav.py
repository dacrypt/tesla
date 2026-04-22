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

nav_app.add_typer(route_app, name="route")
nav_app.add_typer(place_app, name="place")


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
    soc_start: float = typer.Option(
        0.8, "--soc-start", help="Initial SoC for --abrp-link (0.0-1.0)"
    ),
    abrp_link: bool = typer.Option(
        True,
        "--abrp-link/--no-abrp-link",
        help="Emit ABRP deep link as second opinion.",
    ),
    save_as: str | None = typer.Option(
        None, "--save-as", help="Persist as a nav Route with this name"
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

    try:
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

        console.print(
            f"[bold]{origin_addr}[/bold] → [bold]{dest_addr}[/bold]  "
            f"({plan.total_distance_km:.1f} km, {plan.total_duration_min} min, "
            f"via {plan.routing_provider})"
        )
        if not plan.stops:
            console.print("[dim]No intermediate stops needed.[/dim]")
        else:
            table = Table(show_header=True)
            table.add_column("#", justify="right")
            table.add_column("Charger")
            table.add_column("km from route", justify="right")
            table.add_column("kW", justify="right")
            table.add_column("Connectors")
            for i, s in enumerate(plan.stops, start=1):
                kw = f"{s.max_power_kw:.0f}" if s.max_power_kw is not None else "?"
                conns = ", ".join(s.connection_types) if s.connection_types else ""
                table.add_row(str(i), s.name, f"{s.distance_from_route_km:.2f}", kw, conns)
            console.print(table)
        if plan.abrp_deep_link:
            console.print(f"ABRP: {plan.abrp_deep_link}")

    if save_as:
        _validate_name(save_as)
        store = NavStore()
        store.save_route(plan.to_nav_route(save_as))
        render_success(f"Route '{save_as}' saved ({len(plan.stops)} stops).")


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
