"""Dashboard command: tesla dashboard — unified vehicle status view."""

from __future__ import annotations

import json

import typer
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table

from tesla_cli.commands.vehicle import _with_wake
from tesla_cli.config import load_config, resolve_vin
from tesla_cli.output import console, is_json_mode

dashboard_app = typer.Typer(name="dashboard", help="Unified vehicle status dashboard.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


def _bool_icon(val: bool | None) -> str:
    if val is None:
        return "❓"
    return "✅" if val else "❌"


def _make_battery_bar(level: int) -> str:
    filled = level // 5
    empty = 20 - filled
    if level > 60:
        color = "green"
    elif level > 20:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]{'█' * filled}{'░' * empty}[/{color}] {level}%"


@dashboard_app.command("show")
def dashboard_show(vin: str | None = VinOption) -> None:
    """Show unified vehicle dashboard."""
    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_vehicle_data(v), v)

    if is_json_mode():
        console.print(json.dumps(data, indent=2, default=str))
        return

    charge = data.get("charge_state", {})
    climate = data.get("climate_state", {})
    drive = data.get("drive_state", {})
    vehicle = data.get("vehicle_state", {})
    config = data.get("vehicle_config", {})

    # Battery & Charging panel
    battery_level = charge.get("battery_level", 0)
    battery_table = Table(show_header=False, box=None, padding=(0, 1))
    battery_table.add_column("K", style="bold cyan", width=20)
    battery_table.add_column("V")
    battery_table.add_row("Battery", _make_battery_bar(battery_level))
    battery_table.add_row("Range", f"{charge.get('battery_range', 0):.0f} mi")
    battery_table.add_row("Charge Limit", f"{charge.get('charge_limit_soc', 0)}%")
    battery_table.add_row("Charging", charge.get("charging_state", "Unknown"))
    if charge.get("charging_state") == "Charging":
        battery_table.add_row("Rate", f"{charge.get('charge_rate', 0)} mph")
        battery_table.add_row("Power", f"{charge.get('charger_power', 0)} kW")
        battery_table.add_row("Time Left", f"{charge.get('time_to_full_charge', 0):.1f} hr")
    battery_table.add_row("Charge Port", _bool_icon(charge.get("charge_port_door_open")))

    # Location panel
    lat = drive.get("latitude", 0)
    lon = drive.get("longitude", 0)
    loc_table = Table(show_header=False, box=None, padding=(0, 1))
    loc_table.add_column("K", style="bold cyan", width=20)
    loc_table.add_column("V")
    loc_table.add_row("Coordinates", f"{lat:.5f}, {lon:.5f}" if lat else "Unknown")
    loc_table.add_row("Heading", f"{drive.get('heading', 0)}°")
    speed = drive.get("speed")
    loc_table.add_row("Speed", f"{speed} mph" if speed else "Parked")
    if lat and lon:
        loc_table.add_row("Maps", f"https://maps.google.com/?q={lat},{lon}")

    # Security panel
    sec_table = Table(show_header=False, box=None, padding=(0, 1))
    sec_table.add_column("K", style="bold cyan", width=20)
    sec_table.add_column("V")
    sec_table.add_row("Locked", _bool_icon(vehicle.get("locked")))
    sec_table.add_row("Sentry Mode", _bool_icon(vehicle.get("sentry_mode")))
    sec_table.add_row("Valet Mode", _bool_icon(vehicle.get("valet_mode")))
    sec_table.add_row("Software", vehicle.get("car_version", "Unknown"))
    sec_table.add_row("Odometer", f"{vehicle.get('odometer', 0):,.0f} mi")

    # Climate panel
    cli_table = Table(show_header=False, box=None, padding=(0, 1))
    cli_table.add_column("K", style="bold cyan", width=20)
    cli_table.add_column("V")
    cli_table.add_row("Climate On", _bool_icon(climate.get("is_climate_on")))
    inside = climate.get("inside_temp")
    outside = climate.get("outside_temp")
    cli_table.add_row("Inside", f"{inside}°C" if inside is not None else "N/A")
    cli_table.add_row("Outside", f"{outside}°C" if outside is not None else "N/A")
    cli_table.add_row(
        "Set Temp",
        f"{climate.get('driver_temp_setting', 0)}°C / {climate.get('passenger_temp_setting', 0)}°C",
    )
    cli_table.add_row("Preconditioning", _bool_icon(climate.get("is_preconditioning")))

    # Vehicle info
    name = data.get("display_name", data.get("vehicle_name", v))
    model = config.get("car_type", "Tesla")

    panels = [
        Panel(battery_table, title="🔋 Battery & Charging", border_style="green"),
        Panel(loc_table, title="📍 Location", border_style="blue"),
        Panel(sec_table, title="🔒 Security", border_style="red"),
        Panel(cli_table, title="🌡️ Climate", border_style="yellow"),
    ]

    console.print()
    console.print(f"[bold]🚗 {name}[/bold] ({model}) — {v}")
    console.print()
    console.print(Columns(panels, equal=True, expand=True))
    console.print()


# Allow `tesla dashboard` without subcommand
@dashboard_app.callback(invoke_without_command=True)
def dashboard_default(
    ctx: typer.Context,
    vin: str | None = VinOption,
) -> None:
    """Show unified vehicle dashboard."""
    if ctx.invoked_subcommand is None:
        dashboard_show(vin=vin)
