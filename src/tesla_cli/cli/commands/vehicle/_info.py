"""Read-only vehicle queries: state, location, software, alerts, exports, reports.

Part of the ``tesla vehicle`` command group (see ``__init__.py``). Names that
tests patch on ``tesla_cli.cli.commands.vehicle`` (backend factory, config,
VIN resolution, ``time``) are looked up through the package as ``_v.<name>``.
"""

from __future__ import annotations

from tesla_cli.cli.commands import vehicle as _v
from tesla_cli.cli.commands.vehicle import (  # noqa: F401
    Location,
    Progress,
    SpinnerColumn,
    TextColumn,
    VehicleAsleepError,
    VinOption,
    console,
    is_json_mode,
    render_dict,
    render_model,
    render_success,
    render_table,
    typer,
    vehicle_app,
)


@vehicle_app.command("list")
def vehicle_list() -> None:
    """List all vehicles."""
    backend = _v._backend()
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching vehicles...", total=None)
        vehicles = backend.list_vehicles()

    rows = []
    for v in vehicles if isinstance(vehicles, list) else [vehicles]:
        rows.append(
            {
                "vin": v.get("vin", ""),
                "name": v.get("display_name", v.get("vehicle_name", "")),
                "state": v.get("state", ""),
                "model": v.get("model", v.get("vehicle_type", "")),
            }
        )
    render_table(rows, columns=["vin", "name", "state", "model"], title="Vehicles")


@vehicle_app.command("info")
def vehicle_info(vin: str | None = VinOption) -> None:
    """Show complete vehicle data."""
    v = _v._vin(vin)
    data = _v._with_wake(lambda b, v: b.get_vehicle_data(v), v)
    render_dict(data, title=f"Vehicle {v}")


@vehicle_app.command("location")
def vehicle_location(vin: str | None = VinOption) -> None:
    """Show vehicle GPS location with Google Maps link."""
    v = _v._vin(vin)
    drive = _v._with_wake(lambda b, v: b.get_drive_state(v), v)
    loc = Location.from_drive_state(drive)
    render_model(loc, title="Location")


@vehicle_app.command("map")
def vehicle_map(
    span: float = typer.Option(
        0.05, "--span", help="Degree span for map window (default 0.05 ≈ 5km)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Show ASCII terminal map with current vehicle position.

    tesla vehicle map
    tesla vehicle map --span 0.02
    tesla -j vehicle map
    """
    import json as _json
    import math
    import shutil

    v = _v._vin(vin)
    data = _v._with_wake(lambda b, v: b.get_drive_state(v), v)

    lat = data.get("latitude")
    lon = data.get("longitude")
    heading = data.get("heading") or 0
    speed = data.get("speed") or 0
    shift = data.get("shift_state") or "P"

    if lat is None or lon is None:
        console.print("[yellow]No GPS data available.[/yellow]")
        raise typer.Exit(1)

    if is_json_mode():
        console.print(
            _json.dumps(
                {"lat": lat, "lon": lon, "heading": heading, "speed": speed, "shift_state": shift}
            )
        )
        return

    # ── Grid dimensions (auto from terminal, min 40×18) ──────────────────────
    cols, rows = shutil.get_terminal_size((80, 24))
    map_w = min(cols - 4, 72)
    map_h = min(rows - 8, 22)
    # Ensure even numbers for clean center
    map_w = map_w if map_w % 2 == 0 else map_w - 1
    map_h = map_h if map_h % 2 == 0 else map_h - 1

    cx = map_w // 2  # vehicle column
    cy = map_h // 2  # vehicle row

    # Degrees per cell
    lat_span = span
    # Correct for longitude compression at given latitude
    lon_span = span / max(math.cos(math.radians(lat)), 0.01)

    dlat = lat_span / map_h  # degrees per row
    dlon = lon_span / map_w  # degrees per col

    # ── Heading arrow ─────────────────────────────────────────────────────────
    _ARROWS = {
        (0, 22): "↑",
        (23, 67): "↗",
        (68, 112): "→",
        (113, 157): "↘",
        (158, 202): "↓",
        (203, 247): "↙",
        (248, 292): "←",
        (293, 337): "↖",
        (338, 360): "↑",
    }
    arrow = "▲"
    for (lo, hi), sym in _ARROWS.items():
        if lo <= heading <= hi:
            arrow = sym
            break

    # ── Build grid ────────────────────────────────────────────────────────────
    # Geofence zones overlay
    cfg = _v.load_config()
    zones = cfg.geofences.zones

    def _zone_in_cell(row: int, col: int) -> bool:
        cell_lat = lat + (cy - row) * dlat
        cell_lon = lon + (col - cx) * dlon
        for zone in zones.values():
            zlat = zone.get("lat", 0)
            zlon = zone.get("lon", 0)
            zrad = zone.get("radius_km", 0.5)
            # haversine approx in km
            dlat_km = (cell_lat - zlat) * 111.0
            dlon_km = (cell_lon - zlon) * 111.0 * math.cos(math.radians(zlat))
            dist = math.sqrt(dlat_km**2 + dlon_km**2)
            if dist <= zrad:
                return True
        return False

    grid: list[list[str]] = []
    for row in range(map_h):
        line: list[str] = []
        for col in range(map_w):
            if row == cy and col == cx:
                line.append(f"[bold green]{arrow}[/bold green]")
            elif _zone_in_cell(row, col):
                line.append("[cyan]░[/cyan]")
            elif row == cy:
                line.append("[dim]─[/dim]")
            elif col == cx:
                line.append("[dim]│[/dim]")
            else:
                line.append("[dim]·[/dim]")
        grid.append(line)

    # ── Render ────────────────────────────────────────────────────────────────
    console.print()
    # Top coordinate label
    top_lat = lat + cy * dlat
    console.print(f"  [dim]N {top_lat:+.4f}°[/dim]")

    for row_idx, row_cells in enumerate(grid):
        row_str = "".join(row_cells)
        if row_idx == cy:
            row_lat = lat
            console.print(f"  {row_str}  [dim]{row_lat:+.4f}°[/dim]")
        else:
            console.print(f"  {row_str}")

    # Bottom scale
    scale_km = round(lon_span * 111.0 * math.cos(math.radians(lat)), 1)
    console.print(f"  [dim]S  ←{'─' * (map_w - 10)}→  {scale_km} km[/dim]")
    console.print(
        f"\n  [bold]{arrow}[/bold] Heading [bold]{heading}°[/bold]  "
        f"Speed [bold]{speed} mph[/bold]  "
        f"Shift [bold]{shift}[/bold]  "
        f"[dim]{lat:+.5f}, {lon:+.5f}[/dim]"
    )
    if zones:
        console.print(f"  [dim cyan]Geofence zones: {', '.join(zones.keys())}[/dim cyan]")
    console.print()


@vehicle_app.command("fleet-status")
def fleet_status() -> None:
    """Show status of all configured vehicles at once.

    tesla vehicle fleet-status
    """
    import json as _json
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cfg = _v.load_config()
    aliases = cfg.vehicles.aliases  # {alias: vin}
    default_vin = cfg.general.default_vin

    # Build list of (label, vin) pairs — include default VIN if not already in aliases
    vins: list[tuple[str, str]] = [(alias, vin) for alias, vin in aliases.items()]
    aliased_vins = set(aliases.values())
    if default_vin and default_vin not in aliased_vins:
        vins.append((f"...{default_vin[-6:]}", default_vin))

    if not vins:
        console.print("[yellow]No vehicles configured. Set default-vin or add aliases.[/yellow]")
        raise typer.Exit(1)

    backend = _v._backend()

    def _fetch(label: str, vin: str) -> dict:
        try:
            cs = backend.get_charge_state(vin)
            vs = backend.get_vehicle_state(vin)
            ds = backend.get_drive_state(vin)
            return {
                "alias": label,
                "vin": f"...{vin[-6:]}",
                "battery": f"{cs.get('battery_level', '--')}%",
                "range": f"{round(cs.get('battery_range', 0))} mi"
                if cs.get("battery_range")
                else "--",
                "charging": cs.get("charging_state", "--"),
                "locked": "Yes" if vs.get("locked") else "No",
                "sentry": "On" if vs.get("sentry_mode") else "Off",
                "location": f"{ds.get('latitude', 0):.4f},{ds.get('longitude', 0):.4f}"
                if ds.get("latitude")
                else "--",
            }
        except Exception as exc:
            return {
                "alias": label,
                "vin": f"...{vin[-6:]}",
                "battery": "--",
                "range": "--",
                "charging": "--",
                "locked": "--",
                "sentry": "--",
                "location": f"[red]{exc}[/red]",
            }

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(len(vins), 8)) as pool:
        futures = {pool.submit(_fetch, label, vin): (label, vin) for label, vin in vins}
        for future in as_completed(futures):
            rows.append(future.result())

    # Sort by alias for stable output
    rows.sort(key=lambda r: r["alias"])

    if is_json_mode():
        console.print(_json.dumps(rows, indent=2))
        return

    render_table(
        rows,
        columns=["alias", "vin", "battery", "range", "charging", "locked", "sentry", "location"],
        title="Fleet Status",
    )


@vehicle_app.command("software")
def vehicle_software(
    vin: str | None = VinOption,
    install: bool = typer.Option(False, "--install", help="Schedule the pending software update"),
) -> None:
    """Show software version and pending update status.

    tesla vehicle software              → current version + any pending update
    tesla vehicle software --install    → schedule the pending update to install
    tesla -j vehicle software | jq .current_version
    """
    import json as _json

    v = _v._vin(vin)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching software info...", total=None)
        data = _v._with_wake(lambda b, v: b.get_vehicle_state(v), v)

    current = data.get("car_version", "unknown")
    sw_update = data.get("software_update", {}) or {}
    update_status = sw_update.get("status", "")
    update_version = sw_update.get("version", "")
    download_pct = sw_update.get("download_percentage", 0)
    install_pct = sw_update.get("install_percentage", 0)
    expected_sec = sw_update.get("expected_duration_sec", 0)
    scheduled_ms = sw_update.get("scheduled_time_ms", 0)

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "current_version": current,
                    "update_status": update_status,
                    "update_version": update_version or None,
                    "download_percentage": download_pct,
                    "install_percentage": install_pct,
                    "expected_duration_min": round(expected_sec / 60) if expected_sec else None,
                    "scheduled_time_ms": scheduled_ms or None,
                },
                indent=2,
            )
        )
        return

    from rich.table import Table

    console.print()
    console.print(f"  [bold]Software version:[/bold]  [cyan]{current}[/cyan]")

    if not update_status or update_status == "":
        console.print("  [dim]No pending software update.[/dim]")
        return

    status_color = {
        "available": "yellow",
        "scheduled": "cyan",
        "downloading": "blue",
        "installing": "green",
        "wifi_wait": "dim",
        "appinstalled": "green",
    }.get(update_status, "white")

    console.print(
        f"\n  [bold]Update available:[/bold]  [{status_color}]{update_version}[/{status_color}]  "
        f"[dim]({update_status})[/dim]"
    )

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("k", style="dim", width=22)
    table.add_column("v")

    if download_pct:
        table.add_row("Download", f"{download_pct}%")
    if install_pct:
        table.add_row("Install progress", f"{install_pct}%")
    if expected_sec:
        table.add_row("Estimated duration", f"{round(expected_sec / 60)} min")
    if scheduled_ms:
        from datetime import UTC, datetime

        sched_dt = datetime.fromtimestamp(scheduled_ms / 1000, tz=UTC).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        table.add_row("Scheduled for", sched_dt)

    console.print(table)

    if install and update_status in ("available", "wifi_wait"):
        _v._with_wake(lambda b, v: b.command(v, "schedule_software_update", offset_sec=0), v)
        render_success(f"Software update to {update_version} scheduled")
    elif install:
        console.print(
            f"  [yellow]Cannot schedule install — current status: {update_status}[/yellow]"
        )


@vehicle_app.command("nearby")
def vehicle_nearby(
    vin: str | None = VinOption,
) -> None:
    """Show nearby Superchargers and destination chargers.

    tesla vehicle nearby
    tesla -j vehicle nearby | jq '.superchargers[] | select(.available_stalls > 0)'
    """
    import json as _json

    from rich.table import Table

    v = _v._vin(vin)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching nearby charging sites...", total=None)
        data = _v._with_wake(lambda b, v: b.get_nearby_charging_sites(v), v)

    superchargers = data.get("superchargers", [])
    destination = data.get("destination_charging", [])

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "superchargers": superchargers,
                    "destination_charging": destination,
                },
                indent=2,
                default=str,
            )
        )
        return

    if not superchargers and not destination:
        console.print("[yellow]No nearby charging sites found.[/yellow]")
        return

    if superchargers:
        table = Table(
            title=f"Nearby Superchargers ({len(superchargers)})",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Name", width=32)
        table.add_column("Dist", justify="right", width=8)
        table.add_column("Avail", justify="right", width=6)
        table.add_column("Total", justify="right", width=6)
        table.add_column("Type", width=8)

        for sc in superchargers:
            name = (sc.get("name") or "")[:31]
            dist_m = sc.get("distance_miles") or sc.get("distance_km") or 0
            dist_unit = "mi" if "distance_miles" in sc else "km"
            avail = sc.get("available_stalls", "?")
            total = sc.get("total_stalls", "?")
            sc_type = sc.get("type", "SC")
            avail_color = (
                "green"
                if isinstance(avail, int) and avail > 3
                else "yellow"
                if isinstance(avail, int) and avail > 0
                else "red"
            )
            table.add_row(
                name,
                f"{dist_m:.1f} {dist_unit}" if isinstance(dist_m, (int, float)) else str(dist_m),
                f"[{avail_color}]{avail}[/{avail_color}]",
                str(total),
                str(sc_type),
            )
        console.print()
        console.print(table)

    if destination:
        dtable = Table(
            title=f"Destination Chargers ({len(destination)})",
            show_header=True,
            header_style="bold blue",
        )
        dtable.add_column("Name", width=32)
        dtable.add_column("Dist", justify="right", width=8)
        dtable.add_column("Stalls", justify="right", width=7)

        for dc in destination:
            name = (dc.get("name") or "")[:31]
            dist_m = dc.get("distance_miles") or dc.get("distance_km") or 0
            dist_unit = "mi" if "distance_miles" in dc else "km"
            stalls = dc.get("total_stalls", "?")
            dtable.add_row(
                name,
                f"{dist_m:.1f} {dist_unit}" if isinstance(dist_m, (int, float)) else str(dist_m),
                str(stalls),
            )
        console.print()
        console.print(dtable)


@vehicle_app.command("alerts")
def vehicle_alerts(
    vin: str | None = VinOption,
) -> None:
    """Show recent vehicle alerts and fault codes.

    tesla vehicle alerts
    tesla -j vehicle alerts | jq '.[] | select(.audience | contains("CUSTOMER"))'
    """
    import json as _json

    from rich.table import Table

    v = _v._vin(vin)

    from tesla_cli.core.exceptions import BackendNotSupportedError

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            transient=True,
            disable=is_json_mode(),
        ) as p:
            p.add_task("Fetching recent alerts...", total=None)
            data = _v._with_wake(lambda b, v: b.get_recent_alerts(v), v)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)

    alerts = data if isinstance(data, list) else data.get("recent_alerts", [])

    if is_json_mode():
        console.print(_json.dumps(alerts, indent=2, default=str))
        return

    if not alerts:
        console.print("[green]No recent alerts.[/green]")
        return

    table = Table(
        title=f"Recent Vehicle Alerts ({len(alerts)})",
        show_header=True,
        header_style="bold yellow",
    )
    table.add_column("Name", width=36)
    table.add_column("Audience", width=12)
    table.add_column("Time", width=17)
    table.add_column("Expires", width=17)

    for alert in alerts:
        name = (alert.get("name") or alert.get("message") or "")[:35]
        audience = ",".join(alert.get("audiences", []))[:11]
        start = str(alert.get("started_at") or alert.get("time") or "")[:16]
        expires = str(alert.get("expires_at") or "")[:16]
        table.add_row(name, audience, start, expires)

    console.print()
    console.print(table)


@vehicle_app.command("release-notes")
def vehicle_release_notes(
    vin: str | None = VinOption,
) -> None:
    """Show OTA software release notes for the current firmware version.

    tesla vehicle release-notes
    tesla -j vehicle release-notes | jq '.[] | .title'
    """
    import json as _json

    from rich.panel import Panel

    v = _v._vin(vin)

    from tesla_cli.core.exceptions import BackendNotSupportedError

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            transient=True,
            disable=is_json_mode(),
        ) as p:
            p.add_task("Fetching release notes...", total=None)
            data = _v._with_wake(lambda b, v: b.get_release_notes(v), v)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)

    notes = data if isinstance(data, list) else data.get("release_notes", [])

    if is_json_mode():
        console.print(_json.dumps(notes, indent=2, default=str))
        return

    if not notes:
        console.print("[yellow]No release notes available.[/yellow]")
        return

    console.print()
    for note in notes:
        title = note.get("title") or note.get("subtitle") or "Update"
        subtitle = note.get("subtitle") or ""
        description = note.get("description") or note.get("text") or ""
        header = f"[bold cyan]{title}[/bold cyan]"
        if subtitle and subtitle != title:
            header += f"  [dim]{subtitle}[/dim]"
        body = description.strip()
        if not body:
            body = "[dim](no description)[/dim]"
        console.print(Panel(body, title=header, border_style="dim"))
        console.print()


@vehicle_app.command("tires")
def vehicle_tires(
    history: bool = typer.Option(
        False, "--history", "-H", help="Show historical data (Tessie only)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Show TPMS tire pressure readings.

    tesla vehicle tires
    tesla vehicle tires --history    # historical data via Tessie
    tesla -j vehicle tires | jq '{fl:.front_left_psi, fr:.front_right_psi}'
    """
    import json as _json

    from rich.table import Table as _Table

    v = _v._vin(vin)

    if history:
        from tesla_cli.core.backends.tessie import TessieBackend

        backend = _v._backend()
        if not isinstance(backend, TessieBackend):
            console.print("[yellow]Tire pressure history requires the Tessie backend.[/yellow]")
            console.print("[dim]Configure Tessie: tesla config set tessie-token <token>[/dim]")
            raise typer.Exit(1)
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            transient=True,
            disable=is_json_mode(),
        ) as p:
            p.add_task("Fetching tire pressure history...", total=None)
            records = backend.get_tire_pressure_history(v)
        if is_json_mode():
            console.print(_json.dumps(records, indent=2, default=str))
            return
        if not records:
            console.print("[yellow]No tire pressure history found.[/yellow]")
            return
        t = _Table(title="Tire Pressure History (Tessie)", header_style="bold cyan")
        first = records[0]
        for col in first:
            t.add_column(str(col))
        for row in records[:50]:
            t.add_row(*[str(row.get(k, "")) for k in first])
        console.print(t)
        return

    state = _v._with_wake(lambda b, v: b.get_vehicle_state(v), v)

    POSITIONS = [
        ("front_left", "tpms_pressure_fl", "tpms_soft_warning_fl", "tpms_hard_warning_fl"),
        ("front_right", "tpms_pressure_fr", "tpms_soft_warning_fr", "tpms_hard_warning_fr"),
        ("rear_left", "tpms_pressure_rl", "tpms_soft_warning_rl", "tpms_hard_warning_rl"),
        ("rear_right", "tpms_pressure_rr", "tpms_soft_warning_rr", "tpms_hard_warning_rr"),
    ]

    data = {}
    for label, psi_key, soft_key, hard_key in POSITIONS:
        bar = state.get(psi_key)
        psi = round(bar * 14.5038, 1) if bar else None
        data[label] = {
            "bar": bar,
            "psi": psi,
            "soft_warning": state.get(soft_key, False),
            "hard_warning": state.get(hard_key, False),
        }

    if is_json_mode():
        console.print(_json.dumps(data, indent=2, default=str))
        return

    from rich.table import Table

    table = Table(title="Tire Pressure (TPMS)", header_style="bold cyan")
    table.add_column("Tire", width=14)
    table.add_column("Bar", justify="right", width=6)
    table.add_column("PSI", justify="right", width=6)
    table.add_column("Status", width=10)

    for label, vals in data.items():
        bar_v = f"{vals['bar']:.2f}" if vals["bar"] else "—"
        psi_v = f"{vals['psi']}" if vals["psi"] else "—"
        if vals["hard_warning"]:
            status = "[red]HARD WARN[/red]"
        elif vals["soft_warning"]:
            status = "[yellow]LOW[/yellow]"
        elif vals["psi"]:
            status = "[green]OK[/green]"
        else:
            status = "[dim]N/A[/dim]"
        table.add_row(label.replace("_", " ").title(), bar_v, psi_v, status)

    console.print()
    console.print(table)
    last_seen = state.get("tpms_last_seen_pressure_time")
    if last_seen:
        console.print(f"  [dim]Last updated: {last_seen}[/dim]")


@vehicle_app.command("sentry-events")
def vehicle_sentry_events(
    limit: int = typer.Option(20, "--limit", "-n", help="Max events to show"),
    vin: str | None = VinOption,
) -> None:
    """Show recent Sentry Mode events (Fleet API only).

    Filters recent vehicle alerts to sentry-triggered events.

    tesla vehicle sentry-events
    tesla vehicle sentry-events --limit 50
    tesla -j vehicle sentry-events
    """
    import json as _json

    from tesla_cli.core.exceptions import BackendNotSupportedError

    v = _v._vin(vin)
    try:
        alerts = _v._with_wake(lambda b, v: b.get_recent_alerts(v), v)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)

    # Filter sentry-related alerts; if empty, show all
    sentry_keywords = ("sentry", "camera", "detection", "intrus", "motion", "tampering")
    sentry_events = [
        a
        for a in (alerts if isinstance(alerts, list) else alerts.get("alerts", []))
        if any(kw in str(a).lower() for kw in sentry_keywords)
    ] or (alerts if isinstance(alerts, list) else alerts.get("alerts", []))
    sentry_events = sentry_events[:limit]

    if is_json_mode():
        console.print(_json.dumps(sentry_events, indent=2, default=str))
        return

    if not sentry_events:
        console.print("[dim]No sentry events found.[/dim]")
        return

    render_table(
        [
            {
                "time": str(e.get("start_epoch_time") or e.get("created_at") or "")[:19],
                "name": str(e.get("name") or e.get("type") or "")[:40],
                "audience": str(e.get("audience") or "")[:20],
            }
            for e in sentry_events
        ],
        columns=["time", "name", "audience"],
        title=f"Sentry Events (last {len(sentry_events)})",
    )


@vehicle_app.command("summary")
def vehicle_summary(
    oneline: bool = typer.Option(
        False, "--oneline", "-1", help="Single-line output (tmux/cron friendly)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Compact vehicle snapshot.

    tesla vehicle summary              # Rich panel
    tesla vehicle summary --oneline    # single line for tmux/cron
    tesla -j vehicle summary           # JSON
    """
    import json as _json

    from rich.panel import Panel
    from rich.text import Text

    v = _v._vin(vin)
    data = _v._with_wake(lambda b, v: b.get_vehicle_data(v), v)

    if is_json_mode():
        console.print_json(_json.dumps(data, default=str))
        return

    cs = data.get("charge_state", {})
    cl = data.get("climate_state", {})
    ds = data.get("drive_state", {})
    vs = data.get("vehicle_state", {})

    if oneline:
        level = cs.get("battery_level", "?")
        locked = vs.get("locked", False)
        sentry = vs.get("sentry_mode", False)
        inside = cl.get("inside_temp")
        charging = cs.get("charging_state", "")
        parts = [f"🔋 {level}%"]
        parts.append(f"{'🔒 Locked' if locked else '🔓 Unlocked'}")
        parts.append(f"🛡 {'Sentry ON' if sentry else 'Sentry off'}")
        if inside is not None:
            parts.append(f"🌡 {inside}°C")
        if charging == "Charging":
            rate = cs.get("charger_power", 0)
            parts.append(f"⚡ {rate}kW")
        typer.echo(" | ".join(parts))
        return

    # Battery
    level = cs.get("battery_level", "?")
    range_mi = cs.get("battery_range", 0)
    range_km = round(range_mi * 1.60934, 1) if range_mi else "?"
    charge_state = cs.get("charging_state", "Unknown")
    limit = cs.get("charge_limit_soc", "?")

    # Charging details
    charge_line = f"⚡ {charge_state}"
    if charge_state == "Charging":
        rate = cs.get("charger_power", 0)
        eta = cs.get("time_to_full_charge", 0)
        eta_str = f"{int(eta)}h{int((eta % 1) * 60):02d}m" if eta else ""
        charge_line += f" @ {rate} kW — {eta_str} to {limit}%"
    elif charge_state == "Complete":
        charge_line += " ✓"
    elif charge_state == "Stopped":
        charge_line += f" (limit: {limit}%)"

    # Climate
    inside = cl.get("inside_temp")
    outside = cl.get("outside_temp")
    hvac = cl.get("is_climate_on", False)
    climate_line = ""
    if inside is not None:
        climate_line = f"🌡 {inside}°C inside"
        if outside is not None:
            climate_line += f" / {outside}°C outside"
        if hvac:
            climate_line += " — [green]HVAC ON[/green]"

    # Location
    lat = ds.get("latitude")
    lon = ds.get("longitude")
    speed = ds.get("speed") or 0
    loc_line = ""
    if lat and lon:
        loc_line = f"📍 {lat:.4f}, {lon:.4f}"
        if speed > 0:
            loc_line += f" — {speed} km/h"

    # State
    locked = vs.get("locked", False)
    sentry = vs.get("sentry_mode", False)
    odo = vs.get("odometer")
    sw = vs.get("car_version", "?")

    lock_icon = "🔒" if locked else "🔓"
    sentry_icon = "🛡 ON" if sentry else "🛡 off"

    lines = Text()
    lines.append(f"🔋 {level}% — {range_km} km — limit {limit}%\n")
    lines.append(f"{charge_line}\n")
    if climate_line:
        lines.append(f"{climate_line}\n")
    if loc_line:
        lines.append(f"{loc_line}\n")
    lines.append(
        f"{lock_icon} {'Locked' if locked else 'Unlocked'}  |  {sentry_icon}  |  🚗 {sw}\n"
    )
    if odo:
        odo_km = round(odo * 1.60934)
        lines.append(f"📏 {odo_km:,} km")

    vin_short = v[-6:] if len(v) > 6 else v
    console.print(Panel(lines, title=f"Tesla — {vin_short}", border_style="blue", padding=(0, 1)))


# ═══════════════════════════════════════════════════════════════════════════════
# Vehicle identity & specs (migrated from dossier)
# ═══════════════════════════════════════════════════════════════════════════════


@vehicle_app.command("vin")
def vehicle_vin(
    vin_arg: str | None = typer.Argument(None, help="VIN to decode (uses default if omitted)"),
) -> None:
    """Decode a Tesla VIN position by position.

    tesla vehicle vin
    tesla vehicle vin 7SAYGDEF1TF123456
    tesla -j vehicle vin
    """
    from tesla_cli.cli.commands.dossier import dossier_vin

    # dossier_vin accepts a single `vin` positional arg
    dossier_vin(vin=vin_arg)


@vehicle_app.command("option-codes")
def vehicle_option_codes() -> None:
    """Decode Tesla option codes from dossier data.

    tesla vehicle option-codes
    tesla -j vehicle option-codes
    """
    from tesla_cli.cli.commands.dossier import dossier_option_codes

    dossier_option_codes()


@vehicle_app.command("battery-health")
def vehicle_battery_health(
    limit: int = typer.Option(50, "--limit", "-n", help="Max snapshots to analyze"),
) -> None:
    """Estimate battery degradation from snapshot history.

    tesla vehicle battery-health
    tesla -j vehicle battery-health
    """
    from tesla_cli.cli.commands.dossier import dossier_battery_health

    dossier_battery_health(limit=limit)


@vehicle_app.command("profile")
def vehicle_profile() -> None:
    """Complete multi-source vehicle profile (Tesla API + RUNT + NHTSA + logistics).

    tesla vehicle profile
    tesla -j vehicle profile
    """
    from tesla_cli.cli.commands.dossier import dossier_show

    dossier_show()


@vehicle_app.command("export")
def vehicle_export(
    output: str = typer.Option(None, "--output", "-o", help="Output file path (default: stdout)"),
    fmt: str = typer.Option("json", "--format", "-f", help="Format: json or csv"),
    vin: str | None = VinOption,
) -> None:
    """Export current vehicle state to JSON or CSV file.

    tesla vehicle export                          # JSON to stdout
    tesla vehicle export -o state.json            # JSON to file
    tesla vehicle export -f csv -o state.csv      # CSV to file
    tesla vehicle export -o snapshot-$(date +%Y%m%d).json
    """
    import json as _json

    v = _v._vin(vin)
    data = _v._with_wake(lambda b, v: b.get_vehicle_data(v), v)

    if fmt == "csv":
        import csv as _csv
        import io

        # Flatten nested dicts for CSV
        flat: dict[str, str] = {}
        for section, values in data.items():
            if isinstance(values, dict):
                for k, val in values.items():
                    flat[f"{section}.{k}"] = str(val) if val is not None else ""
            else:
                flat[section] = str(values) if values is not None else ""

        if output:
            with open(output, "w", newline="", encoding="utf-8") as fh:
                writer = _csv.DictWriter(fh, fieldnames=sorted(flat.keys()))
                writer.writeheader()
                writer.writerow(flat)
            console.print(f"[green]Exported to {output}[/green] ({len(flat)} fields)")
        else:
            buf = io.StringIO()
            writer = _csv.DictWriter(buf, fieldnames=sorted(flat.keys()))
            writer.writeheader()
            writer.writerow(flat)
            console.print(buf.getvalue())
    else:
        # JSON
        json_str = _json.dumps(data, indent=2, default=str)
        if output:
            from pathlib import Path

            Path(output).write_text(json_str, encoding="utf-8")
            console.print(f"[green]Exported to {output}[/green]")
        else:
            console.print_json(json_str)


@vehicle_app.command("last-seen")
def vehicle_last_seen(
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
    vin: str | None = VinOption,
) -> None:
    """Show when the vehicle was last online and its current state.

    tesla vehicle last-seen
    tesla vehicle last-seen --oneline
    tesla -j vehicle last-seen
    """
    import json as _json
    from datetime import UTC, datetime

    v = _v._vin(vin)
    backend = _v._backend()

    try:
        data = backend.get_vehicle_data(v)
        online = True
    except VehicleAsleepError:
        data = {}
        online = False

    ds = data.get("drive_state", {})
    gps_ts = ds.get("gps_as_of") or ds.get("timestamp")

    last_seen_str = "unknown"
    ago_str = ""
    if gps_ts:
        try:
            if isinstance(gps_ts, (int, float)):
                last_dt = datetime.fromtimestamp(gps_ts / 1000 if gps_ts > 1e12 else gps_ts, tz=UTC)
            else:
                last_dt = datetime.fromisoformat(str(gps_ts))
            last_seen_str = last_dt.strftime("%Y-%m-%d %H:%M UTC")
            delta = datetime.now(tz=UTC) - last_dt
            hours = delta.total_seconds() / 3600
            if hours < 1:
                ago_str = f"{int(delta.total_seconds() / 60)}m ago"
            elif hours < 24:
                ago_str = f"{int(hours)}h ago"
            else:
                ago_str = f"{int(hours / 24)}d ago"
        except (ValueError, TypeError, OSError):
            pass

    state_str = "online" if online else "asleep"

    if is_json_mode():
        console.print_json(
            _json.dumps({"state": state_str, "last_seen": last_seen_str, "ago": ago_str})
        )
        return

    if oneline:
        parts = [f"{'🟢' if online else '🔴'} {state_str.title()}"]
        if ago_str:
            parts.append(ago_str)
        typer.echo(" | ".join(parts))
        return

    icon = "[green]🟢 Online[/green]" if online else "[dim]🔴 Asleep[/dim]"
    console.print(f"\n  {icon}")
    if last_seen_str != "unknown":
        console.print(f"  [dim]Last seen: {last_seen_str} ({ago_str})[/dim]")
    console.print()


@vehicle_app.command("status-line")
def vehicle_status_line(vin: str | None = VinOption) -> None:
    """Ultra-compact status for tmux, polybar, waybar, or shell prompts.

    Output: plain text, no Rich formatting, no colors — just icons + data.
    Designed to be called from shell scripts, tmux status-right, etc.

    tesla vehicle status-line
    # Output: 🔋 72% 🔒 🛡 🌡22°C

    tmux usage:
      set -g status-right '#(tesla vehicle status-line 2>/dev/null)'
    """
    v = _v._vin(vin)
    backend = _v._backend()

    try:
        data = backend.get_vehicle_data(v)
    except VehicleAsleepError:
        typer.echo("\U0001f4a4 asleep")
        return
    except Exception:
        typer.echo("\u274c offline")
        return

    cs = data.get("charge_state") or {}
    cl = data.get("climate_state") or {}
    vs = data.get("vehicle_state") or {}

    level = cs.get("battery_level", "?")
    locked = vs.get("locked", False)
    sentry = vs.get("sentry_mode", False)
    inside = cl.get("inside_temp")
    charging = cs.get("charging_state", "")

    parts = [f"\U0001f50b{level}%"]
    parts.append("\U0001f512" if locked else "\U0001f513")
    if sentry:
        parts.append("\U0001f6e1")
    if inside is not None:
        parts.append(f"\U0001f321{inside}\u00b0")
    if charging == "Charging":
        power = cs.get("charger_power", 0)
        parts.append(f"\u26a1{power}kW")

    typer.echo(" ".join(parts))


@vehicle_app.command("firmware-alerts")
def vehicle_firmware_alerts(
    vin: str | None = VinOption,
) -> None:
    """Show firmware alerts from Tessie.

    tesla vehicle firmware-alerts
    tesla -j vehicle firmware-alerts
    """
    import json as _json

    from rich.table import Table as _Table

    from tesla_cli.core.backends.tessie import TessieBackend

    cfg = _v.load_config()
    v = _v.resolve_vin(cfg, vin)
    backend = _v.get_vehicle_backend(cfg)

    if not isinstance(backend, TessieBackend):
        console.print("[yellow]firmware-alerts requires the Tessie backend.[/yellow]")
        console.print("[dim]Configure Tessie: tesla config set tessie-token <token>[/dim]")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching firmware alerts...", total=None)
        alerts = backend.get_firmware_alerts(v)

    if is_json_mode():
        console.print_json(_json.dumps(alerts, indent=2, default=str))
        return

    if not alerts:
        console.print("[green]No firmware alerts.[/green]")
        return

    t = _Table(title="Firmware Alerts (Tessie)", header_style="bold yellow")
    first = alerts[0] if alerts else {}
    cols = list(first.keys()) if first else ["alert"]
    for col in cols:
        t.add_column(str(col))
    for row in alerts:
        if isinstance(row, dict):
            t.add_row(*[str(row.get(k, "")) for k in cols])
        else:
            t.add_row(str(row))
    console.print(t)


@vehicle_app.command("weather")
def vehicle_weather(
    vin: str | None = VinOption,
) -> None:
    """Show current weather at vehicle location (Tessie).

    tesla vehicle weather
    tesla -j vehicle weather
    """
    import json as _json

    from tesla_cli.core.backends.tessie import TessieBackend

    cfg = _v.load_config()
    v = _v.resolve_vin(cfg, vin)
    backend = _v.get_vehicle_backend(cfg)

    if not isinstance(backend, TessieBackend):
        console.print("[yellow]weather requires the Tessie backend.[/yellow]")
        console.print("[dim]Configure Tessie: tesla config set tessie-token <token>[/dim]")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching weather data...", total=None)
        data = backend.get_weather(v)

    if is_json_mode():
        console.print_json(_json.dumps(data, indent=2, default=str))
        return

    # Render key weather fields nicely
    current = data.get("current", data)
    pairs = [
        ("Condition", current.get("condition") or current.get("description") or ""),
        ("Temperature", _fmt_temp(current.get("temp") or current.get("temperature"))),
        ("Feels like", _fmt_temp(current.get("feels_like") or current.get("apparent_temperature"))),
        (
            "Humidity",
            f"{current.get('humidity', '')}%" if current.get("humidity") is not None else "",
        ),
        (
            "Wind speed",
            f"{current.get('wind_speed', '')} m/s" if current.get("wind_speed") is not None else "",
        ),
        (
            "Visibility",
            f"{current.get('visibility', '')} m" if current.get("visibility") is not None else "",
        ),
        ("UV index", str(current.get("uvi") or current.get("uv_index") or "")),
    ]
    console.print()
    console.print(f"  [bold]Weather at vehicle location[/bold]  [dim](VIN: {v})[/dim]")
    for label, value in pairs:
        if value:
            console.print(f"  [dim]{label}:[/dim] {value}")


def _fmt_temp(val: float | int | None) -> str:
    """Format a temperature value (Celsius assumed from Tessie)."""
    if val is None:
        return ""
    return f"{val}°C"


@vehicle_app.command("consumption")
def vehicle_consumption(
    vin: str | None = VinOption,
) -> None:
    """Show energy consumption data (Tessie).

    tesla vehicle consumption
    tesla -j vehicle consumption
    """
    import json as _json

    from tesla_cli.core.backends.tessie import TessieBackend

    cfg = _v.load_config()
    v = _v.resolve_vin(cfg, vin)
    backend = _v.get_vehicle_backend(cfg)

    if not isinstance(backend, TessieBackend):
        console.print("[yellow]consumption requires the Tessie backend.[/yellow]")
        console.print("[dim]Configure Tessie: tesla config set tessie-token <token>[/dim]")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching consumption data...", total=None)
        data = backend.get_consumption(v)

    if is_json_mode():
        console.print_json(_json.dumps(data, indent=2, default=str))
        return

    # Render top-level key/value pairs
    console.print()
    console.print(f"  [bold]Energy Consumption[/bold]  [dim](VIN: {v})[/dim]")
    if isinstance(data, dict):
        for key, value in data.items():
            if value is not None:
                label = key.replace("_", " ").title()
                console.print(f"  [dim]{label}:[/dim] {value}")
    elif isinstance(data, list):
        from rich.table import Table as _Table

        if data:
            t = _Table(title="Energy Consumption (Tessie)", header_style="bold cyan")
            first = data[0]
            cols = list(first.keys()) if isinstance(first, dict) else ["value"]
            for col in cols:
                t.add_column(str(col))
            for row in data:
                if isinstance(row, dict):
                    t.add_row(*[str(row.get(k, "")) for k in cols])
                else:
                    t.add_row(str(row))
            console.print(t)
        console.print("\n[dim]Live stream stopped.[/dim]")


@vehicle_app.command("safety-score")
def vehicle_safety_score(vin: str | None = VinOption) -> None:
    """Show Tesla Safety Score (Insurance telematics).

    Displays overall safety score, per-category breakdown, and recent trip scores.
    Requires Fleet API backend.

    Categories tracked:
    - Forward Collision Warnings per 1000 miles
    - Hard Braking events
    - Aggressive Turning events
    - Unsafe Following events
    - Forced Autopilot Disengagements
    """
    import json as _json

    from tesla_cli.core.exceptions import ApiError

    v = _v._vin(vin)
    backend = _v._backend()

    try:
        data = backend.get_safety_score(v)
    except ApiError as exc:
        if exc.status_code in (404, 403):
            console.print(
                "[yellow]Safety Score not available for this account or vehicle.[/yellow]\n"
                "[dim]This endpoint may require Tesla Insurance enrollment.[/dim]"
            )
            raise typer.Exit(1)
        raise

    if is_json_mode():
        console.print_json(_json.dumps(data, default=str))
        return

    score = data.get("safety_score") if isinstance(data, dict) else None
    console.print()
    console.print("[bold]Tesla Safety Score[/bold]")
    console.print()

    if score is not None:
        color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
        console.print(f"  [bold]Overall Score:[/bold] [{color}]{score}/100[/{color}]")
        console.print()

    label_map = {
        "forward_collision_warnings": "Forward Collision Warnings (per 1000 mi)",
        "hard_braking": "Hard Braking Events",
        "aggressive_turning": "Aggressive Turning Events",
        "unsafe_following": "Unsafe Following Events",
        "forced_autopilot_disengagements": "Forced Autopilot Disengagements",
    }

    if isinstance(data, dict):
        for key, label in label_map.items():
            val = data.get(key)
            if val is not None:
                console.print(f"  [dim]{label}:[/dim] {val}")

    trips = data.get("trips") if isinstance(data, dict) else None
    if trips and isinstance(trips, list):
        console.print()
        console.print("[bold]Recent Trips[/bold]")
        rows = [
            {
                "date": t.get("date", ""),
                "score": t.get("score", ""),
                "distance_mi": t.get("distance_mi", ""),
            }
            for t in trips[:10]
        ]
        render_table(rows, columns=["date", "score", "distance_mi"], title="Trip Scores")

    console.print()
