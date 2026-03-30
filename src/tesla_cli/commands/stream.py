"""Streaming telemetry — real-time vehicle data via polling or WebSocket."""

from __future__ import annotations

import time

import typer

from tesla_cli.output import console, is_json_mode

stream_app = typer.Typer(name="stream", help="Real-time vehicle telemetry.")


@stream_app.command("live")
def stream_live(
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
    interval: float = typer.Option(5.0, "--interval", "-i", help="Refresh interval in seconds"),
    count: int = typer.Option(0, "--count", "-n", help="Stop after N refreshes (0 = run forever)"),
) -> None:
    """Stream live vehicle data, refreshing every N seconds.

    Polls the Owner API and renders a live dashboard with:
    - State (online/asleep), battery, charge rate
    - Location (lat/lon, speed, heading)
    - Climate (inside/outside temperature, HVAC on/off)
    - Odometer, sentry mode, locked status

    Press Ctrl+C to stop.
    """
    import json as _json

    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    from tesla_cli.backends import get_vehicle_backend
    from tesla_cli.config import load_config, resolve_vin
    from tesla_cli.exceptions import VehicleAsleepError

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    backend = get_vehicle_backend(cfg)

    refreshes = 0
    last_error: str | None = None

    def _build_panel() -> Panel:
        nonlocal last_error
        try:
            data = backend.get_vehicle_data(v)
            last_error = None
        except VehicleAsleepError:
            last_error = "Vehicle is asleep (data from last known state)"
            data = {}
        except Exception as exc:
            last_error = str(exc)
            data = {}

        if is_json_mode():
            console.print_json(_json.dumps(data, indent=2, default=str))
            raise typer.Exit(0)

        charge = data.get("charge_state", {})
        climate = data.get("climate_state", {})
        drive = data.get("drive_state", {})
        vehicle = data.get("vehicle_state", {})
        gui = data.get("gui_settings", {})

        dist_unit = gui.get("gui_distance_units", "mi/hr")
        temp_unit = gui.get("gui_temperature_units", "F")

        # ── Build table ──
        table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
        table.add_column("Label", style="bold cyan", width=22)
        table.add_column("Value")

        def row(label: str, value: str) -> None:
            table.add_row(label, value)

        row("VIN", v)
        row("State", data.get("state", "[dim]unknown[/dim]"))
        row("", "")

        # Charge
        soc = charge.get("battery_level", "?")
        soc_color = "green" if isinstance(soc, int) and soc > 30 else "yellow" if isinstance(soc, int) and soc > 15 else "red"
        est_range = charge.get("battery_range", charge.get("ideal_battery_range", "?"))
        row("Battery", f"[{soc_color}]{soc}%[/{soc_color}]  │  {est_range} {dist_unit}")
        cs = charge.get("charging_state", "")
        if cs:
            charge_power = charge.get("charger_power", 0)
            time_full = charge.get("time_to_full_charge", 0)
            row("Charging", f"{cs}  │  {charge_power} kW  │  {time_full:.1f} hrs to full")
        limit = charge.get("charge_limit_soc", "?")
        row("Charge Limit", f"{limit}%")
        row("", "")

        # Climate
        inside_t = climate.get("inside_temp", "?")
        outside_t = climate.get("outside_temp", "?")
        hvac = "[green]ON[/green]" if climate.get("is_climate_on") else "[dim]OFF[/dim]"
        row("Temperature", f"Inside: {inside_t}°{temp_unit}  │  Outside: {outside_t}°{temp_unit}")
        row("HVAC", hvac)
        row("", "")

        # Location / Drive
        lat = drive.get("latitude", "?")
        lon = drive.get("longitude", "?")
        speed = drive.get("speed", 0) or 0
        heading = drive.get("heading", "?")
        if lat != "?":
            maps_url = f"https://maps.google.com/?q={lat},{lon}"
            row("Location", f"{lat:.4f}, {lon:.4f}  │  {speed} {dist_unit.split('/')[0]}  │  {heading}°")
            row("Maps", maps_url)
        row("", "")

        # Vehicle state
        locked = "[green]🔒 Locked[/green]" if vehicle.get("locked") else "[red]🔓 Unlocked[/red]"
        sentry = "[yellow]🛡 Sentry ON[/yellow]" if vehicle.get("sentry_mode") else "[dim]Sentry OFF[/dim]"
        odo = vehicle.get("odometer", "?")
        row("Doors", locked)
        row("Sentry", sentry)
        if odo != "?":
            row("Odometer", f"{odo:.1f} {dist_unit.split('/')[0]}")
        sw = vehicle.get("car_version", "")
        if sw:
            row("Software", sw)

        footer = Text.assemble(
            ("  Refreshed: ", "dim"),
            (time.strftime("%H:%M:%S"), "bold"),
            (f"  │  Auto-refresh every {interval}s  │  Ctrl+C to stop", "dim"),
        )
        if last_error:
            footer = Text.assemble(("  ⚠ ", "yellow"), (last_error, "yellow dim"), ("  ", ""))

        return Panel(
            table,
            title=f"[bold cyan]⚡ Tesla Live  {v}[/bold cyan]",
            subtitle=footer,
            border_style="cyan",
        )

    console.print("[dim]Starting live stream… press Ctrl+C to stop.[/dim]\n")
    try:
        with Live(console=console, refresh_per_second=1, screen=False) as live:
            while True:
                live.update(_build_panel())
                refreshes += 1
                if count and refreshes >= count:
                    break
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[bold]Stream stopped.[/bold]")
