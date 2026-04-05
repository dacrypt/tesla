"""Scene commands: composite workflows for common daily patterns."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from rich.panel import Panel
from rich.table import Table

from tesla_cli.cli.output import console
from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin

scenes_app = typer.Typer(name="scene", help="Smart scene commands — common workflows in one command.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias (uses default if omitted)")


def _backend():
    return get_vehicle_backend(load_config())


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


def _fetch_parallel(tasks: dict) -> dict:
    """Run a dict of {key: callable} in parallel, return {key: result_or_exception}."""
    results: dict = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {executor.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:  # noqa: BLE001
                results[key] = exc
    return results


def _safe_get(results: dict, key: str, default=None):
    val = results.get(key, default)
    return default if isinstance(val, Exception) else val


@scenes_app.command("morning")
def scene_morning(vin: str | None = VinOption) -> None:
    """Morning briefing — battery, climate, readiness, location."""
    v = _vin(vin)
    backend = _backend()

    console.print("[dim]Fetching vehicle data...[/dim]")

    data = _fetch_parallel(
        {
            "charge": lambda: backend.get_charge_state(v),
            "climate": lambda: backend.get_climate_state(v),
            "drive": lambda: backend.get_drive_state(v),
            "vehicle": lambda: backend.get_vehicle_data(v),
        }
    )

    charge = _safe_get(data, "charge", {})
    climate = _safe_get(data, "climate", {})
    drive = _safe_get(data, "drive", {})
    vehicle = _safe_get(data, "vehicle", {})

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="bold cyan", min_width=18)
    table.add_column("Value")

    # Battery
    battery_level = charge.get("battery_level", "?")
    charge_limit = charge.get("charge_limit_soc", "?")
    est_range = charge.get("battery_range", charge.get("est_battery_range", "?"))
    charging_state = charge.get("charging_state", "Unknown")

    battery_color = "green" if isinstance(battery_level, int) and battery_level >= 50 else "yellow"
    table.add_row(
        "Battery",
        f"[{battery_color}]{battery_level}%[/{battery_color}] (limit {charge_limit}%)"
        f"  ~{est_range:.0f} mi" if isinstance(est_range, float) else
        f"[{battery_color}]{battery_level}%[/{battery_color}] (limit {charge_limit}%)",
    )
    table.add_row("Charge State", charging_state)

    # Climate
    inside_temp = climate.get("inside_temp")
    outside_temp = climate.get("outside_temp")
    climate_on = climate.get("is_climate_on", False)
    climate_status = "[green]On[/green]" if climate_on else "[dim]Off[/dim]"
    temps = []
    if inside_temp is not None:
        temps.append(f"inside {inside_temp:.1f}°C")
    if outside_temp is not None:
        temps.append(f"outside {outside_temp:.1f}°C")
    table.add_row("Climate", f"{climate_status}  {', '.join(temps)}" if temps else climate_status)

    # Location / drive state
    shift_state = drive.get("shift_state") or "P"
    speed = drive.get("speed")
    location_parts = [f"Gear: {shift_state}"]
    if speed:
        location_parts.append(f"Speed: {speed} mph")
    table.add_row("Drive State", "  ".join(location_parts))

    # Vehicle / software
    sw_version = vehicle.get("vehicle_state", {}).get("car_version", "") if isinstance(vehicle, dict) else ""
    if sw_version:
        table.add_row("Software", sw_version)

    # Locks / sentry
    locked = None
    sentry_on = None
    if isinstance(vehicle, dict):
        vs = vehicle.get("vehicle_state", {})
        locked = vs.get("locked")
        sentry_on = vs.get("sentry_mode")

    if locked is not None:
        lock_str = "[green]Locked[/green]" if locked else "[red]Unlocked[/red]"
        table.add_row("Doors", lock_str)
    if sentry_on is not None:
        sentry_str = "[green]On[/green]" if sentry_on else "[dim]Off[/dim]"
        table.add_row("Sentry", sentry_str)

    console.print(Panel(table, title="[bold cyan]Good Morning — Vehicle Briefing[/bold cyan]", border_style="cyan"))


@scenes_app.command("goodnight")
def scene_goodnight(vin: str | None = VinOption) -> None:
    """Night check — lock, sentry, charge schedule, battery."""
    v = _vin(vin)
    backend = _backend()

    console.print("[dim]Running night check...[/dim]")

    data = _fetch_parallel(
        {
            "charge": lambda: backend.get_charge_state(v),
            "vehicle": lambda: backend.get_vehicle_data(v),
        }
    )

    charge = _safe_get(data, "charge", {})
    vehicle = _safe_get(data, "vehicle", {})

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Check", style="bold cyan", min_width=20)
    table.add_column("Status")

    def _check(ok: bool | None, ok_text: str, warn_text: str) -> str:
        if ok is None:
            return "[dim]Unknown[/dim]"
        return f"[green]OK[/green]  {ok_text}" if ok else f"[red]WARN[/red]  {warn_text}"

    # Lock status
    locked = None
    sentry_on = None
    if isinstance(vehicle, dict):
        vs = vehicle.get("vehicle_state", {})
        locked = vs.get("locked")
        sentry_on = vs.get("sentry_mode")

    table.add_row("Doors locked", _check(locked, "Locked", "Doors are UNLOCKED"))
    table.add_row("Sentry Mode", _check(sentry_on, "Sentry ON", "Sentry is OFF"))

    # Charge
    battery_level = charge.get("battery_level")
    charge_limit = charge.get("charge_limit_soc", 80)
    charging_state = charge.get("charging_state", "Unknown")
    scheduled_charging = charge.get("scheduled_charging_pending", False)

    if battery_level is not None:
        battery_color = "green" if battery_level >= 50 else "yellow" if battery_level >= 20 else "red"
        table.add_row(
            "Battery",
            f"[{battery_color}]{battery_level}%[/{battery_color}] (limit {charge_limit}%)",
        )

    charge_ok = charging_state in ("Charging", "Complete") or scheduled_charging
    table.add_row(
        "Charge scheduled",
        _check(charge_ok, f"State: {charging_state}", f"Not charging — state: {charging_state}"),
    )

    console.print(Panel(table, title="[bold blue]Goodnight Check[/bold blue]", border_style="blue"))


@scenes_app.command("trip")
def scene_trip(
    destination: str = typer.Argument("", help="Destination address (optional)"),
    vin: str | None = VinOption,
) -> None:
    """Pre-trip prep — battery, range, climate, tire pressure, navigation."""
    v = _vin(vin)
    backend = _backend()

    console.print("[dim]Preparing for trip...[/dim]")

    data = _fetch_parallel(
        {
            "charge": lambda: backend.get_charge_state(v),
            "climate": lambda: backend.get_climate_state(v),
            "vehicle": lambda: backend.get_vehicle_data(v),
        }
    )

    charge = _safe_get(data, "charge", {})
    climate = _safe_get(data, "climate", {})
    vehicle = _safe_get(data, "vehicle", {})

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Check", style="bold cyan", min_width=20)
    table.add_column("Status")

    # Battery / range
    battery_level = charge.get("battery_level", "?")
    est_range = charge.get("battery_range", charge.get("est_battery_range"))
    battery_color = (
        "green" if isinstance(battery_level, int) and battery_level >= 50
        else "yellow" if isinstance(battery_level, int) and battery_level >= 20
        else "red"
    )
    range_str = f"  ~{est_range:.0f} mi range" if isinstance(est_range, float) else ""
    table.add_row(
        "Battery",
        f"[{battery_color}]{battery_level}%[/{battery_color}]{range_str}",
    )

    # Climate
    climate_on = climate.get("is_climate_on", False)
    inside_temp = climate.get("inside_temp")
    driver_temp = climate.get("driver_temp_setting")
    climate_parts = ["[green]On[/green]" if climate_on else "[dim]Off[/dim]"]
    if inside_temp is not None:
        climate_parts.append(f"inside {inside_temp:.1f}°C")
    if driver_temp is not None:
        climate_parts.append(f"set {driver_temp:.1f}°C")
    table.add_row("Climate", "  ".join(climate_parts))

    # Tire pressure (from vehicle_state if available)
    tire_info = []
    if isinstance(vehicle, dict):
        vs = vehicle.get("vehicle_state", {})
        tire_map = {
            "tpms_pressure_fl": "FL",
            "tpms_pressure_fr": "FR",
            "tpms_pressure_rl": "RL",
            "tpms_pressure_rr": "RR",
        }
        for key, label in tire_map.items():
            val = vs.get(key)
            if val is not None:
                tire_info.append(f"{label}:{val:.1f}")
    if tire_info:
        table.add_row("Tire Pressure (bar)", "  ".join(tire_info))

    # Destination / navigation
    if destination:
        try:
            backend.command(v, "navigation_request", type="share_ext_content_raw", value={
                "android.intent.extra.TEXT": destination,
                "content-version": 1,
                "share_name": destination,
            })
            table.add_row("Navigation", f"[green]Sent[/green]  {destination}")
        except Exception as exc:  # noqa: BLE001
            table.add_row("Navigation", f"[yellow]Failed[/yellow]  {exc}")
    else:
        table.add_row("Navigation", "[dim]No destination given[/dim]")

    title = f"[bold green]Trip Prep — {destination}[/bold green]" if destination else "[bold green]Pre-Trip Check[/bold green]"
    console.print(Panel(table, title=title, border_style="green"))
