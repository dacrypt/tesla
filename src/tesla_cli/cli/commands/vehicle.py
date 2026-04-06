"""Vehicle commands: tesla vehicle info/location/charge/climate/lock/unlock/..."""

from __future__ import annotations

import time

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from tesla_cli.cli.output import (
    console,
    is_json_mode,
    render_dict,
    render_model,
    render_success,
    render_table,
)
from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.exceptions import VehicleAsleepError
from tesla_cli.core.models.charge import ChargeState
from tesla_cli.core.models.climate import ClimateState
from tesla_cli.core.models.drive import Location

vehicle_app = typer.Typer(name="vehicle", help="Tesla vehicle data and control.")

# Common VIN option
VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias (uses default if omitted)")


def _backend():
    return get_vehicle_backend(load_config())


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


def _with_wake(fn, vin: str, retries: int = 2):
    """Execute fn, auto-waking the vehicle if asleep."""
    backend = _backend()
    for attempt in range(retries + 1):
        try:
            return fn(backend, vin)
        except VehicleAsleepError:
            if attempt == retries:
                raise
            console.print("[yellow]Vehicle asleep, waking up...[/yellow]")
            backend.wake_up(vin)
            time.sleep(5)


@vehicle_app.command("list")
def vehicle_list() -> None:
    """List all vehicles."""
    backend = _backend()
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
    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_vehicle_data(v), v)
    render_dict(data, title=f"Vehicle {v}")


@vehicle_app.command("location")
def vehicle_location(vin: str | None = VinOption) -> None:
    """Show vehicle GPS location with Google Maps link."""
    v = _vin(vin)
    drive = _with_wake(lambda b, v: b.get_drive_state(v), v)
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

    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_drive_state(v), v)

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
    cfg = load_config()
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


@vehicle_app.command("charge")
def vehicle_charge(
    vin: str | None = VinOption,
    action: str | None = typer.Argument(None, help="start | stop (omit to show status)"),
) -> None:
    """Show charge state or start/stop charging."""
    v = _vin(vin)

    if action == "start":
        _with_wake(lambda b, v: b.command(v, "charge_start"), v)
        render_success("Charging started")
    elif action == "stop":
        _with_wake(lambda b, v: b.command(v, "charge_stop"), v)
        render_success("Charging stopped")
    else:
        data = _with_wake(lambda b, v: b.get_charge_state(v), v)
        state = ChargeState.model_validate(data)
        render_model(state, title="Charge State")


@vehicle_app.command("climate")
def vehicle_climate(
    vin: str | None = VinOption,
    action: str | None = typer.Argument(None, help="on | off (omit to show status)"),
) -> None:
    """Show climate state or turn HVAC on/off."""
    v = _vin(vin)

    if action == "on":
        _with_wake(lambda b, v: b.command(v, "auto_conditioning_start"), v)
        render_success("Climate ON")
    elif action == "off":
        _with_wake(lambda b, v: b.command(v, "auto_conditioning_stop"), v)
        render_success("Climate OFF")
    else:
        data = _with_wake(lambda b, v: b.get_climate_state(v), v)
        state = ClimateState.model_validate(data)
        render_model(state, title="Climate State")


@vehicle_app.command("lock")
def vehicle_lock(vin: str | None = VinOption) -> None:
    """Lock the vehicle."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "door_lock"), v)
    render_success("Vehicle locked")


@vehicle_app.command("unlock")
def vehicle_unlock(vin: str | None = VinOption) -> None:
    """Unlock the vehicle."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "door_unlock"), v)
    render_success("Vehicle unlocked")


@vehicle_app.command("horn")
def vehicle_horn(vin: str | None = VinOption) -> None:
    """Honk the horn."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "honk_horn"), v)
    render_success("Horn honked")


@vehicle_app.command("flash")
def vehicle_flash(vin: str | None = VinOption) -> None:
    """Flash the lights."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "flash_lights"), v)
    render_success("Lights flashed")


@vehicle_app.command("wake")
def vehicle_wake(vin: str | None = VinOption) -> None:
    """Wake up the vehicle."""
    v = _vin(vin)
    backend = _backend()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Waking vehicle...", total=None)
        result = backend.wake_up(v)

    if result:
        render_success("Vehicle is awake")
    else:
        console.print("[yellow]Wake command sent. Vehicle may take a moment to respond.[/yellow]")


@vehicle_app.command("trunk")
def vehicle_trunk(
    which: str = typer.Argument("rear", help="rear | front (frunk)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview action without executing"),
    vin: str | None = VinOption,
) -> None:
    """Open trunk or frunk."""
    v = _vin(vin)
    if dry_run:
        console.print(f"[dim]Dry run:[/dim] Would open {which} trunk for VIN ...{v[-6:]}")
        return
    cmd = "actuate_trunk"
    param = "rear" if which == "rear" else "front"
    _with_wake(lambda b, v: b.command(v, cmd, which_trunk=param), v)
    render_success(f"{which.title()} trunk opened")


@vehicle_app.command("sentry")
def vehicle_sentry(
    enable: bool | None = typer.Option(None, "--on/--off", help="Turn Sentry Mode on or off"),
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
    vin: str | None = VinOption,
) -> None:
    """Show or toggle Sentry Mode.

    tesla vehicle sentry              → show status
    tesla vehicle sentry --oneline    → 🛡 Sentry ON
    tesla vehicle sentry --on         → enable
    tesla vehicle sentry --off        → disable
    """
    v = _vin(vin)

    if enable is None:
        # Show status
        data = _with_wake(lambda b, v: b.get_vehicle_state(v), v)
        sentry_on = data.get("sentry_mode", False)
        available = data.get("sentry_mode_available", True)
        status = "ON" if sentry_on else "OFF"
        status_color = "green" if sentry_on else "dim"

        if oneline:
            icon = "\U0001f6e1"
            typer.echo(f"{icon} Sentry {status}")
            return

        if is_json_mode():
            import json

            console.print(
                json.dumps(
                    {
                        "sentry_mode": sentry_on,
                        "sentry_mode_available": available,
                    }
                )
            )
            return

        console.print(f"\n  Sentry Mode: [{status_color}][bold]{status}[/bold][/{status_color}]")
        if not available:
            console.print(
                "  [yellow]Note: Sentry Mode not available (vehicle may not be parked)[/yellow]"
            )
        return

    cmd = "set_sentry_mode"
    _with_wake(lambda b, v: b.command(v, cmd, on=enable), v)
    state = "enabled" if enable else "disabled"
    render_success(f"Sentry Mode {state}")


@vehicle_app.command("trips")
def vehicle_trips(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of recent trips to show"),
    vin: str | None = VinOption,
) -> None:
    """Show recent trip summary from vehicle service data.

    Note: Detailed trip history requires TeslaMate or Fleet API telemetry.
    This command shows what's available from the Owner API service data.
    """
    v = _vin(vin)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching trip data...", total=None)
        try:
            svc_data = _with_wake(lambda b, v: b.get_service_data(v), v)
        except Exception:
            svc_data = {}

        drive_state = _with_wake(lambda b, v: b.get_drive_state(v), v)
        vehicle_state = _with_wake(lambda b, v: b.get_vehicle_state(v), v)

    if is_json_mode():
        import json

        console.print(
            json.dumps(
                {
                    "service_data": svc_data,
                    "drive_state": drive_state,
                    "vehicle_state": vehicle_state,
                },
                indent=2,
                default=str,
            )
        )
        return

    odo = vehicle_state.get("odometer", 0)
    last_lat = drive_state.get("latitude")
    last_lon = drive_state.get("longitude")
    last_speed = drive_state.get("speed", 0) or 0
    heading = drive_state.get("heading", 0)
    native_type = drive_state.get("native_type", "")

    console.print("\n[bold cyan]Trip Data[/bold cyan]")
    console.print(f"  Odometer: [bold]{odo:.1f} mi[/bold]")
    if last_lat:
        console.print(
            f"  Last location: {last_lat:.4f}, {last_lon:.4f}  (heading {heading}°, {last_speed} mph)"
        )
        console.print(f"  Maps: https://maps.google.com/?q={last_lat},{last_lon}")

    if native_type:
        console.print(f"  Native type: {native_type}")

    console.print(
        "\n[dim]Tip: For full trip history with route maps, energy usage, and stats,\n"
        "     connect TeslaMate: https://docs.teslamate.org[/dim]"
    )


@vehicle_app.command("windows")
def vehicle_windows(
    action: str = typer.Argument("vent", help="Action: vent or close"),
    vin: str | None = VinOption,
) -> None:
    """Vent or close all windows.

    tesla vehicle windows vent    → vent all windows ~4 cm
    tesla vehicle windows close   → close all windows
    """
    v = _vin(vin)
    action = action.lower()
    if action not in ("vent", "close"):
        console.print("[red]Action must be 'vent' or 'close'.[/red]")
        raise typer.Exit(1)
    # command: window_control, params: command="vent"|"close", lat=0, lon=0
    _with_wake(lambda b, v: b.command(v, "window_control", command=action, lat=0, lon=0), v)
    render_success(f"Windows {'vented' if action == 'vent' else 'closed'}")


@vehicle_app.command("charge-port")
def vehicle_charge_port(
    action: str = typer.Argument("open", help="Action: open, close, or stop"),
    vin: str | None = VinOption,
) -> None:
    """Control the charging port door.

    tesla vehicle charge-port open    → open the charge port door
    tesla vehicle charge-port close   → close the charge port door
    tesla vehicle charge-port stop    → stop charging (unlocks port)
    """
    v = _vin(vin)
    action = action.lower()
    CMD_MAP = {
        "open": "charge_port_door_open",
        "close": "charge_port_door_close",
        "stop": "charge_stop",
    }
    if action not in CMD_MAP:
        console.print("[red]Action must be 'open', 'close', or 'stop'.[/red]")
        raise typer.Exit(1)
    _with_wake(lambda b, v: b.command(v, CMD_MAP[action]), v)
    labels = {
        "open": "Charge port opened",
        "close": "Charge port closed",
        "stop": "Charging stopped",
    }
    render_success(labels[action])


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

    v = _vin(vin)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching software info...", total=None)
        data = _with_wake(lambda b, v: b.get_vehicle_state(v), v)

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
        _with_wake(lambda b, v: b.command(v, "schedule_software_update", offset_sec=0), v)
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

    v = _vin(vin)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching nearby charging sites...", total=None)
        data = _with_wake(lambda b, v: b.get_nearby_charging_sites(v), v)

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

    v = _vin(vin)

    from tesla_cli.core.exceptions import BackendNotSupportedError

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            transient=True,
            disable=is_json_mode(),
        ) as p:
            p.add_task("Fetching recent alerts...", total=None)
            data = _with_wake(lambda b, v: b.get_recent_alerts(v), v)
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

    v = _vin(vin)

    from tesla_cli.core.exceptions import BackendNotSupportedError

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            transient=True,
            disable=is_json_mode(),
        ) as p:
            p.add_task("Fetching release notes...", total=None)
            data = _with_wake(lambda b, v: b.get_release_notes(v), v)
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


@vehicle_app.command("valet")
def vehicle_valet(
    on: bool | None = typer.Option(None, "--on/--off", help="Enable or disable valet mode"),
    password: str = typer.Option("", "--password", "-p", help="4-digit PIN for valet mode"),
    vin: str | None = VinOption,
) -> None:
    """Show or toggle Valet Mode.

    tesla vehicle valet              # show status
    tesla vehicle valet --on --password 1234
    tesla vehicle valet --off
    """
    import json as _json

    v = _vin(vin)

    if on is None:
        # Show current status
        state = _with_wake(lambda b, v: b.get_vehicle_state(v), v)
        valet_active = state.get("valet_mode", False)
        if is_json_mode():
            console.print(_json.dumps({"valet_mode": valet_active}, indent=2))
            return
        status = "[green]ON[/green]" if valet_active else "[dim]OFF[/dim]"
        console.print(f"  Valet Mode: {status}")
        return

    _with_wake(lambda b, v: b.set_valet_mode(v, on=on, password=password), v)
    action = "enabled" if on else "disabled"
    if is_json_mode():
        console.print(_json.dumps({"valet_mode": on, "action": action}, indent=2))
        return
    render_success(f"Valet Mode {action}")


@vehicle_app.command("schedule-charge")
def vehicle_schedule_charge(
    time_str: str | None = typer.Argument(None, help="Charge time HH:MM (24h), e.g. 23:30"),
    off: bool = typer.Option(False, "--off", help="Disable scheduled charging"),
    vin: str | None = VinOption,
) -> None:
    """Set or disable scheduled charging.

    tesla vehicle schedule-charge 23:30   # charge at 11:30 PM
    tesla vehicle schedule-charge --off   # disable schedule
    tesla -j vehicle schedule-charge 06:00
    """
    import json as _json

    v = _vin(vin)

    if off:
        _with_wake(lambda b, v: b.set_scheduled_charging(v, enable=False, time_minutes=0), v)
        if is_json_mode():
            console.print(_json.dumps({"scheduled_charging": False}, indent=2))
            return
        render_success("Scheduled charging disabled")
        return

    if not time_str:
        # Show current schedule
        state = _with_wake(lambda b, v: b.get_charge_state(v), v)
        enabled = state.get("scheduled_charging_pending", False)
        sched_time = state.get("scheduled_charging_start_time")
        if is_json_mode():
            console.print(
                _json.dumps(
                    {
                        "scheduled_charging_pending": enabled,
                        "scheduled_charging_start_time": sched_time,
                    },
                    indent=2,
                )
            )
            return
        if enabled and sched_time:
            from datetime import datetime

            try:
                dt = datetime.fromtimestamp(int(sched_time), tz=datetime.UTC).strftime("%H:%M UTC")
            except Exception:
                dt = str(sched_time)
            console.print(f"  Scheduled Charging: [green]ON[/green] at {dt}")
        else:
            console.print("  Scheduled Charging: [dim]OFF[/dim]")
        return

    # Parse HH:MM → minutes since midnight
    try:
        parts = time_str.strip().split(":")
        hours, minutes = int(parts[0]), int(parts[1])
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError
    except (ValueError, IndexError):
        console.print("[red]Invalid time format. Use HH:MM (24h), e.g. 23:30[/red]")
        raise typer.Exit(1)

    time_minutes = hours * 60 + minutes
    _with_wake(lambda b, v: b.set_scheduled_charging(v, enable=True, time_minutes=time_minutes), v)

    if is_json_mode():
        console.print(
            _json.dumps(
                {"scheduled_charging": True, "time": time_str, "time_minutes": time_minutes},
                indent=2,
            )
        )
        return
    render_success(f"Scheduled charging set to {time_str} ({time_minutes} min from midnight)")


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

    v = _vin(vin)

    if history:
        from tesla_cli.core.backends.tessie import TessieBackend

        backend = _backend()
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

    state = _with_wake(lambda b, v: b.get_vehicle_state(v), v)

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


@vehicle_app.command("homelink")
def vehicle_homelink(
    vin: str | None = VinOption,
) -> None:
    """Trigger HomeLink (garage door opener) when near home location.

    tesla vehicle homelink
    """
    import json as _json

    v = _vin(vin)

    # Get current GPS coordinates for the HomeLink proximity check
    drive = _with_wake(lambda b, v: b.get_drive_state(v), v)
    lat = drive.get("latitude", 0.0) or 0.0
    lon = drive.get("longitude", 0.0) or 0.0

    _with_wake(lambda b, v: b.command(v, "trigger_homelink", lat=lat, lon=lon), v)

    if is_json_mode():
        console.print(_json.dumps({"homelink": "triggered", "lat": lat, "lon": lon}, indent=2))
        return
    render_success("HomeLink triggered")


@vehicle_app.command("dashcam")
def vehicle_dashcam(
    vin: str | None = VinOption,
) -> None:
    """Save the current dashcam clip to USB storage.

    tesla vehicle dashcam
    """
    import json as _json

    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "dashcam_save_clip"), v)

    if is_json_mode():
        console.print(_json.dumps({"dashcam_save": True}, indent=2))
        return
    render_success("Dashcam clip saved to USB storage")


@vehicle_app.command("rename")
def vehicle_rename(
    name: str = typer.Argument(..., help="New vehicle name"),
    vin: str | None = VinOption,
) -> None:
    """Rename the vehicle (requires firmware 2023.12+).

    tesla vehicle rename "My Tesla Y"
    """
    import json as _json

    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "set_vehicle_name", vehicle_name=name), v)

    if is_json_mode():
        console.print(_json.dumps({"name": name}, indent=2))
        return
    render_success(f"Vehicle renamed to '{name}'")


@vehicle_app.command("precondition")
def vehicle_precondition(
    on: bool = typer.Argument(..., help="Enable or disable max preconditioning"),
    vin: str | None = VinOption,
) -> None:
    """Toggle max preconditioning (blast heat/cool before a trip).

    tesla vehicle precondition true
    tesla vehicle precondition false
    tesla -j vehicle precondition true
    """
    import json as _json

    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "set_preconditioning_max", on=on), v)

    if is_json_mode():
        console.print(_json.dumps({"preconditioning_max": on}, indent=2))
        return
    status = "enabled" if on else "disabled"
    render_success(f"Max preconditioning {status}")


@vehicle_app.command("screenshot")
def vehicle_screenshot(
    vin: str | None = VinOption,
) -> None:
    """Trigger a screenshot of the vehicle's display (saves to TeslaConnect).

    tesla vehicle screenshot
    tesla -j vehicle screenshot
    """
    import json as _json

    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "trigger_vehicle_screenshot"), v)

    if is_json_mode():
        console.print(_json.dumps({"screenshot": "triggered"}, indent=2))
        return
    render_success("Screenshot triggered — check the TeslaConnect mobile app")


@vehicle_app.command("tonneau")
def vehicle_tonneau(
    action: str = typer.Argument(..., help="Action: open|close|stop|status"),
    vin: str | None = VinOption,
) -> None:
    """Control the Cybertruck tonneau cover.

    tesla vehicle tonneau open
    tesla vehicle tonneau close
    tesla vehicle tonneau stop
    tesla vehicle tonneau status
    tesla -j vehicle tonneau status
    """
    import json as _json

    v = _vin(vin)
    action = action.lower()

    if action == "status":
        state = _with_wake(lambda b, v: b.get_vehicle_state(v), v)
        tonneau_open = state.get("tonneau_open")
        door_state = state.get("tonneau_door_state", "unknown")
        data = {
            "tonneau_open": tonneau_open,
            "door_state": door_state,
        }
        if is_json_mode():
            console.print(_json.dumps(data, indent=2, default=str))
            return
        render_dict(data, title="Tonneau Cover Status")
        return

    command_map = {
        "open": "tonneau_open",
        "close": "tonneau_close",
        "stop": "tonneau_stop",
    }
    if action not in command_map:
        from tesla_cli.cli.output import console as _console

        _console.print(f"[red]Unknown action:[/red] {action}. Use: open|close|stop|status")
        raise typer.Exit(1)

    _with_wake(lambda b, v: b.command(v, command_map[action]), v)

    if is_json_mode():
        console.print(_json.dumps({"tonneau": action}, indent=2))
        return
    render_success(f"Tonneau cover {action} command sent")


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

    v = _vin(vin)
    try:
        alerts = _with_wake(lambda b, v: b.get_recent_alerts(v), v)
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


@vehicle_app.command("sw-update")
def vehicle_sw_update(
    watch: bool = typer.Option(
        False, "--watch", "-w", help="Watch mode: keep polling until update appears"
    ),
    interval: int = typer.Option(
        60, "--interval", "-i", help="Poll interval in minutes (watch mode)"
    ),
    notify: bool = typer.Option(
        False, "--notify", help="Send Apprise notification when update is detected"
    ),
    vin: str | None = VinOption,
) -> None:
    """Check for a pending OTA software update, or watch until one is available.

    tesla vehicle sw-update                          → one-shot check
    tesla vehicle sw-update --watch                 → poll every 60 min
    tesla vehicle sw-update --watch --interval 30   → poll every 30 min
    tesla vehicle sw-update --watch --notify        → + Apprise notification on detection
    """
    import json as _json

    v = _vin(vin)

    def _check_once() -> dict:
        """Fetch vehicle data and return software update info."""
        data = _with_wake(lambda b, v: b.get_vehicle_data(v), v)
        vs = data.get("vehicle_state", {})
        return {
            "current_version": vs.get("car_version", ""),
            "update_available": bool(
                vs.get("software_update", {}).get("status")
                in ("available", "scheduled", "installing", "downloading")
            ),
            "update_status": vs.get("software_update", {}).get("status", ""),
            "update_version": vs.get("software_update", {}).get("version", ""),
            "update_download_pct": vs.get("software_update", {}).get("download_perc", 0),
            "update_install_perc": vs.get("software_update", {}).get("install_perc", 0),
            "expected_duration_sec": vs.get("software_update", {}).get("expected_duration_sec", 0),
            "scheduled_time_ms": vs.get("software_update", {}).get("scheduled_time_ms", 0),
        }

    if not watch:
        info = _check_once()
        if is_json_mode():
            console.print(_json.dumps(info, indent=2))
            return
        from rich.panel import Panel
        from rich.table import Table as RTable

        t = RTable(show_header=False, box=None, padding=(0, 2))
        t.add_column("Key", style="dim", width=28)
        t.add_column("Value", style="bold")
        t.add_row("Current Version", info["current_version"])
        if info["update_available"]:
            t.add_row(
                "Update Status", f"[bold yellow]{info['update_status'].upper()}[/bold yellow]"
            )
            t.add_row("Update Version", f"[bold green]{info['update_version']}[/bold green]")
            if info["update_download_pct"]:
                t.add_row("Download", f"{info['update_download_pct']}%")
            if info["update_install_perc"]:
                t.add_row("Install", f"{info['update_install_perc']}%")
        else:
            t.add_row("Update Status", "[dim]No update pending[/dim]")
        console.print(Panel(t, title="[bold]Software Update Status[/bold]", border_style="cyan"))
        return

    # ── Watch mode ────────────────────────────────────────────────────────────
    import signal

    console.print(
        f"[dim]Watching for OTA updates every {interval} min. Press Ctrl+C to stop.[/dim]\n"
    )
    poll_secs = interval * 60
    try:
        while True:
            try:
                info = _check_once()
            except Exception as exc:
                console.print(f"[yellow]Poll error: {exc}[/yellow]")
                info = {}

            ts = __import__("datetime").datetime.now().strftime("%H:%M:%S")
            if info.get("update_available"):
                ver = info.get("update_version", "")
                status = info.get("update_status", "")
                console.print(
                    f"[bold green]✓ [{ts}] Update detected![/bold green] "
                    f"Version [bold]{ver}[/bold] — {status}"
                )
                if notify:
                    try:
                        import apprise

                        cfg = load_config()
                        urls = getattr(cfg.notifications, "apprise_urls", []) or []
                        if urls:
                            a = apprise.Apprise()
                            for u in urls:
                                a.add(u)
                            a.notify(
                                title="Tesla OTA Update Available",
                                body=f"Version {ver} is {status} on your Tesla.",
                            )
                            console.print("[dim]Apprise notification sent.[/dim]")
                    except Exception as exc:
                        console.print(f"[yellow]Notify error: {exc}[/yellow]")
                break
            else:
                cur = info.get("current_version", "—")
                console.print(
                    f"[dim][{ts}] No update — current: {cur}. Next check in {interval} min.[/dim]"
                )

            time.sleep(poll_secs)
    except (KeyboardInterrupt, signal.Signals):
        console.print("\n[dim]Stopped.[/dim]")


@vehicle_app.command("speed-limit")
def vehicle_speed_limit(
    limit_mph: int | None = typer.Option(None, "--limit", help="Set speed limit in mph (50–90)"),
    pin: str | None = typer.Option(None, "--pin", help="4-digit speed limit PIN"),
    on: bool = typer.Option(False, "--on", help="Activate speed limit mode (requires --pin)"),
    off: bool = typer.Option(False, "--off", help="Deactivate speed limit mode (requires --pin)"),
    clear: bool = typer.Option(
        False, "--clear", help="Clear the saved speed limit PIN (requires --pin)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Show or control Speed Limit Mode.

    tesla vehicle speed-limit                          → show current status
    tesla vehicle speed-limit --limit 65               → set limit to 65 mph
    tesla vehicle speed-limit --on --pin 1234          → activate speed limit mode
    tesla vehicle speed-limit --off --pin 1234         → deactivate speed limit mode
    tesla vehicle speed-limit --clear --pin 1234       → clear saved PIN
    """
    import json as _json

    v = _vin(vin)

    if on:
        if not pin:
            console.print("[red]--pin is required to activate speed limit mode.[/red]")
            raise typer.Exit(1)
        _with_wake(lambda b, v: b.command(v, "speed_limit_activate", pin=pin), v)
        render_success("Speed Limit Mode activated")
        return

    if off:
        if not pin:
            console.print("[red]--pin is required to deactivate speed limit mode.[/red]")
            raise typer.Exit(1)
        _with_wake(lambda b, v: b.command(v, "speed_limit_deactivate", pin=pin), v)
        render_success("Speed Limit Mode deactivated")
        return

    if clear:
        if not pin:
            console.print("[red]--pin is required to clear the speed limit PIN.[/red]")
            raise typer.Exit(1)
        _with_wake(lambda b, v: b.command(v, "speed_limit_clear_pin", pin=pin), v)
        render_success("Speed Limit PIN cleared")
        return

    if limit_mph is not None:
        if not (50 <= limit_mph <= 90):
            console.print("[red]Speed limit must be between 50 and 90 mph.[/red]")
            raise typer.Exit(1)
        _with_wake(lambda b, v: b.command(v, "speed_limit_set_limit", limit_mph=limit_mph), v)
        render_success(f"Speed limit set to {limit_mph} mph")
        return

    # ── Status (no flags) ────────────────────────────────────────────────────
    data = _with_wake(lambda b, v: b.get_vehicle_state(v), v)
    slm = data.get("speed_limit_mode", {}) if isinstance(data, dict) else {}
    active = slm.get("active", False)
    current_limit = slm.get("current_limit_mph")
    max_limit = slm.get("max_limit_mph")
    min_limit = slm.get("min_limit_mph")
    pin_set = slm.get("pin_code_set", False)

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "active": active,
                    "current_limit_mph": current_limit,
                    "max_limit_mph": max_limit,
                    "min_limit_mph": min_limit,
                    "pin_code_set": pin_set,
                },
                indent=2,
            )
        )
        return

    from rich.panel import Panel
    from rich.table import Table as RTable

    t = RTable(show_header=False, box=None, padding=(0, 2))
    t.add_column("Key", style="dim", width=24)
    t.add_column("Value", style="bold")
    t.add_row("Status", "[bold red]Active[/bold red]" if active else "[dim]Inactive[/dim]")
    if current_limit:
        t.add_row("Current Limit", f"{current_limit} mph")
    if max_limit:
        t.add_row("Max Limit", f"{max_limit} mph")
    if min_limit:
        t.add_row("Min Limit", f"{min_limit} mph")
    t.add_row("PIN Set", "Yes" if pin_set else "No")
    console.print(Panel(t, title="[bold]Speed Limit Mode[/bold]", border_style="red"))


@vehicle_app.command("bio")
def vehicle_bio(vin: str | None = VinOption) -> None:
    """Comprehensive single-screen vehicle profile — all states at once.

    tesla vehicle bio
    tesla -j vehicle bio | jq '.battery.battery_level'
    """
    import json as _json

    v = _vin(vin)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Loading vehicle profile...", total=None)
        data = _with_wake(lambda b, v: b.get_vehicle_data(v), v)

    vs = data.get("vehicle_state", {}) or {}
    cs = data.get("charge_state", {}) or {}
    clim = data.get("climate_state", {}) or {}
    vcfg = data.get("vehicle_config", {}) or {}

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "vin": data.get("vin", v),
                    "name": data.get("display_name") or data.get("vehicle_name", ""),
                    "state": data.get("state", ""),
                    "identity": {
                        "vin": data.get("vin", v),
                        "model": vcfg.get("car_type", ""),
                        "color": vcfg.get("exterior_color", ""),
                        "sw_version": vs.get("car_version", ""),
                    },
                    "battery": {
                        "battery_level": cs.get("battery_level"),
                        "battery_range": cs.get("battery_range"),
                        "charging_state": cs.get("charging_state"),
                        "charge_limit_soc": cs.get("charge_limit_soc"),
                    },
                    "climate": {
                        "is_climate_on": clim.get("is_climate_on"),
                        "inside_temp": clim.get("inside_temp"),
                        "outside_temp": clim.get("outside_temp"),
                    },
                    "drive": {
                        "locked": vs.get("locked"),
                        "sentry_mode": vs.get("sentry_mode"),
                        "valet_mode": vs.get("valet_mode"),
                        "odometer": vs.get("odometer"),
                        "sw_version": vs.get("car_version"),
                    },
                    "scheduling": {
                        "scheduled_charging_pending": cs.get("scheduled_charging_pending"),
                        "scheduled_charging_start_time": cs.get("scheduled_charging_start_time"),
                        "scheduled_departure_time": cs.get("scheduled_departure_time"),
                    },
                },
                indent=2,
                default=str,
            )
        )
        return

    from rich.panel import Panel as _Panel
    from rich.table import Table as _Table

    display_name = data.get("display_name") or data.get("vehicle_name") or v
    state_txt = data.get("state", "unknown")

    def _row(t: _Table, label: str, value: object, color: str = "white") -> None:
        if value is None or str(value) in ("None", ""):
            t.add_row(f"[dim]{label}[/dim]", "[dim]—[/dim]")
        else:
            t.add_row(f"[dim]{label}[/dim]", f"[{color}]{value}[/{color}]")

    def _kv() -> _Table:
        t = _Table(show_header=False, box=None, padding=(0, 2), expand=True)
        t.add_column("k", width=26)
        t.add_column("v")
        return t

    # Identity
    t_id = _kv()
    _row(t_id, "VIN", data.get("vin", v), "cyan")
    _row(t_id, "Model", vcfg.get("car_type", ""), "cyan")
    _row(t_id, "Color", vcfg.get("exterior_color", ""))
    _row(t_id, "Name", display_name, "bold")
    _row(t_id, "SW Version", vs.get("car_version", ""))
    _row(t_id, "State", state_txt, "green" if state_txt == "online" else "yellow")

    # Battery
    lvl = cs.get("battery_level")
    rng = cs.get("battery_range")
    cs_txt = cs.get("charging_state", "")
    lim = cs.get("charge_limit_soc")
    t_bat = _kv()
    bc = "green" if (lvl or 0) >= 50 else "yellow" if (lvl or 0) >= 20 else "red"
    _row(t_bat, "Level", f"{lvl}%" if lvl is not None else None, bc)
    _row(t_bat, "Range", f"{rng} mi" if rng else None)
    _row(t_bat, "Charging", cs_txt, "green" if cs_txt == "Charging" else "dim")
    _row(t_bat, "Charge Limit", f"{lim}%" if lim else None)

    # Climate
    hvac_on = clim.get("is_climate_on")
    inside = clim.get("inside_temp")
    outside = clim.get("outside_temp")
    t_clim = _kv()
    _row(t_clim, "HVAC", "ON" if hvac_on else "OFF", "green" if hvac_on else "dim")
    _row(t_clim, "Inside temp", f"{inside}°C" if inside is not None else None)
    _row(t_clim, "Outside temp", f"{outside}°C" if outside is not None else None)

    # Drive state
    locked = vs.get("locked")
    sentry = vs.get("sentry_mode")
    valet = vs.get("valet_mode")
    odometer = vs.get("odometer")
    t_drv = _kv()
    _row(t_drv, "Locked", "LOCKED" if locked else "UNLOCKED", "green" if locked else "red")
    _row(t_drv, "Sentry", "ON" if sentry else "off", "yellow" if sentry else "dim")
    _row(t_drv, "Valet", "ON" if valet else "off", "yellow" if valet else "dim")
    _row(t_drv, "Odometer", f"{odometer:.1f} mi" if odometer else None)

    # Scheduling
    sched_pending = cs.get("scheduled_charging_pending")
    sched_time = cs.get("scheduled_charging_start_time")
    dep_time = cs.get("scheduled_departure_time")
    t_sched = _kv()
    if sched_pending and sched_time:
        try:
            from datetime import UTC, datetime

            dt_s = datetime.fromtimestamp(int(sched_time), tz=UTC).strftime("%H:%M UTC")
        except Exception:
            dt_s = str(sched_time)
        _row(t_sched, "Scheduled Charge", dt_s, "cyan")
    else:
        _row(t_sched, "Scheduled Charge", "Not set")
    if dep_time:
        try:
            from datetime import UTC, datetime  # noqa: F811

            dt_d = datetime.fromtimestamp(int(dep_time), tz=UTC).strftime("%H:%M UTC")
        except Exception:
            dt_d = str(dep_time)
        _row(t_sched, "Departure", dt_d, "cyan")

    console.print()
    console.print(_Panel(t_id, title=f"[bold cyan]{display_name}[/bold cyan]", border_style="cyan"))
    console.print(_Panel(t_bat, title="[bold]Battery[/bold]", border_style="green"))
    console.print(_Panel(t_clim, title="[bold]Climate[/bold]", border_style="blue"))
    console.print(_Panel(t_drv, title="[bold]Drive State[/bold]", border_style="yellow"))
    console.print(_Panel(t_sched, title="[bold]Scheduling[/bold]", border_style="dim"))


_CABIN_LEVEL_MAP: dict[str, dict] = {
    "FAN_ONLY": {"on": True, "fan_only": True},
    "NO_AC": {"on": True, "fan_only": False},
    "CHARGE_ON": {"on": True, "fan_only": False},
}


@vehicle_app.command("cabin-protection")
def vehicle_cabin_protection(
    on: bool | None = typer.Option(
        None, "--on/--off", help="Enable or disable cabin overheat protection"
    ),
    level: str | None = typer.Option(
        None,
        "--level",
        help="Protection level: FAN_ONLY | NO_AC | CHARGE_ON",
    ),
    vin: str | None = VinOption,
) -> None:
    """Show or control Cabin Overheat Protection.

    tesla vehicle cabin-protection              → show current status
    tesla vehicle cabin-protection --on         → enable protection
    tesla vehicle cabin-protection --off        → disable protection
    tesla vehicle cabin-protection --level FAN_ONLY
    tesla vehicle cabin-protection --level NO_AC
    tesla -j vehicle cabin-protection
    """
    import json as _json

    v = _vin(vin)
    VALID_LEVELS = tuple(_CABIN_LEVEL_MAP.keys())

    # ── Status (no flags) ────────────────────────────────────────────────────
    if on is None and level is None:
        data = _with_wake(lambda b, v: b.get_climate_state(v), v)
        cop = data.get("cabin_overheat_protection", "Unknown")
        cop_active = data.get("cabin_overheat_protection_actively_cooling", False)
        if is_json_mode():
            console.print(
                _json.dumps(
                    {
                        "cabin_overheat_protection": cop,
                        "actively_cooling": cop_active,
                    },
                    indent=2,
                )
            )
            return
        sc = "green" if cop not in ("Off", "Unknown", None) else "dim"
        console.print(f"\n  Cabin Overheat Protection: [{sc}][bold]{cop}[/bold][/{sc}]")
        if cop_active:
            console.print("  [yellow]Currently actively cooling[/yellow]")
        return

    # ── --level flag ─────────────────────────────────────────────────────────
    if level is not None:
        lu = level.upper()
        if lu not in VALID_LEVELS:
            console.print(
                f"[red]Invalid level '{level}'. Choose from: {', '.join(VALID_LEVELS)}[/red]"
            )
            raise typer.Exit(1)
        params = _CABIN_LEVEL_MAP[lu]
        _with_wake(lambda b, v: b.command(v, "set_cabin_overheat_protection", **params), v)
        if is_json_mode():
            console.print(_json.dumps({"cabin_overheat_protection": lu, **params}, indent=2))
            return
        render_success(f"Cabin Overheat Protection set to {lu}")
        return

    # ── --on / --off ─────────────────────────────────────────────────────────
    _with_wake(
        lambda b, v: b.command(v, "set_cabin_overheat_protection", on=bool(on), fan_only=False), v
    )
    if is_json_mode():
        console.print(_json.dumps({"cabin_overheat_protection": "on" if on else "off"}, indent=2))
        return
    render_success(f"Cabin Overheat Protection {'enabled' if on else 'disabled'}")


# ── Watch state keys ──────────────────────────────────────────────────────────

_WATCH_KEYS: list[tuple[str, str, str]] = [
    # (section, key, label)
    ("charge_state", "battery_level", "🔋 Battery"),
    ("charge_state", "charging_state", "⚡ Charging state"),
    ("charge_state", "charge_limit_soc", "⚡ Charge limit"),
    ("vehicle_state", "locked", "🔒 Locked"),
    ("vehicle_state", "is_user_present", "👤 User present"),
    ("vehicle_state", "df", "🚪 Driver front door"),
    ("vehicle_state", "pf", "🚪 Pass front door"),
    ("vehicle_state", "dr", "🚪 Driver rear door"),
    ("vehicle_state", "pr", "🚪 Pass rear door"),
    ("climate_state", "is_climate_on", "🌡️ Climate"),
    ("climate_state", "inside_temp", "🌡️ Cabin temp"),
    ("drive_state", "shift_state", "🚗 Shift state"),
    ("drive_state", "speed", "🚗 Speed"),
]


@vehicle_app.command("watch")
def vehicle_watch(
    interval: int = typer.Option(60, "--interval", "-i", min=10, help="Poll interval in seconds"),
    notify: str | None = typer.Option(
        None, "--notify", help="Apprise URL for push notifications on change"
    ),
    on_change_exec: str | None = typer.Option(
        None,
        "--on-change-exec",
        help="Shell command to run on state change. Changes passed as JSON via TESLA_CHANGES env var.",
    ),
    all_vehicles: bool = typer.Option(
        False, "--all", "-A", help="Watch all configured vehicles simultaneously"
    ),
    vin: str | None = VinOption,
) -> None:
    """Continuous vehicle monitoring — prints alerts on state changes.

    Polls every INTERVAL seconds and reports any change in battery,
    charging state, locks, climate, doors, or shift state.

    tesla vehicle watch
    tesla vehicle watch --on-change-exec "echo 'State changed!' >> /tmp/tesla.log"
    tesla vehicle watch --interval 30
    tesla vehicle watch --notify "tgram://botid/chatid"
    tesla vehicle watch --all
    tesla vehicle watch --all --notify "tgram://botid/chatid"
    Press Ctrl+C to stop.
    """
    import json as _json
    import threading
    from datetime import datetime as _dt

    cfg = load_config()

    notifier = None
    if notify:
        try:
            import apprise

            notifier = apprise.Apprise()
            notifier.add(notify)
        except ImportError:
            console.print("[yellow]⚠ apprise not installed — notifications disabled[/yellow]")

    def _snapshot(backend, target_v: str) -> dict:
        """Fetch vehicle data and extract watched keys into a flat dict."""
        try:
            data = backend.get_vehicle_data(target_v)
        except VehicleAsleepError:
            return {}
        flat: dict = {}
        for section, key, _label in _WATCH_KEYS:
            sec = data.get(section) or {}
            val = sec.get(key)
            if val is not None:
                flat[f"{section}.{key}"] = val
        return flat

    def _watch_one(target_v: str, prefix: str, stop: threading.Event | None) -> None:
        label = prefix
        backend = get_vehicle_backend(cfg)
        prev: dict = {}
        while True:
            if stop is not None and stop.is_set():
                break
            curr = _snapshot(backend, target_v)
            tag = f"[cyan]{prefix}[/cyan]  " if prefix else ""
            if not curr:
                console.print(
                    f"  {tag}[dim]{_dt.now().strftime('%H:%M:%S')}[/dim]  [yellow]Vehicle asleep[/yellow]"
                )
            else:
                changes: list[str] = []
                for section, key, watch_label in _WATCH_KEYS:
                    fk = f"{section}.{key}"
                    if fk not in curr:
                        continue
                    old = prev.get(fk)
                    new = curr[fk]
                    if old is None:
                        continue  # first-seen value, don't alert
                    if new != old:
                        changes.append(f"{watch_label}: [bold]{old}[/bold] → [bold]{new}[/bold]")

                ts = _dt.now().strftime("%H:%M:%S")
                if is_json_mode():
                    payload = {
                        "ts": ts,
                        "vin": target_v,
                        "changes": [
                            c.replace("[bold]", "").replace("[/bold]", "") for c in changes
                        ],
                    }
                    console.print(_json.dumps(payload))
                elif changes:
                    for c in changes:
                        console.print(f"  {tag}[dim]{ts}[/dim]  {c}")
                    if notifier:
                        body = "\n".join(
                            c.replace("[bold]", "").replace("[/bold]", "") for c in changes
                        )
                        prefix_title = f"Tesla Watch — {label}" if label else "Tesla Watch"
                        notifier.notify(title=prefix_title, body=body)
                    if on_change_exec:
                        import os
                        import subprocess

                        change_data = [
                            {"key": c.split(":")[0].strip(), "change": c}
                            for c in [
                                c.replace("[bold]", "").replace("[/bold]", "") for c in changes
                            ]
                        ]
                        env = {**os.environ, "TESLA_CHANGES": _json.dumps(change_data)}
                        subprocess.Popen(on_change_exec, shell=True, env=env)
                else:
                    batt = curr.get("charge_state.battery_level", "?")
                    state = curr.get("charge_state.charging_state", "Unknown")
                    locked = curr.get("vehicle_state.locked", "?")
                    console.print(
                        f"  {tag}[dim]{ts}[/dim]  🔋{batt}%  ⚡{state}  🔒{'yes' if locked else 'no'}  [dim](no changes)[/dim]"
                    )
            prev = curr
            time.sleep(interval)

    if all_vehicles:
        # Collect all VINs from default + aliases, deduplicated
        vins_raw: list[str] = []
        if cfg.general.default_vin:
            vins_raw.append(cfg.general.default_vin)
        vins_raw.extend(cfg.vehicles.aliases.values())
        vins: list[str] = list(dict.fromkeys(vins_raw))

        if not vins:
            console.print("[red]No VINs configured. Set default-vin or add aliases.[/red]")
            raise typer.Exit(1)

        alias_of = {v: a for a, v in cfg.vehicles.aliases.items()}
        stop_event = threading.Event()
        threads = []
        for target_v in vins:
            label = alias_of.get(target_v, target_v[-6:])
            t = threading.Thread(target=_watch_one, args=(target_v, label, stop_event), daemon=True)
            threads.append(t)

        for t in threads:
            t.start()

        console.print(
            f"\n  [bold]Watching {len(vins)} vehicle(s)...[/bold]  [dim]Press Ctrl+C to stop.[/dim]\n"
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()
            for t in threads:
                t.join()
            console.print("\n  [dim]Watch stopped.[/dim]\n")
    else:
        v = _vin(vin)
        console.print(
            f"\n  [bold]Watching vehicle[/bold] [dim]{v}[/dim] — polling every [bold]{interval}s[/bold]"
        )
        console.print("  [dim]Press Ctrl+C to stop.[/dim]\n")
        try:
            _watch_one(v, "", None)
        except KeyboardInterrupt:
            console.print("\n  [dim]Watch stopped.[/dim]\n")


@vehicle_app.command("schedule-update")
def vehicle_schedule_update(
    delay: int = typer.Option(
        0, "--delay", "-d", help="Delay in minutes before installing (0 = now)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Schedule a pending OTA software update to install.

    \b
    tesla vehicle schedule-update            # install immediately
    tesla vehicle schedule-update --delay 60 # install in 60 minutes
    tesla -j vehicle schedule-update
    """
    import json as _json

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    b = get_vehicle_backend(cfg)

    offset_sec = delay * 60
    result = b.schedule_software_update(v, offset_sec=offset_sec)

    if is_json_mode():
        console.print(_json.dumps({"ok": bool(result), "delay_min": delay, "vin": v}))
        return

    if result:
        msg = "immediately" if delay == 0 else f"in {delay} minutes"
        render_success(f"Software update scheduled to install [bold]{msg}[/bold].")
    else:
        console.print("[red]Failed to schedule software update.[/red]")
        raise typer.Exit(1)


@vehicle_app.command("health-check")
def vehicle_health_check(vin: str | None = VinOption) -> None:
    """Comprehensive vehicle health summary: battery, firmware, tyres, alerts, sentry.

    \b
    tesla vehicle health-check
    tesla -j vehicle health-check
    """
    import json as _json

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    b = get_vehicle_backend(cfg)

    results: dict = {"vin": v, "checks": []}

    def _check(name: str, status: str, value: str, detail: str = "") -> None:
        results["checks"].append({"name": name, "status": status, "value": value, "detail": detail})

    # Fetch all states in one call
    try:
        data = b.get_vehicle_data(v)
    except VehicleAsleepError:
        console.print("[yellow]Vehicle is asleep — wake it first.[/yellow]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Failed to fetch vehicle data:[/red] {exc}")
        raise typer.Exit(1)

    cs = data.get("charge_state") or {}
    vs = data.get("vehicle_state") or {}

    # Battery
    level = cs.get("battery_level")
    if level is not None:
        st = "ok" if level >= 20 else "warn" if level >= 10 else "error"
        _check("Battery level", st, f"{level}%")
    else:
        _check("Battery level", "unknown", "—")

    # Charge limit
    limit = cs.get("charge_limit_soc")
    if limit is not None:
        st = "ok" if 70 <= limit <= 90 else "warn"
        _check(
            "Charge limit",
            st,
            f"{limit}%",
            "" if 70 <= (limit or 0) <= 90 else "Limit outside 70–90% range",
        )

    # Firmware
    sw = vs.get("car_version") or "—"
    pending = vs.get("software_update", {})
    has_update = bool(
        pending.get("status") not in (None, "", "available") and pending.get("version")
    )
    sw_status = "warn" if has_update else "ok"
    sw_detail = f"Update available: {pending.get('version', '')}" if has_update else ""
    _check("Firmware", sw_status, sw, sw_detail)

    # Tyre pressure
    tpms = {
        "FL": vs.get("tpms_pressure_fl"),
        "FR": vs.get("tpms_pressure_fr"),
        "RL": vs.get("tpms_pressure_rl"),
        "RR": vs.get("tpms_pressure_rr"),
    }
    low = [k for k, v_p in tpms.items() if v_p is not None and float(v_p) < 2.4]
    tyre_vals = {k: f"{float(v_p):.2f}" for k, v_p in tpms.items() if v_p is not None}
    if not tyre_vals:
        _check("Tyre pressure", "unknown", "—", "TPMS data unavailable")
    elif low:
        _check(
            "Tyre pressure",
            "warn",
            ", ".join(f"{k}:{tyre_vals.get(k, '?')}bar" for k in sorted(tyre_vals)),
            f"Low: {', '.join(low)}",
        )
    else:
        _check("Tyre pressure", "ok", ", ".join(f"{k}:{tyre_vals[k]}" for k in sorted(tyre_vals)))

    # Locks
    locked = vs.get("locked")
    if locked is not None:
        _check("Doors locked", "ok" if locked else "warn", "Yes" if locked else "No")

    # Sentry
    sentry = vs.get("sentry_mode")
    if sentry is not None:
        _check("Sentry mode", "ok", "On" if sentry else "Off")

    # Odometer
    odo = vs.get("odometer")
    if odo is not None:
        _check("Odometer", "ok", f"{float(odo):.0f} mi")

    if is_json_mode():
        console.print(_json.dumps(results, indent=2))
        return

    _ICON = {
        "ok": "[green]✓[/green]",
        "warn": "[yellow]⚠[/yellow]",
        "error": "[red]✗[/red]",
        "unknown": "[dim]?[/dim]",
    }
    from rich.table import Table as _Table

    t = _Table(title=f"Vehicle Health — {v[-6:]}", show_header=False, box=None, padding=(0, 2))
    t.add_column("s", width=3)
    t.add_column("k", style="bold", width=18)
    t.add_column("v", width=30)
    t.add_column("d", style="dim")

    for c in results["checks"]:
        icon = _ICON.get(c["status"], "?")
        t.add_row(icon, c["name"], c["value"], c.get("detail") or "")
    console.print(t)

    errors = sum(1 for c in results["checks"] if c["status"] == "error")
    warnings = sum(1 for c in results["checks"] if c["status"] == "warn")
    if errors:
        console.print(f"\n  [red]✗ {errors} issue(s) need attention[/red]")
    elif warnings:
        console.print(f"\n  [yellow]⚠ {warnings} item(s) to review[/yellow]")
    else:
        console.print("\n  [green]✓ All checks passed[/green]")


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

    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_vehicle_data(v), v)

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


# ═══════════════════════════════════════════════════════════════════════════════
# Absorbed from stream.py, dashboard.py, sharing.py
# ═══════════════════════════════════════════════════════════════════════════════


@vehicle_app.command("stream")
def vehicle_stream(
    interval: float = typer.Option(5.0, "--interval", "-i", help="Refresh interval in seconds"),
    count: int = typer.Option(0, "--count", "-n", help="Stop after N refreshes (0=forever)"),
    mqtt_url: str | None = typer.Option(None, "--mqtt", help="MQTT broker URL"),
    vin: str | None = VinOption,
) -> None:
    """Real-time vehicle telemetry stream.

    tesla vehicle stream
    tesla vehicle stream --interval 10
    tesla vehicle stream --count 20
    """
    import json as _json

    from rich.live import Live
    from rich.table import Table as _Table

    from tesla_cli.core.config import load_config, resolve_vin

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    backend = _backend()

    iteration = 0
    try:
        with Live(console=console, refresh_per_second=1, transient=False) as live:
            while True:
                try:
                    data = backend.get_vehicle_data(v)
                except VehicleAsleepError:
                    console.print("[yellow]Vehicle asleep, waking...[/yellow]")
                    backend.wake_up(v)
                    time.sleep(5)
                    continue

                if is_json_mode():
                    console.print_json(_json.dumps(data, indent=2, default=str))
                    raise typer.Exit(0)

                cs = data.get("charge_state", {})
                cl = data.get("climate_state", {})
                ds = data.get("drive_state", {})
                vs = data.get("vehicle_state", {})

                t = _Table(title=f"Tesla Stream — {v[-6:]}", show_lines=True)
                t.add_column("Key", style="cyan", width=22)
                t.add_column("Value", width=30)

                t.add_row("Battery", f"{cs.get('battery_level', '?')}%")
                t.add_row("Range", f"{cs.get('battery_range', 0):.1f} mi")
                t.add_row("Charging", cs.get("charging_state", "?"))
                if cs.get("charging_state") == "Charging":
                    t.add_row("Charge Rate", f"{cs.get('charger_power', 0)} kW")
                t.add_row("Inside Temp", f"{cl.get('inside_temp', '?')}°C")
                t.add_row("Outside Temp", f"{cl.get('outside_temp', '?')}°C")
                lat = ds.get("latitude")
                lon = ds.get("longitude")
                if lat and lon:
                    t.add_row("Location", f"{lat:.4f}, {lon:.4f}")
                t.add_row("Speed", f"{ds.get('speed') or 0} mph")
                t.add_row("Locked", "Yes" if vs.get("locked") else "No")
                t.add_row("Sentry", "ON" if vs.get("sentry_mode") else "off")
                t.add_row("Software", vs.get("car_version", "?"))
                t.add_row("Odometer", f"{vs.get('odometer', 0):,.0f} mi")

                live.update(t)

                # MQTT publish if configured
                if mqtt_url:
                    try:
                        from tesla_cli.core.providers.impl.mqtt import MqttProvider

                        mp = MqttProvider(cfg)
                        if mp.available():
                            mp.push(data)
                    except Exception:
                        pass

                iteration += 1
                if count and iteration >= count:
                    break
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stream stopped.[/dim]")


@vehicle_app.command("dashboard")
def vehicle_dashboard(vin: str | None = VinOption) -> None:
    """Unified multi-panel vehicle status dashboard.

    tesla vehicle dashboard
    tesla -j vehicle dashboard
    """
    import json as _json

    from rich.columns import Columns
    from rich.panel import Panel
    from rich.table import Table as _Table

    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_vehicle_data(v), v)

    if is_json_mode():
        console.print(_json.dumps(data, indent=2, default=str))
        return

    charge = data.get("charge_state", {})
    climate = data.get("climate_state", {})
    drive = data.get("drive_state", {})
    vehicle = data.get("vehicle_state", {})
    config = data.get("vehicle_config", {})

    def _bool_icon(val):
        return "\u2705" if val else "\u274c" if val is not None else "\u2753"

    def _bar(level):
        filled = level // 5
        empty = 20 - filled
        color = "green" if level > 60 else "yellow" if level > 20 else "red"
        return f"[{color}]{chr(9608) * filled}{chr(9617) * empty}[/{color}] {level}%"

    battery_level = charge.get("battery_level", 0)
    bt = _Table(show_header=False, box=None, padding=(0, 1))
    bt.add_column("K", style="bold cyan", width=20)
    bt.add_column("V")
    bt.add_row("Battery", _bar(battery_level))
    bt.add_row("Range", f"{charge.get('battery_range', 0):.0f} mi")
    bt.add_row("Charge Limit", f"{charge.get('charge_limit_soc', 0)}%")
    bt.add_row("Charging", charge.get("charging_state", "Unknown"))
    if charge.get("charging_state") == "Charging":
        bt.add_row("Power", f"{charge.get('charger_power', 0)} kW")
        bt.add_row("Time Left", f"{charge.get('time_to_full_charge', 0):.1f} hr")

    lat = drive.get("latitude", 0)
    lon = drive.get("longitude", 0)
    lt = _Table(show_header=False, box=None, padding=(0, 1))
    lt.add_column("K", style="bold cyan", width=20)
    lt.add_column("V")
    lt.add_row("Coordinates", f"{lat:.5f}, {lon:.5f}" if lat else "Unknown")
    speed = drive.get("speed")
    lt.add_row("Speed", f"{speed} mph" if speed else "Parked")

    st = _Table(show_header=False, box=None, padding=(0, 1))
    st.add_column("K", style="bold cyan", width=20)
    st.add_column("V")
    st.add_row("Locked", _bool_icon(vehicle.get("locked")))
    st.add_row("Sentry Mode", _bool_icon(vehicle.get("sentry_mode")))
    st.add_row("Software", vehicle.get("car_version", "Unknown"))
    st.add_row("Odometer", f"{vehicle.get('odometer', 0):,.0f} mi")

    ct = _Table(show_header=False, box=None, padding=(0, 1))
    ct.add_column("K", style="bold cyan", width=20)
    ct.add_column("V")
    ct.add_row("Climate On", _bool_icon(climate.get("is_climate_on")))
    inside = climate.get("inside_temp")
    outside = climate.get("outside_temp")
    ct.add_row("Inside", f"{inside}\u00b0C" if inside is not None else "N/A")
    ct.add_row("Outside", f"{outside}\u00b0C" if outside is not None else "N/A")

    name = data.get("display_name", data.get("vehicle_name", v))
    model = config.get("car_type", "Tesla")

    panels = [
        Panel(bt, title="\U0001f50b Battery & Charging", border_style="green"),
        Panel(lt, title="\U0001f4cd Location", border_style="blue"),
        Panel(st, title="\U0001f512 Security", border_style="red"),
        Panel(ct, title="\U0001f321\ufe0f Climate", border_style="yellow"),
    ]

    console.print()
    console.print(f"[bold]\U0001f697 {name}[/bold] ({model}) \u2014 {v}")
    console.print()
    console.print(Columns(panels, equal=True, expand=True))


@vehicle_app.command("invite")
def vehicle_invite(vin: str | None = VinOption) -> None:
    """Create a new driver invitation link."""
    from tesla_cli.core.exceptions import BackendNotSupportedError

    v = _vin(vin)
    backend = _backend()
    try:
        data = backend.create_invitation(v)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)
    render_dict(data, title="New Invitation")


@vehicle_app.command("invitations")
def vehicle_invitations(vin: str | None = VinOption) -> None:
    """List current driver invitations."""
    from tesla_cli.core.exceptions import BackendNotSupportedError

    v = _vin(vin)
    backend = _backend()
    try:
        invitations = backend.get_invitations(v)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)
    if not invitations:
        render_success("No active invitations")
        return
    render_table(
        invitations,
        columns=["id", "owner", "state", "created_at"],
        title="Driver Invitations",
    )


@vehicle_app.command("revoke-invite")
def vehicle_revoke_invite(
    invitation_id: str = typer.Argument(..., help="Invitation ID to revoke"),
    vin: str | None = VinOption,
) -> None:
    """Revoke a driver invitation."""
    from tesla_cli.core.exceptions import BackendNotSupportedError

    v = _vin(vin)
    backend = _backend()
    try:
        backend.revoke_invitation(v, invitation_id)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)
    render_success(f"Invitation {invitation_id} revoked")


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

    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_vehicle_data(v), v)

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


@vehicle_app.command("ready")
def vehicle_ready(
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
    vin: str | None = VinOption,
) -> None:
    """Morning check: am I ready to drive?

    Combines battery level, charge schedule, cabin temperature, alerts,
    and vehicle state into a single "ready to go" assessment.

    tesla vehicle ready
    tesla vehicle ready --oneline
    tesla -j vehicle ready
    """
    import json as _json

    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_vehicle_data(v), v)

    cs = data.get("charge_state", {})
    cl = data.get("climate_state", {})
    vs = data.get("vehicle_state", {})

    level = cs.get("battery_level", 0)
    range_mi = cs.get("battery_range", 0)
    range_km = round(range_mi * 1.60934, 1) if range_mi else 0
    charging = cs.get("charging_state", "Unknown")
    limit = cs.get("charge_limit_soc", 0)
    inside = cl.get("inside_temp")
    outside = cl.get("outside_temp")
    locked = vs.get("locked", False)
    sentry = vs.get("sentry_mode", False)
    sw_update = vs.get("software_update") or {}
    update_available = sw_update.get("status", "") not in ("", "available")
    precond = cl.get("is_preconditioning", False)
    climate_on = cl.get("is_climate_on", False)

    # Assess readiness
    issues: list[str] = []
    good: list[str] = []

    if level >= 20:
        good.append(f"Battery {level}% ({range_km} km)")
    else:
        issues.append(f"Low battery: {level}% ({range_km} km)")

    if charging == "Charging":
        eta = cs.get("time_to_full_charge", 0)
        eta_str = f"{int(eta)}h{int((eta % 1) * 60):02d}m" if eta else ""
        issues.append(f"Still charging — {eta_str} to {limit}%")
    elif charging == "Complete":
        good.append(f"Charge complete ({limit}%)")
    elif level >= limit:
        good.append(f"At charge limit ({limit}%)")

    if outside is not None and outside < 5:
        if climate_on or precond:
            good.append(f"Preconditioning active ({outside}\u00b0C outside)")
        else:
            issues.append(f"Cold outside ({outside}\u00b0C) \u2014 consider preconditioning")
    elif inside is not None:
        good.append(f"Cabin {inside}\u00b0C")

    if locked:
        good.append("Locked")
    else:
        issues.append("Vehicle unlocked")

    if sentry:
        good.append("Sentry ON")

    if update_available:
        issues.append("Software update pending")

    if is_json_mode():
        console.print_json(
            _json.dumps(
                {
                    "ready": len(issues) == 0,
                    "battery_level": level,
                    "range_km": range_km,
                    "charging_state": charging,
                    "inside_temp": inside,
                    "outside_temp": outside,
                    "locked": locked,
                    "sentry_mode": sentry,
                    "preconditioning": precond or climate_on,
                    "issues": issues,
                    "good": good,
                },
                indent=2,
            )
        )
        return

    if oneline:
        status = "\u2705 Ready" if not issues else f"\u26a0\ufe0f {len(issues)} issue(s)"
        parts = [status, f"\U0001f50b {level}%"]
        if inside is not None:
            parts.append(f"\U0001f321 {inside}\u00b0C")
        if charging == "Charging":
            parts.append("\u26a1 Charging")
        typer.echo(" | ".join(parts))
        return

    console.print()
    if not issues:
        console.print("  [bold green]\u2705 Ready to drive![/bold green]")
    else:
        console.print(f"  [bold yellow]\u26a0\ufe0f  {len(issues)} issue(s)[/bold yellow]")

    console.print()
    for g in good:
        console.print(f"  [green]\u2713[/green] {g}")
    for i in issues:
        console.print(f"  [yellow]\u26a0[/yellow] {i}")
    console.print()


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

    v = _vin(vin)
    backend = _backend()

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
    v = _vin(vin)
    backend = _backend()

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


@vehicle_app.command("stream-live")
def vehicle_stream_live(
    lines: int = typer.Option(
        50, "--lines", "-n", help="Number of recent log lines to show before following"
    ),
    raw: bool = typer.Option(False, "--raw", help="Print raw log lines without formatting"),
    vin: str | None = VinOption,
) -> None:
    """Stream real-time telemetry from the self-hosted fleet-telemetry server.

    Tails the fleet-telemetry Docker container logs, which receive data
    streamed directly from your vehicle.

    Requires: tesla telemetry install + tesla telemetry configure

    tesla vehicle stream-live
    tesla vehicle stream-live --lines 100
    tesla vehicle stream-live --raw
    """

    from tesla_cli.core.config import load_config

    cfg = load_config()

    if not cfg.telemetry.enabled or not cfg.telemetry.managed:
        console.print(
            "[red]Self-hosted fleet-telemetry not configured.[/red]\n"
            "Run: [bold]tesla telemetry install <hostname>[/bold]\n"
            "Then: [bold]tesla telemetry configure[/bold]"
        )
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.infra.fleet_telemetry_stack import FleetTelemetryStack

    stack_dir = Path(cfg.telemetry.stack_dir) if cfg.telemetry.stack_dir else None
    stack = FleetTelemetryStack(stack_dir)

    if not stack.is_installed():
        console.print(
            "[red]Fleet-telemetry stack is not installed.[/red]\n"
            "Run: [bold]tesla telemetry install <hostname>[/bold]"
        )
        raise typer.Exit(1)

    if not stack.is_running():
        console.print(
            "[yellow]Fleet-telemetry container is not running.[/yellow]\n"
            "Start it with: [bold]tesla telemetry start[/bold]"
        )
        raise typer.Exit(1)

    console.print(
        "[bold]Streaming from fleet-telemetry server...[/bold] [dim](Ctrl+C to stop)[/dim]"
    )

    proc = stack.logs(lines=lines, follow=True)
    try:
        for line in proc.stdout or []:
            if raw:
                console.print(line, end="")
            else:
                console.print(line, end="")
    except KeyboardInterrupt:
        proc.terminate()


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

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    backend = get_vehicle_backend(cfg)

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

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    backend = get_vehicle_backend(cfg)

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

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    backend = get_vehicle_backend(cfg)

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
