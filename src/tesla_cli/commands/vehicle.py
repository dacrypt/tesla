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
