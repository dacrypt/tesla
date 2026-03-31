"""TeslaMate integration commands: tesla teslaMate trips/charging/updates/status."""

from __future__ import annotations

import json

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.config import load_config, save_config
from tesla_cli.output import console, is_json_mode, render_success, render_table

teslaMate_app = typer.Typer(
    name="teslaMate",
    help="TeslaMate database integration — trips, charging, OTA history.",
)


def _backend():
    from tesla_cli.backends.teslaMate import TeslaMateBacked
    cfg = load_config()
    url = cfg.teslaMate.database_url
    if not url:
        console.print(
            "[red]TeslaMate not configured.[/red]\n"
            "Run: [bold]tesla teslaMate connect postgresql://user:pass@host:5432/teslaMate[/bold]"
        )
        raise typer.Exit(1)
    return TeslaMateBacked(url, car_id=cfg.teslaMate.car_id)


@teslaMate_app.command("connect")
def teslaMate_connect(
    database_url: str = typer.Argument(
        ..., help="PostgreSQL URL: postgresql://user:pass@host:5432/teslaMate"
    ),
    car_id: int = typer.Option(1, "--car-id", "-c", help="TeslaMate car ID (1-based, default 1)"),
) -> None:
    """Configure and test a TeslaMate database connection.

    tesla teslaMate connect postgresql://user:pass@localhost:5432/teslaMate
    tesla teslaMate connect postgresql://user:pass@myserver/teslaMate --car-id 2
    """
    cfg = load_config()
    cfg.teslaMate.database_url = database_url
    cfg.teslaMate.car_id = car_id

    # Test connection
    from tesla_cli.backends.teslaMate import TeslaMateBacked
    backend = TeslaMateBacked(database_url, car_id=car_id)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Testing connection...", total=None)
        try:
            ok = backend.ping()
            cars = backend.get_cars() if ok else []
        except Exception as exc:
            console.print(f"[red]Connection failed:[/red] {exc}")
            raise typer.Exit(1)

    if not ok:
        console.print("[red]Connection failed[/red] — ping returned False")
        raise typer.Exit(1)

    save_config(cfg)
    render_success(f"Connected to TeslaMate ({database_url})")

    if cars:
        console.print("\n  [dim]Cars in DB:[/dim]")
        for car in cars:
            active = " ← [bold cyan](selected)[/bold cyan]" if car["id"] == car_id else ""
            console.print(f"    [{car['id']}] {car.get('name') or '(unnamed)'} — {car.get('vin', '?')}{active}")


@teslaMate_app.command("status")
def teslaMate_status() -> None:
    """Show TeslaMate connection status and lifetime stats."""
    backend = _backend()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task("Fetching stats...", total=None)
        ok = backend.ping()
        drive_stats = backend.get_stats() if ok else {}
        charge_stats = backend.get_charging_stats() if ok else {}
        cars = backend.get_cars() if ok else []

    cfg = load_config()
    status_data = {
        "connected": ok,
        "database_url": cfg.teslaMate.database_url.split("@")[-1] if "@" in cfg.teslaMate.database_url else cfg.teslaMate.database_url,
        "car_id": cfg.teslaMate.car_id,
        "total_drives": drive_stats.get("total_drives", 0),
        "total_km": str(drive_stats.get("total_km", 0)),
        "total_kwh_driven": str(drive_stats.get("total_kwh", 0)),
        "first_drive": str(drive_stats.get("first_drive", ""))[:19],
        "last_drive": str(drive_stats.get("last_drive", ""))[:19],
        "total_charging_sessions": charge_stats.get("total_sessions", 0),
        "total_kwh_charged": str(charge_stats.get("total_kwh_added", 0)),
        "total_charging_cost": f"${charge_stats.get('total_cost', 0):.2f}",
    }

    if is_json_mode():
        console.print_json(json.dumps(status_data, indent=2, default=str))
        return

    from rich.panel import Panel
    status_icon = "[green]✅ Connected[/green]" if ok else "[red]❌ Not connected[/red]"
    console.print()
    console.print(Panel(
        f"{status_icon}  │  DB: [dim]{status_data['database_url']}[/dim]  │  Car ID: [cyan]{cfg.teslaMate.car_id}[/cyan]",
        title="[bold]TeslaMate Integration[/bold]",
        border_style="cyan",
    ))

    if ok:
        console.print("\n[bold]Driving[/bold]")
        _kv([
            ("Total trips", str(drive_stats.get("total_drives", 0))),
            ("Total distance", f"{drive_stats.get('total_km', 0)} km"),
            ("Total energy", f"{drive_stats.get('total_kwh', 0)} kWh"),
            ("Avg per trip", f"{drive_stats.get('avg_km_per_trip', 0)} km"),
            ("Longest trip", f"{drive_stats.get('longest_trip_km', 0)} km"),
            ("First drive", str(drive_stats.get("first_drive", ""))[:19]),
            ("Last drive", str(drive_stats.get("last_drive", ""))[:19]),
        ])
        console.print("\n[bold]Charging[/bold]")
        _kv([
            ("Total sessions", str(charge_stats.get("total_sessions", 0))),
            ("Total energy added", f"{charge_stats.get('total_kwh_added', 0)} kWh"),
            ("Total cost", f"${charge_stats.get('total_cost', 0):.2f}"),
            ("Avg per session", f"{charge_stats.get('avg_kwh_per_session', 0)} kWh"),
        ])

    if cars:
        console.print("\n[bold]Cars in DB[/bold]")
        for car in cars:
            active = " ← [bold cyan]active[/bold cyan]" if car["id"] == cfg.teslaMate.car_id else ""
            console.print(f"  [{car['id']}] {car.get('name') or '(unnamed)'}  VIN: [dim]{car.get('vin', '?')}[/dim]{active}")


@teslaMate_app.command("trips")
def teslaMate_trips(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of trips to show"),
    csv_out: str | None = typer.Option(None, "--csv", help="Save output to CSV file"),
) -> None:
    """Show recent trip history from TeslaMate.

    tesla teslaMate trips
    tesla teslaMate trips --limit 50
    tesla -j teslaMate trips | jq '.[0]'
    """
    backend = _backend()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task(f"Fetching last {limit} trips...", total=None)
        trips = backend.get_trips(limit=limit)

    if csv_out:
        import csv as _csv
        import pathlib  # noqa: F401
        if not trips:
            console.print("[yellow]No data to export.[/yellow]")
            raise typer.Exit(0)
        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            writer = _csv.DictWriter(fh, fieldnames=list(trips[0].keys()))
            writer.writeheader()
            writer.writerows(trips)
        console.print(f"  [green]\u2713[/green] Saved {len(trips)} rows to [bold]{csv_out}[/bold]")
        return

    if is_json_mode():
        console.print_json(json.dumps(trips, indent=2, default=str))
        return

    if not trips:
        console.print("[yellow]No trips found in TeslaMate.[/yellow]")
        return

    table = Table(
        title=f"Last {len(trips)} Trips (TeslaMate)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Date", width=17)
    table.add_column("From", width=22)
    table.add_column("To", width=22)
    table.add_column("km", justify="right", width=7)
    table.add_column("min", justify="right", width=5)
    table.add_column("kWh", justify="right", width=7)
    table.add_column("🔋 start→end", width=12)

    for i, t in enumerate(trips, 1):
        date = str(t.get("start_date") or "")[:16]
        frm = (t.get("start_address") or "")[:21]
        to = (t.get("end_address") or "")[:21]
        km = str(t.get("distance_km") or "-")
        mins = str(t.get("duration_min") or "-")
        kwh = str(t.get("energy_kwh") or "-")
        s_batt = t.get("start_battery_level")
        e_batt = t.get("end_battery_level")
        batt = f"{s_batt}% → {e_batt}%" if s_batt is not None else "-"
        table.add_row(str(i), date, frm, to, km, mins, kwh, batt)

    console.print(table)

    # Summary line
    total_km = sum(float(t.get("distance_km") or 0) for t in trips)
    total_kwh = sum(float(t.get("energy_kwh") or 0) for t in trips)
    console.print(f"\n  [dim]Showing {len(trips)} trips │ {total_km:.0f} km │ {total_kwh:.1f} kWh[/dim]")


@teslaMate_app.command("charging")
def teslaMate_charging(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of sessions to show"),
    csv_out: str | None = typer.Option(None, "--csv", help="Save output to CSV file"),
) -> None:
    """Show recent charging session history from TeslaMate.

    tesla teslaMate charging
    tesla teslaMate charging --limit 50
    tesla -j teslaMate charging | jq '.[] | select(.cost != null)'
    """
    backend = _backend()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task(f"Fetching last {limit} charging sessions...", total=None)
        sessions = backend.get_charging_sessions(limit=limit)

    if csv_out:
        import csv as _csv
        import pathlib  # noqa: F401
        if not sessions:
            console.print("[yellow]No data to export.[/yellow]")
            raise typer.Exit(0)
        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            writer = _csv.DictWriter(fh, fieldnames=list(sessions[0].keys()))
            writer.writeheader()
            writer.writerows(sessions)
        console.print(f"  [green]\u2713[/green] Saved {len(sessions)} rows to [bold]{csv_out}[/bold]")
        return

    if is_json_mode():
        console.print_json(json.dumps(sessions, indent=2, default=str))
        return

    if not sessions:
        console.print("[yellow]No charging sessions found in TeslaMate.[/yellow]")
        return

    table = Table(
        title=f"Last {len(sessions)} Charging Sessions (TeslaMate)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Date", width=17)
    table.add_column("Location", width=30)
    table.add_column("kWh added", justify="right", width=10)
    table.add_column("Cost", justify="right", width=8)
    table.add_column("🔋 start→end", width=12)

    for i, s in enumerate(sessions, 1):
        date = str(s.get("start_date") or "")[:16]
        loc = (s.get("location") or "Unknown")[:29]
        kwh = str(s.get("energy_added_kwh") or "-")
        cost = f"${s.get('cost'):.2f}" if s.get("cost") is not None else "-"
        s_batt = s.get("start_battery_level")
        e_batt = s.get("end_battery_level")
        batt = f"{s_batt}% → {e_batt}%" if s_batt is not None else "-"
        table.add_row(str(i), date, loc, kwh, cost, batt)

    console.print(table)

    total_kwh = sum(float(s.get("energy_added_kwh") or 0) for s in sessions)
    total_cost = sum(float(s.get("cost") or 0) for s in sessions)
    console.print(f"\n  [dim]{len(sessions)} sessions │ {total_kwh:.1f} kWh added │ ${total_cost:.2f} total cost[/dim]")


@teslaMate_app.command("updates")
def teslaMate_updates() -> None:
    """Show software OTA update history from TeslaMate.

    tesla teslaMate updates
    tesla -j teslaMate updates | jq '.[] | .version'
    """
    backend = _backend()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task("Fetching OTA history...", total=None)
        updates = backend.get_updates()

    if is_json_mode():
        console.print_json(json.dumps(updates, indent=2, default=str))
        return

    if not updates:
        console.print("[yellow]No OTA updates found in TeslaMate.[/yellow]")
        return

    table = Table(
        title=f"Software OTA History — {len(updates)} updates (TeslaMate)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Version", style="bold", width=20)
    table.add_column("Installed", width=17)
    table.add_column("Duration")

    for i, u in enumerate(updates, 1):
        ver = u.get("version") or "-"
        start = str(u.get("start_date") or "")[:16]
        end_dt = u.get("end_date")
        start_dt = u.get("start_date")
        if end_dt and start_dt:
            try:
                from datetime import datetime
                s = datetime.fromisoformat(str(start_dt).replace("Z", "+00:00").replace(" ", "T"))
                e = datetime.fromisoformat(str(end_dt).replace("Z", "+00:00").replace(" ", "T"))
                mins = int((e - s).total_seconds() / 60)
                duration = f"{mins} min"
            except Exception:
                duration = "-"
        else:
            duration = "-"
        table.add_row(str(i), ver, start, duration)

    console.print(table)


@teslaMate_app.command("efficiency")
def teslaMate_efficiency(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of trips to analyze"),
    csv_out: str | None = typer.Option(None, "--csv", help="Save output to CSV file"),
) -> None:
    """Show per-trip energy efficiency from TeslaMate.

    tesla teslaMate efficiency
    tesla teslaMate efficiency --limit 50
    tesla -j teslaMate efficiency | jq '[.[] | .wh_per_km] | add / length'
    """
    backend = _backend()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task(f"Calculating efficiency for last {limit} trips...", total=None)
        trips = backend.get_efficiency(limit=limit)

    if csv_out:
        import csv as _csv
        import pathlib  # noqa: F401
        if not trips:
            console.print("[yellow]No data to export.[/yellow]")
            raise typer.Exit(0)
        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            writer = _csv.DictWriter(fh, fieldnames=list(trips[0].keys()))
            writer.writeheader()
            writer.writerows(trips)
        console.print(f"  [green]\u2713[/green] Saved {len(trips)} rows to [bold]{csv_out}[/bold]")
        return

    if is_json_mode():
        console.print_json(json.dumps(trips, indent=2, default=str))
        return

    if not trips:
        console.print("[yellow]No trip data found in TeslaMate.[/yellow]")
        return

    table = Table(
        title=f"Energy Efficiency — Last {len(trips)} Trips (TeslaMate)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Date", width=17)
    table.add_column("From→To", width=28)
    table.add_column("km", justify="right", width=7)
    table.add_column("kWh", justify="right", width=7)
    table.add_column("Wh/km", justify="right", width=7)
    table.add_column("kWh/100mi", justify="right", width=10)

    total_km = 0.0
    total_kwh = 0.0

    for i, t in enumerate(trips, 1):
        date = str(t.get("start_date") or "")[:16]
        frm = (t.get("start_address") or "")[:13]
        to = (t.get("end_address") or "")[:13]
        route = f"{frm}→{to}" if frm or to else "—"
        km = float(t.get("distance_km") or 0)
        kwh = float(t.get("energy_kwh") or 0)
        wh_km = str(t.get("wh_per_km") or "—")
        kwh_100mi = str(t.get("kwh_per_100mi") or "—")
        total_km += km
        total_kwh += kwh
        table.add_row(str(i), date, route[:27], f"{km:.1f}", f"{kwh:.2f}", wh_km, kwh_100mi)

    console.print(table)

    avg_wh_km = (total_kwh * 1000 / total_km) if total_km else 0
    avg_kwh_100mi = (total_kwh / (total_km / 160.934) * 100) if total_km else 0
    console.print(
        f"\n  [dim]{len(trips)} trips │ {total_km:.0f} km │ {total_kwh:.1f} kWh │ "
        f"avg {avg_wh_km:.0f} Wh/km │ avg {avg_kwh_100mi:.1f} kWh/100mi[/dim]"
    )


@teslaMate_app.command("vampire")
def teslaMate_vampire(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
) -> None:
    """Show vampire drain (battery loss while parked) from TeslaMate.

    tesla teslaMate vampire
    tesla teslaMate vampire --days 90
    tesla -j teslaMate vampire | jq '.avg_pct_per_hour'
    """
    backend = _backend()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()) as p:
        p.add_task(f"Analyzing vampire drain over {days} days...", total=None)
        result = backend.get_vampire_drain(days=days)

    if is_json_mode():
        console.print_json(json.dumps(result, indent=2, default=str))
        return

    daily = result.get("daily", [])
    avg_per_hour = result.get("avg_pct_per_hour")

    if not daily:
        console.print("[yellow]No vampire drain data found for the selected period.[/yellow]")
        return

    # Summary
    console.print()
    if avg_per_hour is not None:
        color = "green" if float(avg_per_hour) < 0.05 else "yellow" if float(avg_per_hour) < 0.15 else "red"
        console.print(f"  Average vampire drain: [{color}]{avg_per_hour:.3f}% / hour[/{color}]")
        daily_equiv = round(float(avg_per_hour) * 24, 1)
        console.print(f"  \u2248 [dim]{daily_equiv}% per 24 hours while parked[/dim]")
    console.print()

    table = Table(
        title=f"Vampire Drain \u2014 Last {days} Days (TeslaMate)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Date", width=12)
    table.add_column("Periods", justify="right", width=8)
    table.add_column("Avg drain %", justify="right", width=11)
    table.add_column("Avg parked h", justify="right", width=12)
    table.add_column("% / hour", justify="right", width=9)

    for row in daily[:20]:
        pph = float(row["pct_per_hour"]) if row["pct_per_hour"] else 0
        pph_color = "green" if pph < 0.05 else "yellow" if pph < 0.15 else "red"
        table.add_row(
            str(row.get("date") or "")[:10],
            str(row.get("periods") or "-"),
            f"{row.get('avg_drain_pct') or 0:.2f}%",
            f"{row.get('avg_parked_hours') or 0:.1f}h",
            f"[{pph_color}]{pph:.3f}[/{pph_color}]",
        )
    console.print(table)


@teslaMate_app.command("geo")
def teslaMate_geo(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of top locations to show"),
    csv_out: str | None = typer.Option(None, "--csv", help="Save output to CSV file"),
) -> None:
    """Show most-visited locations from TeslaMate.

    tesla teslaMate geo
    tesla teslaMate geo --limit 20
    tesla -j teslaMate geo | jq '.[] | select(.visit_count > 5)'
    """
    import json as _json

    backend = _backend()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task("Loading location data...", total=None)
        locations = backend.get_top_locations(limit=limit)

    if not locations:
        console.print("[yellow]No location data found in TeslaMate.[/yellow]")
        return

    if csv_out:
        import csv as _csv
        from pathlib import Path  # noqa: F401
        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            writer = _csv.DictWriter(fh, fieldnames=list(locations[0].keys()))
            writer.writeheader()
            writer.writerows([{k: str(v) for k, v in row.items()} for row in locations])
        console.print(f"  [green]\u2713[/green] Saved {len(locations)} rows to [bold]{csv_out}[/bold]")
        return

    if is_json_mode():
        console.print(_json.dumps(locations, indent=2, default=str))
        return

    render_table(
        [{
            "location": r["location"][:40] if r["location"] else "\u2014",
            "visits": r["visit_count"],
            "lat": f"{r['latitude']:.4f}" if r.get("latitude") else "\u2014",
            "lon": f"{r['longitude']:.4f}" if r.get("longitude") else "\u2014",
            "arrival_pct": f"{r['min_arrival_pct']}\u2013{r['max_arrival_pct']}%",
        } for r in locations],
        columns=["location", "visits", "lat", "lon", "arrival_pct"],
        title=f"Top {len(locations)} Most Visited Locations",
    )


# ── helpers ──

def _kv(rows: list[tuple[str, str]]) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("k", style="dim", width=22)
    table.add_column("v")
    for k, v in rows:
        if v and v != "None" and v != "0" and v != "$0.00":
            table.add_row(k, v)
    console.print(table)
