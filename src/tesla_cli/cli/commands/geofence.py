"""Geofence commands: tesla geofence add|list|remove|watch.

Named geographic zones with continuous enter/exit alerts.
Zones are stored in config.toml under [geofences].
"""

from __future__ import annotations

import math
import time

import typer

from tesla_cli.cli.commands.vehicle import _with_wake
from tesla_cli.core.config import load_config, resolve_vin, save_config
from tesla_cli.cli.output import console, is_json_mode, render_success, render_table

geofence_app = typer.Typer(
    name="geofence",
    help="Named geofence zones with enter/exit alerts.",
)

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two GPS points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ──────────────────────────────────────────────────────────────────────────────


@geofence_app.command("add")
def geofence_add(
    name: str   = typer.Argument(..., help="Zone name (e.g. home, work, charger)"),
    lat: float  = typer.Option(..., "--lat", help="Latitude in decimal degrees"),
    lon: float  = typer.Option(..., "--lon", help="Longitude in decimal degrees"),
    radius: float = typer.Option(0.5, "--radius", "-r", help="Radius in km (default 0.5)"),
) -> None:
    """Add or update a named geofence zone.

    tesla geofence add home --lat 37.4219 --lon -122.0840
    tesla geofence add work --lat 37.3382 --lon -121.8863 --radius 0.3
    """
    import json as _json

    cfg = load_config()
    cfg.geofences.zones[name] = {"lat": lat, "lon": lon, "radius_km": radius}
    save_config(cfg)

    if is_json_mode():
        console.print(_json.dumps({"zone": name, "lat": lat, "lon": lon, "radius_km": radius, "status": "added"}))
        return
    render_success(f"Geofence '{name}' added: {lat:+.5f}, {lon:+.5f} r={radius} km")


@geofence_app.command("list")
def geofence_list() -> None:
    """List all configured geofence zones.

    tesla geofence list
    tesla -j geofence list
    """
    import json as _json

    cfg = load_config()
    zones = cfg.geofences.zones

    if not zones:
        console.print("[dim]No geofence zones configured.[/dim]")
        console.print("Add one with: [bold]tesla geofence add <name> <lat> <lon>[/bold]")
        return

    if is_json_mode():
        console.print(_json.dumps([
            {"name": n, **z} for n, z in zones.items()
        ], indent=2))
        return

    rows = [
        {"name": n, "lat": f"{z['lat']:+.5f}", "lon": f"{z['lon']:+.5f}", "radius_km": z.get("radius_km", 0.5)}
        for n, z in zones.items()
    ]
    render_table(rows, columns=["name", "lat", "lon", "radius_km"], title="Geofence Zones")


@geofence_app.command("remove")
def geofence_remove(
    name: str = typer.Argument(..., help="Zone name to remove"),
) -> None:
    """Remove a named geofence zone.

    tesla geofence remove home
    """
    import json as _json

    cfg = load_config()
    if name not in cfg.geofences.zones:
        console.print(f"[red]Zone '{name}' not found.[/red]")
        raise typer.Exit(1)

    del cfg.geofences.zones[name]
    save_config(cfg)

    if is_json_mode():
        console.print(_json.dumps({"zone": name, "status": "removed"}))
        return
    render_success(f"Geofence zone '{name}' removed.")


@geofence_app.command("watch")
def geofence_watch(
    interval: int = typer.Option(30, "--interval", "-i", help="Poll interval in seconds (default 30)"),
    notify: str = typer.Option("", "--notify", help="Apprise URL for enter/exit alerts"),
    vin: str | None = VinOption,
) -> None:
    """Watch for geofence enter/exit events (runs until Ctrl+C).

    tesla geofence watch
    tesla geofence watch --interval 15 --notify "tgram://botid/chatid"
    """
    import json as _json
    from datetime import datetime as _dt

    cfg = load_config()
    v   = resolve_vin(cfg, vin)

    zones = cfg.geofences.zones
    if not zones:
        console.print(
            "[yellow]No geofence zones defined.[/yellow]\n"
            "Add one with: [bold]tesla geofence add <name> <lat> <lon>[/bold]"
        )
        raise typer.Exit(1)

    notifier = None
    if notify:
        try:
            import apprise
            notifier = apprise.Apprise()
            notifier.add(notify)
        except ImportError:
            console.print("[yellow]⚠ apprise not installed — notifications disabled[/yellow]")

    # State: which zones is the vehicle currently inside?
    inside: set[str] = set()
    first_poll = True

    console.print(
        f"\n  [bold]Geofence watch[/bold] [dim]{v}[/dim] — "
        f"[bold]{len(zones)}[/bold] zones — "
        f"polling every [bold]{interval}s[/bold]\n"
        f"  [dim]Zones: {', '.join(zones)}[/dim]\n"
        "  [dim]Press Ctrl+C to stop.[/dim]\n"
    )

    try:
        while True:
            ts = _dt.now().strftime("%H:%M:%S")
            try:
                data = _with_wake(lambda b, vv: b.get_drive_state(vv), v)
                car_lat = data.get("latitude")
                car_lon = data.get("longitude")

                if car_lat is None or car_lon is None:
                    console.print(f"  [dim]{ts}[/dim]  [yellow]No GPS[/yellow]")
                    time.sleep(interval)
                    continue

                curr_inside: set[str] = set()
                distances: dict[str, float] = {}
                for name, zone in zones.items():
                    dist = _haversine_km(car_lat, car_lon, zone["lat"], zone["lon"])
                    distances[name] = dist
                    if dist <= zone.get("radius_km", 0.5):
                        curr_inside.add(name)

                events: list[str] = []
                if not first_poll:
                    for name in curr_inside - inside:
                        events.append(f"[green]ENTER[/green] {name} ({distances[name]:.2f} km from center)")
                    for name in inside - curr_inside:
                        events.append(f"[red]EXIT[/red]  {name} ({distances[name]:.2f} km from center)")

                if is_json_mode():
                    payload: dict = {
                        "ts": ts,
                        "lat": car_lat,
                        "lon": car_lon,
                        "inside": list(curr_inside),
                        "events": [e.replace("[green]", "").replace("[/green]", "").replace("[red]", "").replace("[/red]", "").strip() for e in events],
                    }
                    console.print(_json.dumps(payload))
                elif events:
                    for ev in events:
                        console.print(f"  [dim]{ts}[/dim]  {ev}")
                    if notifier:
                        body = "\n".join(e.replace("[green]", "").replace("[/green]", "").replace("[red]", "").replace("[/red]", "").strip() for e in events)
                        notifier.notify(title="Tesla Geofence", body=body)
                else:
                    zone_info = "  ".join(
                        f"[{'green' if n in curr_inside else 'dim'}]{n}[/{'green' if n in curr_inside else 'dim'}] {distances[n]:.1f}km"
                        for n in zones
                    )
                    console.print(f"  [dim]{ts}[/dim]  {zone_info}")

                inside = curr_inside
                first_poll = False

            except Exception as exc:  # noqa: BLE001
                console.print(f"  [dim]{ts}[/dim]  [red]Error:[/red] {exc}")

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n  [dim]Geofence watch stopped.[/dim]\n")
