"""Climate commands: tesla climate on|off|temp|seat-heater|steering-heater|dog-mode|camp-mode|bioweapon|defrost."""

from __future__ import annotations

import typer

from tesla_cli.cli.commands.vehicle import _with_wake
from tesla_cli.cli.output import console, is_json_mode, render_model, render_success
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.models.climate import ClimateState

climate_app = typer.Typer(name="climate", help="Climate and HVAC controls.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@climate_app.command("status")
def climate_status(
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
    vin: str | None = VinOption,
) -> None:
    """Show climate state.

    tesla climate status
    tesla climate status --oneline    # 🌡 22°C in / 18°C out | HVAC off
    tesla -j climate status
    """
    import json as _json

    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_climate_state(v), v)

    if is_json_mode():
        console.print_json(_json.dumps(data, default=str))
        return

    if oneline:
        inside = data.get("inside_temp")
        outside = data.get("outside_temp")
        hvac = data.get("is_climate_on", False)
        parts = []
        if inside is not None:
            parts.append(f"\U0001f321 {inside}\u00b0C in")
        if outside is not None:
            parts.append(f"{outside}\u00b0C out")
        parts.append("HVAC on" if hvac else "HVAC off")
        typer.echo(" | ".join(parts))
        return

    state = ClimateState.model_validate(data)
    render_model(state, title="Climate State")


@climate_app.command("on")
def climate_on(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview action without executing"),
    vin: str | None = VinOption,
) -> None:
    """Turn climate/AC on."""
    v = _vin(vin)
    if dry_run:
        console.print(f"[dim]Dry run:[/dim] Would turn climate ON for VIN ...{v[-6:]}")
        return
    _with_wake(lambda b, v: b.command(v, "auto_conditioning_start"), v)
    render_success("Climate ON")


@climate_app.command("off")
def climate_off(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview action without executing"),
    vin: str | None = VinOption,
) -> None:
    """Turn climate/AC off."""
    v = _vin(vin)
    if dry_run:
        console.print(f"[dim]Dry run:[/dim] Would turn climate OFF for VIN ...{v[-6:]}")
        return
    _with_wake(lambda b, v: b.command(v, "auto_conditioning_stop"), v)
    render_success("Climate OFF")


@climate_app.command("temp")
def climate_temp(
    celsius: float | None = typer.Argument(
        None, help="Driver temp in °C (15.0-30.0). Omit to show current."
    ),
    passenger: float | None = typer.Option(
        None, "--passenger", "-p", help="Passenger temp in °C (defaults to driver)."
    ),
    vin: str | None = VinOption,
) -> None:
    """Show or set climate temperature.

    tesla climate temp              → show current temps
    tesla climate temp 22           → set driver + passenger to 22°C
    tesla climate temp 22 -p 20     → driver 22°C, passenger 20°C
    tesla -j climate temp           → JSON output
    """
    import json as _json

    v = _vin(vin)
    if celsius is None:
        data = _with_wake(lambda b, v: b.get_climate_state(v), v)
        d = data.get("driver_temp_setting")
        p = data.get("passenger_temp_setting")
        if is_json_mode():
            console.print(_json.dumps({"driver_temp_setting": d, "passenger_temp_setting": p}))
            return
        render_success(f"Driver: {d}°C  Passenger: {p}°C")
        return
    if not 15.0 <= celsius <= 30.0:
        raise typer.BadParameter("Temperature must be between 15.0 and 30.0 °C.")
    if passenger is not None and not 15.0 <= passenger <= 30.0:
        raise typer.BadParameter("Passenger temperature must be between 15.0 and 30.0 °C.")
    pass_temp = passenger if passenger is not None else celsius
    _with_wake(
        lambda b, v: b.command(v, "set_temps", driver_temp=celsius, passenger_temp=pass_temp),
        v,
    )
    if is_json_mode():
        console.print(
            _json.dumps({"driver_temp": celsius, "passenger_temp": pass_temp, "status": "ok"})
        )
        return
    render_success(f"Temperature set to {celsius}°C / {pass_temp}°C")


@climate_app.command("seat-heater")
def seat_heater(
    seat: int = typer.Argument(
        ..., help="Seat (0=driver, 1=passenger, 2=rear-left, 4=rear-center, 5=rear-right)"
    ),
    level: int = typer.Argument(..., help="Level (0=off, 1=low, 2=med, 3=high)"),
    vin: str | None = VinOption,
) -> None:
    """Set seat heater level."""
    v = _vin(vin)
    _with_wake(
        lambda b, v: b.command(v, "remote_seat_heater_request", heater=seat, level=level),
        v,
    )
    render_success(f"Seat {seat} heater set to level {level}")


@climate_app.command("steering-heater")
def steering_heater(
    on: bool = typer.Argument(..., help="Turn on (true) or off (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle steering wheel heater."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "remote_steering_wheel_heater_request", on=on), v)
    status = "ON" if on else "OFF"
    render_success(f"Steering wheel heater {status}")


_SEAT_MAP: dict[str, int] = {
    "driver": 0,
    "passenger": 1,
    "rear-left": 2,
    "rear-center": 4,
    "rear-right": 5,
}


@climate_app.command("seat")
def seat_heater_named(
    position: str | None = typer.Argument(
        None, help="driver|passenger|rear-left|rear-center|rear-right. Omit to show all."
    ),
    level: int | None = typer.Argument(
        None, help="Heat level 0-3 (0=off, 1-3=heat). Required when POSITION given."
    ),
    vin: str | None = VinOption,
) -> None:
    """Show seat heater levels or set by named position.

    tesla climate seat                      → show all seat levels
    tesla climate seat driver 2             → driver seat to level 2
    tesla climate seat rear-left 1          → rear-left to level 1
    tesla climate seat passenger 0          → turn off passenger seat
    tesla -j climate seat                   → JSON output
    """
    import json as _json

    v = _vin(vin)
    if position is None:
        data = _with_wake(lambda b, v: b.get_climate_state(v), v)
        seats = {
            "driver": data.get("seat_heater_left", 0),
            "passenger": data.get("seat_heater_right", 0),
            "rear-left": data.get("seat_heater_rear_left", 0),
            "rear-center": data.get("seat_heater_rear_center", 0),
            "rear-right": data.get("seat_heater_rear_right", 0),
        }
        if is_json_mode():
            console.print(_json.dumps(seats))
            return
        for name, lvl in seats.items():
            dot = "🔴" if lvl == 3 else "🟡" if lvl == 2 else "🟠" if lvl == 1 else "⚫"
            console.print(f"  {dot}  {name:<14} {lvl}")
        return
    pos_lower = position.lower()
    if pos_lower not in _SEAT_MAP:
        valid = ", ".join(_SEAT_MAP)
        raise typer.BadParameter(f"Invalid position '{position}'. Choose from: {valid}")
    if level is None:
        raise typer.BadParameter("LEVEL is required when POSITION is given (0-3).")
    if not 0 <= level <= 3:
        raise typer.BadParameter("Level must be 0-3.")
    seat_id = _SEAT_MAP[pos_lower]
    _with_wake(
        lambda b, v: b.command(v, "remote_seat_heater_request", heater=seat_id, level=level), v
    )
    if is_json_mode():
        console.print(
            _json.dumps({"seat": pos_lower, "heater_id": seat_id, "level": level, "status": "ok"})
        )
        return
    render_success(f"Seat '{pos_lower}' heater set to level {level}")


@climate_app.command("steering-wheel")
def steering_wheel_heater(
    on: bool | None = typer.Option(
        None, "--on/--off", help="Turn on or off. Omit to show current state."
    ),
    vin: str | None = VinOption,
) -> None:
    """Show or toggle steering wheel heater.

    tesla climate steering-wheel            → show current state
    tesla climate steering-wheel --on       → enable
    tesla climate steering-wheel --off      → disable
    tesla -j climate steering-wheel         → JSON output
    """
    import json as _json

    v = _vin(vin)
    if on is None:
        data = _with_wake(lambda b, v: b.get_climate_state(v), v)
        state = data.get("steering_wheel_heater", False)
        if is_json_mode():
            console.print(_json.dumps({"steering_wheel_heater": state}))
            return
        label = "[green]ON[/green]" if state else "[dim]OFF[/dim]"
        console.print(f"\n  Steering wheel heater: {label}\n")
        return
    _with_wake(lambda b, v: b.command(v, "remote_steering_wheel_heater_request", on=on), v)
    if is_json_mode():
        console.print(_json.dumps({"steering_wheel_heater": on, "status": "ok"}))
        return
    render_success(f"Steering wheel heater {'ON' if on else 'OFF'}")


@climate_app.command("dog-mode")
def dog_mode(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle Dog Mode."""
    v = _vin(vin)
    mode = 2 if on else 0  # 0=off, 2=dog
    _with_wake(
        lambda b, v: b.command(v, "set_climate_keeper_mode", climate_keeper_mode=mode),
        v,
    )
    status = "ON" if on else "OFF"
    render_success(f"Dog Mode {status}")


@climate_app.command("camp-mode")
def camp_mode(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle Camp Mode."""
    v = _vin(vin)
    mode = 3 if on else 0  # 0=off, 3=camp
    _with_wake(
        lambda b, v: b.command(v, "set_climate_keeper_mode", climate_keeper_mode=mode),
        v,
    )
    status = "ON" if on else "OFF"
    render_success(f"Camp Mode {status}")


@climate_app.command("bioweapon")
def bioweapon(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle Bioweapon Defense Mode."""
    v = _vin(vin)
    _with_wake(
        lambda b, v: b.command(v, "set_bioweapon_mode", on=on, manual_override=True),
        v,
    )
    status = "ON" if on else "OFF"
    render_success(f"Bioweapon Defense Mode {status}")


@climate_app.command("defrost")
def defrost(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle max defrost (preconditioning max)."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "set_preconditioning_max", on=on), v)
    status = "ON" if on else "OFF"
    render_success(f"Max Defrost {status}")


def _backend():
    from tesla_cli.core.backends import get_vehicle_backend

    return get_vehicle_backend(load_config())


def _parse_hhmm(time_str: str) -> int:
    """Convert HH:MM to minutes after midnight."""
    try:
        h, m = time_str.split(":")
        return int(h) * 60 + int(m)
    except ValueError:
        raise typer.BadParameter(f"Time must be in HH:MM format, got '{time_str}'.")


def _parse_days(days: str) -> str:
    """Normalise days to API format: all, weekdays, weekends, or mon,tue,..."""
    aliases = {"all": "all", "weekdays": "weekdays", "weekends": "weekends"}
    return aliases.get(days.strip().lower(), days.strip().lower())


@climate_app.command("add-precondition-schedule")
def climate_add_precondition_schedule(
    time: str = typer.Argument(help="Start time in HH:MM (24h)"),
    days: str = typer.Option(
        "all",
        "--days",
        "-d",
        help="Days: all, weekdays, weekends, or comma-separated (mon,tue,wed,...)",
    ),
    lat: float | None = typer.Option(
        None, "--lat", help="Latitude (uses vehicle location if omitted)"
    ),
    lon: float | None = typer.Option(
        None, "--lon", help="Longitude (uses vehicle location if omitted)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Add a location-based preconditioning schedule.

    tesla climate add-precondition-schedule 07:00
    tesla climate add-precondition-schedule 07:30 --days weekdays --lat 37.42 --lon -122.08
    """
    import json as _json

    from tesla_cli.core.exceptions import ApiError, BackendNotSupportedError

    v = _vin(vin)
    backend = _backend()
    start_time = _parse_hhmm(time)
    days_val = _parse_days(days)

    # Fetch vehicle location if lat/lon omitted
    if lat is None or lon is None:
        try:
            drive = _with_wake(lambda b, v: b.get_drive_state(v), v)
            lat = lat if lat is not None else drive.get("latitude", 0.0)
            lon = lon if lon is not None else drive.get("longitude", 0.0)
        except Exception:
            lat = lat or 0.0
            lon = lon or 0.0

    try:
        result = backend.add_precondition_schedule(v, days_val, start_time, lat, lon)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)
    except ApiError as exc:
        if exc.status_code in (404, 403):
            console.print(
                "[yellow]Location-based preconditioning schedules not available for this account.[/yellow]"
            )
            raise typer.Exit(1)
        raise

    if is_json_mode():
        console.print_json(_json.dumps(result, default=str))
        return
    render_success(
        f"Preconditioning schedule added: {time} on {days_val} at ({lat:.4f}, {lon:.4f})"
    )


@climate_app.command("remove-precondition-schedule")
def climate_remove_precondition_schedule(
    schedule_id: int = typer.Argument(help="Schedule ID to remove"),
    vin: str | None = VinOption,
) -> None:
    """Remove a location-based preconditioning schedule by ID.

    tesla climate remove-precondition-schedule 42
    """
    import json as _json

    from tesla_cli.core.exceptions import ApiError, BackendNotSupportedError

    v = _vin(vin)
    backend = _backend()

    try:
        result = backend.remove_precondition_schedule(v, schedule_id)
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)
    except ApiError as exc:
        if exc.status_code in (404, 403):
            console.print("[yellow]Schedule not found or not available for this account.[/yellow]")
            raise typer.Exit(1)
        raise

    if is_json_mode():
        console.print_json(_json.dumps(result, default=str))
        return
    render_success(f"Preconditioning schedule {schedule_id} removed")
