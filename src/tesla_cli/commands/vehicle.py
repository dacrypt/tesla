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
