"""Vehicle commands: tesla vehicle info/location/charge/climate/lock/unlock/..."""

from __future__ import annotations

import time

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from tesla_cli.backends import get_vehicle_backend
from tesla_cli.config import load_config, resolve_vin
from tesla_cli.exceptions import VehicleAsleepError
from tesla_cli.models.charge import ChargeState
from tesla_cli.models.climate import ClimateState
from tesla_cli.models.drive import Location
from tesla_cli.output import (
    console,
    is_json_mode,
    render_dict,
    render_model,
    render_success,
    render_table,
)

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
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task("Fetching vehicles...", total=None)
        vehicles = backend.list_vehicles()

    rows = []
    for v in vehicles if isinstance(vehicles, list) else [vehicles]:
        rows.append({
            "vin": v.get("vin", ""),
            "name": v.get("display_name", v.get("vehicle_name", "")),
            "state": v.get("state", ""),
            "model": v.get("model", v.get("vehicle_type", "")),
        })
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

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task("Waking vehicle...", total=None)
        result = backend.wake_up(v)

    if result:
        render_success("Vehicle is awake")
    else:
        console.print("[yellow]Wake command sent. Vehicle may take a moment to respond.[/yellow]")


@vehicle_app.command("trunk")
def vehicle_trunk(
    which: str = typer.Argument("rear", help="rear | front (frunk)"),
    vin: str | None = VinOption,
) -> None:
    """Open trunk or frunk."""
    v = _vin(vin)
    cmd = "actuate_trunk"
    param = "rear" if which == "rear" else "front"
    _with_wake(lambda b, v: b.command(v, cmd, which_trunk=param), v)
    render_success(f"{which.title()} trunk opened")


@vehicle_app.command("sentry")
def vehicle_sentry(
    enable: bool | None = typer.Option(None, "--on/--off", help="Turn Sentry Mode on or off"),
    vin: str | None = VinOption,
) -> None:
    """Show or toggle Sentry Mode.

    tesla vehicle sentry          → show current sentry mode status
    tesla vehicle sentry --on     → enable Sentry Mode
    tesla vehicle sentry --off    → disable Sentry Mode
    """
    v = _vin(vin)

    if enable is None:
        # Show status
        data = _with_wake(lambda b, v: b.get_vehicle_state(v), v)
        sentry_on = data.get("sentry_mode", False)
        available = data.get("sentry_mode_available", True)
        status = "ON" if sentry_on else "OFF"
        status_color = "green" if sentry_on else "dim"

        if is_json_mode():
            import json
            console.print(json.dumps({
                "sentry_mode": sentry_on,
                "sentry_mode_available": available,
            }))
            return

        console.print(f"\n  Sentry Mode: [{status_color}][bold]{status}[/bold][/{status_color}]")
        if not available:
            console.print("  [yellow]Note: Sentry Mode not available (vehicle may not be parked)[/yellow]")
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

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task("Fetching trip data...", total=None)
        try:
            svc_data = _with_wake(lambda b, v: b.get_service_data(v), v)
        except Exception:
            svc_data = {}

        drive_state = _with_wake(lambda b, v: b.get_drive_state(v), v)
        vehicle_state = _with_wake(lambda b, v: b.get_vehicle_state(v), v)

    if is_json_mode():
        import json
        console.print(json.dumps({
            "service_data": svc_data,
            "drive_state": drive_state,
            "vehicle_state": vehicle_state,
        }, indent=2, default=str))
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
        console.print(f"  Last location: {last_lat:.4f}, {last_lon:.4f}  (heading {heading}°, {last_speed} mph)")
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
        "open":  "charge_port_door_open",
        "close": "charge_port_door_close",
        "stop":  "charge_stop",
    }
    if action not in CMD_MAP:
        console.print("[red]Action must be 'open', 'close', or 'stop'.[/red]")
        raise typer.Exit(1)
    _with_wake(lambda b, v: b.command(v, CMD_MAP[action]), v)
    labels = {"open": "Charge port opened", "close": "Charge port closed", "stop": "Charging stopped"}
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

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
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
        console.print(_json.dumps({
            "current_version": current,
            "update_status": update_status,
            "update_version": update_version or None,
            "download_percentage": download_pct,
            "install_percentage": install_pct,
            "expected_duration_min": round(expected_sec / 60) if expected_sec else None,
            "scheduled_time_ms": scheduled_ms or None,
        }, indent=2))
        return

    from rich.table import Table

    console.print()
    console.print(f"  [bold]Software version:[/bold]  [cyan]{current}[/cyan]")

    if not update_status or update_status == "":
        console.print("  [dim]No pending software update.[/dim]")
        return

    status_color = {
        "available":    "yellow",
        "scheduled":    "cyan",
        "downloading":  "blue",
        "installing":   "green",
        "wifi_wait":    "dim",
        "appinstalled": "green",
    }.get(update_status, "white")

    console.print(f"\n  [bold]Update available:[/bold]  [{status_color}]{update_version}[/{status_color}]  "
                  f"[dim]({update_status})[/dim]")

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
        sched_dt = datetime.fromtimestamp(scheduled_ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        table.add_row("Scheduled for", sched_dt)

    console.print(table)

    if install and update_status in ("available", "wifi_wait"):
        _with_wake(lambda b, v: b.command(v, "schedule_software_update", offset_sec=0), v)
        render_success(f"Software update to {update_version} scheduled")
    elif install:
        console.print(f"  [yellow]Cannot schedule install — current status: {update_status}[/yellow]")


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

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task("Fetching nearby charging sites...", total=None)
        data = _with_wake(lambda b, v: b.get_nearby_charging_sites(v), v)

    superchargers = data.get("superchargers", [])
    destination = data.get("destination_charging", [])

    if is_json_mode():
        console.print(_json.dumps({
            "superchargers": superchargers,
            "destination_charging": destination,
        }, indent=2, default=str))
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
            avail_color = "green" if isinstance(avail, int) and avail > 3 else "yellow" if isinstance(avail, int) and avail > 0 else "red"
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

    from tesla_cli.exceptions import BackendNotSupportedError

    try:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
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

    from tesla_cli.exceptions import BackendNotSupportedError

    try:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
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
            console.print(_json.dumps({
                "scheduled_charging_pending": enabled,
                "scheduled_charging_start_time": sched_time,
            }, indent=2))
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
        console.print(_json.dumps({"scheduled_charging": True, "time": time_str, "time_minutes": time_minutes}, indent=2))
        return
    render_success(f"Scheduled charging set to {time_str} ({time_minutes} min from midnight)")


@vehicle_app.command("tires")
def vehicle_tires(
    vin: str | None = VinOption,
) -> None:
    """Show TPMS tire pressure readings.

    tesla vehicle tires
    tesla -j vehicle tires | jq '{fl:.front_left_psi, fr:.front_right_psi}'
    """
    import json as _json

    v = _vin(vin)
    state = _with_wake(lambda b, v: b.get_vehicle_state(v), v)

    POSITIONS = [
        ("front_left",  "tpms_pressure_fl", "tpms_soft_warning_fl", "tpms_hard_warning_fl"),
        ("front_right", "tpms_pressure_fr", "tpms_soft_warning_fr", "tpms_hard_warning_fr"),
        ("rear_left",   "tpms_pressure_rl", "tpms_soft_warning_rl", "tpms_hard_warning_rl"),
        ("rear_right",  "tpms_pressure_rr", "tpms_soft_warning_rr", "tpms_hard_warning_rr"),
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
        from tesla_cli.output import console as _console
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

    from tesla_cli.exceptions import BackendNotSupportedError

    v = _vin(vin)
    try:
        alerts = _with_wake(lambda b, v: b.get_recent_alerts(v), v)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)

    # Filter sentry-related alerts; if empty, show all
    sentry_keywords = ("sentry", "camera", "detection", "intrus", "motion", "tampering")
    sentry_events = [
        a for a in (alerts if isinstance(alerts, list) else alerts.get("alerts", []))
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
