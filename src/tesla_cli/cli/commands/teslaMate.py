"""TeslaMate integration commands: tesla teslaMate trips/charging/updates/status."""

from __future__ import annotations

import json

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.cli.output import console, is_json_mode, render_success, render_table
from tesla_cli.core.config import load_config, save_config

teslaMate_app = typer.Typer(
    name="teslaMate",
    help="TeslaMate database integration — trips, charging, OTA history.",
)


def _backend():
    from tesla_cli.core.backends.teslaMate import TeslaMateBacked

    cfg = load_config()
    url = cfg.teslaMate.database_url
    if not url:
        console.print(
            "[red]TeslaMate not configured.[/red]\n"
            "Run: [bold]tesla teslaMate install[/bold] to set up a managed stack,\n"
            "  or [bold]tesla teslaMate connect postgresql://user:pass@host:5432/teslaMate[/bold] for an external DB."
        )
        raise typer.Exit(1)
    # Warn if managed stack is installed but not running
    if cfg.teslaMate.managed:
        from pathlib import Path

        from tesla_cli.infra.teslamate_stack import TeslaMateStack

        stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
        if stack.is_installed() and not stack.is_running():
            console.print(
                "[yellow]TeslaMate stack is installed but not running.[/yellow]\n"
                "Start it with: [bold]tesla teslaMate start[/bold]\n"
            )
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
    from tesla_cli.core.backends.teslaMate import TeslaMateBacked

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
            console.print(
                f"    [{car['id']}] {car.get('name') or '(unnamed)'} — {car.get('vin', '?')}{active}"
            )


@teslaMate_app.command("status")
def teslaMate_status() -> None:
    """Show TeslaMate connection status and lifetime stats."""
    backend = _backend()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Fetching stats...", total=None)
        ok = backend.ping()
        drive_stats = backend.get_stats() if ok else {}
        charge_stats = backend.get_charging_stats() if ok else {}
        cars = backend.get_cars() if ok else []

    cfg = load_config()

    # Managed stack info
    stack_info: dict = {}
    if cfg.teslaMate.managed:
        from pathlib import Path

        from tesla_cli.infra.teslamate_stack import TeslaMateStack

        stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
        stack_info = {
            "managed": True,
            "installed": stack.is_installed(),
            "services": stack.status(),
        }

    status_data = {
        "connected": ok,
        "database_url": cfg.teslaMate.database_url.split("@")[-1]
        if "@" in cfg.teslaMate.database_url
        else cfg.teslaMate.database_url,
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
    if stack_info:
        status_data["stack"] = stack_info

    if is_json_mode():
        console.print_json(json.dumps(status_data, indent=2, default=str))
        return

    from rich.panel import Panel

    status_icon = "[green]Connected[/green]" if ok else "[red]Not connected[/red]"
    mode_label = "[cyan]managed[/cyan]" if cfg.teslaMate.managed else "[dim]external[/dim]"
    console.print()
    console.print(
        Panel(
            f"{status_icon}  |  Mode: {mode_label}  |  DB: [dim]{status_data['database_url']}[/dim]  |  Car ID: [cyan]{cfg.teslaMate.car_id}[/cyan]",
            title="[bold]TeslaMate Integration[/bold]",
            border_style="cyan",
        )
    )

    # Show managed stack container status
    if stack_info and stack_info.get("services"):
        console.print("\n[bold]Docker Stack[/bold]")
        st = Table(show_header=True, box=None, padding=(0, 2))
        st.add_column("Service", style="bold")
        st.add_column("State")
        st.add_column("Image", style="dim")
        st.add_column("Status")
        for svc in stack_info["services"]:
            state = svc.get("state", "unknown")
            state_styled = (
                f"[green]{state}[/green]" if state == "running" else f"[red]{state}[/red]"
            )
            st.add_row(svc["name"], state_styled, svc.get("image", ""), svc.get("status", ""))
        console.print(st)

    if ok:
        console.print("\n[bold]Driving[/bold]")
        _kv(
            [
                ("Total trips", str(drive_stats.get("total_drives", 0))),
                ("Total distance", f"{drive_stats.get('total_km', 0)} km"),
                ("Total energy", f"{drive_stats.get('total_kwh', 0)} kWh"),
                ("Avg per trip", f"{drive_stats.get('avg_km_per_trip', 0)} km"),
                ("Longest trip", f"{drive_stats.get('longest_trip_km', 0)} km"),
                ("First drive", str(drive_stats.get("first_drive", ""))[:19]),
                ("Last drive", str(drive_stats.get("last_drive", ""))[:19]),
            ]
        )
        console.print("\n[bold]Charging[/bold]")
        _kv(
            [
                ("Total sessions", str(charge_stats.get("total_sessions", 0))),
                ("Total energy added", f"{charge_stats.get('total_kwh_added', 0)} kWh"),
                ("Total cost", f"${charge_stats.get('total_cost', 0):.2f}"),
                ("Avg per session", f"{charge_stats.get('avg_kwh_per_session', 0)} kWh"),
            ]
        )

    if cars:
        console.print("\n[bold]Cars in DB[/bold]")
        for car in cars:
            active = (
                " <- [bold cyan]active[/bold cyan]" if car["id"] == cfg.teslaMate.car_id else ""
            )
            console.print(
                f"  [{car['id']}] {car.get('name') or '(unnamed)'}  VIN: [dim]{car.get('vin', '?')}[/dim]{active}"
            )


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

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
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
    console.print(
        f"\n  [dim]Showing {len(trips)} trips │ {total_km:.0f} km │ {total_kwh:.1f} kWh[/dim]"
    )


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

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
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
        console.print(
            f"  [green]\u2713[/green] Saved {len(sessions)} rows to [bold]{csv_out}[/bold]"
        )
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
    console.print(
        f"\n  [dim]{len(sessions)} sessions │ {total_kwh:.1f} kWh added │ ${total_cost:.2f} total cost[/dim]"
    )


@teslaMate_app.command("updates")
def teslaMate_updates() -> None:
    """Show software OTA update history from TeslaMate.

    tesla teslaMate updates
    tesla -j teslaMate updates | jq '.[] | .version'
    """
    backend = _backend()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
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

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
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

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
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
        color = (
            "green"
            if float(avg_per_hour) < 0.05
            else "yellow"
            if float(avg_per_hour) < 0.15
            else "red"
        )
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
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
    ) as p:
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
        console.print(
            f"  [green]\u2713[/green] Saved {len(locations)} rows to [bold]{csv_out}[/bold]"
        )
        return

    if is_json_mode():
        console.print(_json.dumps(locations, indent=2, default=str))
        return

    render_table(
        [
            {
                "location": r["location"][:40] if r["location"] else "\u2014",
                "visits": r["visit_count"],
                "lat": f"{r['latitude']:.4f}" if r.get("latitude") else "\u2014",
                "lon": f"{r['longitude']:.4f}" if r.get("longitude") else "\u2014",
                "arrival_pct": f"{r['min_arrival_pct']}\u2013{r['max_arrival_pct']}%",
            }
            for r in locations
        ],
        columns=["location", "visits", "lat", "lon", "arrival_pct"],
        title=f"Top {len(locations)} Most Visited Locations",
    )


@teslaMate_app.command("report")
def teslaMate_report(
    month: str = typer.Option(
        "",
        "--month",
        "-m",
        help="Month to report on (YYYY-MM). Defaults to current month.",
    ),
) -> None:
    """Show monthly driving and charging summary from TeslaMate.

    tesla teslaMate report
    tesla teslaMate report --month 2024-06
    tesla -j teslaMate report --month 2024-06
    """
    import json as _json
    from datetime import datetime

    if not month:
        month = datetime.now().strftime("%Y-%m")

    backend = _backend()
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
    ) as p:
        p.add_task(f"Loading report for {month}...", total=None)
        data = backend.get_monthly_report(month=month)

    if is_json_mode():
        console.print(_json.dumps(data, indent=2, default=str))
        return

    driving = data.get("driving") or {}
    charging = data.get("charging") or {}

    console.print()
    console.print(f"  [bold]Monthly Report \u2014 {month}[/bold]")
    console.print()

    # Driving section
    console.print(
        "  [bold cyan]\u2500\u2500 Driving \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500[/bold cyan]"
    )
    trips = driving.get("trips") or 0
    total_km = driving.get("total_km") or 0
    total_mi = round(float(total_km) * 0.621371, 1) if total_km else 0
    console.print(f"  Trips              : [bold]{trips}[/bold]")
    console.print(f"  Total distance     : [bold]{total_km} km[/bold] ({total_mi} mi)")
    console.print(f"  Avg per trip       : {driving.get('avg_km_per_trip') or '\u2014'} km")
    console.print(f"  Longest trip       : {driving.get('longest_trip_km') or '\u2014'} km")
    console.print(f"  Energy used        : {driving.get('total_kwh_used') or '\u2014'} kWh")
    console.print(f"  Avg efficiency     : {driving.get('avg_wh_per_km') or '\u2014'} Wh/km")
    console.print()

    # Charging section
    console.print(
        "  [bold cyan]\u2500\u2500 Charging \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500[/bold cyan]"
    )
    sessions = charging.get("sessions") or 0
    total_kwh = charging.get("total_kwh_charged") or 0
    total_cost = charging.get("total_cost")
    console.print(f"  Sessions           : [bold]{sessions}[/bold]")
    console.print(f"    DC fast (\u226550kW)  : {charging.get('dc_fast_sessions') or 0}")
    console.print(f"    AC (<50kW)       : {charging.get('ac_sessions') or 0}")
    console.print(f"  Total charged      : [bold]{total_kwh} kWh[/bold]")
    console.print(f"  Avg per session    : {charging.get('avg_kwh_per_session') or '\u2014'} kWh")
    if total_cost is not None and float(total_cost) > 0:
        console.print(f"  Total cost         : [bold]${total_cost}[/bold]")
    console.print()


@teslaMate_app.command("daily-chart")
def teslaMate_daily_chart(
    days: int = typer.Option(30, "--days", "-d", help="Number of past days to chart"),
) -> None:
    """ASCII bar chart of daily kWh added from TeslaMate (last N days).

    tesla teslaMate daily-chart
    tesla teslaMate daily-chart --days 60
    tesla -j teslaMate daily-chart
    """
    import json as _json
    import shutil

    backend = _backend()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as p:
        p.add_task(f"Fetching daily energy for last {days} days...", total=None)
        rows = backend.get_daily_energy(days=days)

    if is_json_mode():
        console.print_json(_json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        console.print(f"[yellow]No charging data found for the last {days} days.[/yellow]")
        return

    terminal_cols = shutil.get_terminal_size((80, 24)).columns
    BAR_MAX = max(10, min(terminal_cols - 26, 60))

    kwh_vals = [float(r.get("kwh_added") or 0) for r in rows]
    max_kwh = max(kwh_vals) if any(v > 0 for v in kwh_vals) else 1.0
    total_kwh = sum(kwh_vals)
    total_sessions = sum(int(r.get("sessions") or 0) for r in rows)

    console.print()
    console.print(f"  [bold cyan]Daily kWh Added — last {days} days[/bold cyan]")
    console.print(f"  [dim]Scale: full bar = {max_kwh:.1f} kWh[/dim]")
    console.print()

    for r in rows:
        day = str(r.get("day") or "")[:10]
        kwh = float(r.get("kwh_added") or 0)
        sess = int(r.get("sessions") or 0)

        bar_len = round((kwh / max_kwh) * BAR_MAX) if max_kwh > 0 else 0
        bar = "█" * bar_len

        bc = "green" if kwh >= 30 else "yellow" if kwh >= 10 else "red" if kwh > 0 else "dim"
        sess_str = f"[dim]({sess})[/dim]" if sess > 1 else ""
        console.print(f"  [dim]{day}[/dim]  [{bc}]{bar}[/{bc}] {kwh:.1f} kWh {sess_str}")

    console.print()
    console.print(
        f"  [dim]{len(rows)} days with charging │ {total_kwh:.1f} kWh total │ {total_sessions} sessions[/dim]"
    )


@teslaMate_app.command("graph")
def teslaMate_graph(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of recent sessions to chart"),
) -> None:
    """ASCII bar chart of recent charging sessions (kWh per session) from TeslaMate.

    tesla teslaMate graph
    tesla teslaMate graph --limit 30
    tesla -j teslaMate graph | jq '.[0].energy_added_kwh'
    """
    import json as _json
    import shutil

    backend = _backend()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as p:
        p.add_task(f"Fetching last {limit} charging sessions...", total=None)
        sessions = backend.get_charging_sessions(limit=limit)

    if is_json_mode():
        console.print_json(_json.dumps(sessions, indent=2, default=str))
        return

    if not sessions:
        console.print("[yellow]No charging sessions found in TeslaMate.[/yellow]")
        return

    terminal_cols = shutil.get_terminal_size((80, 24)).columns
    BAR_MAX_WIDTH = max(10, min(terminal_cols - 32, 60))

    kwh_values = [float(s.get("energy_added_kwh") or 0) for s in sessions]
    max_kwh = max(kwh_values) if any(v > 0 for v in kwh_values) else 1.0
    total_kwh = sum(kwh_values)
    total_cost = sum(float(s.get("cost") or 0) for s in sessions)

    console.print()
    console.print(f"  [bold cyan]Charging Sessions — last {len(sessions)}[/bold cyan]")
    console.print(f"  [dim]Scale: full bar = {max_kwh:.1f} kWh[/dim]")
    console.print()

    for s in sessions:
        kwh = float(s.get("energy_added_kwh") or 0)
        date = str(s.get("start_date") or "")[:10]
        loc = (s.get("location") or "Unknown")[:16]
        label = f"{date}  {loc:<16}"

        bar_len = round((kwh / max_kwh) * BAR_MAX_WIDTH) if max_kwh > 0 else 0
        bar = "█" * bar_len

        bc = "green" if kwh >= 30 else "yellow" if kwh >= 10 else "red"
        console.print(f"  [dim]{label}[/dim]  [{bc}]{bar}[/{bc}] {kwh:.1f} kWh")

    console.print()
    parts = [f"{len(sessions)} sessions", f"{total_kwh:.1f} kWh total"]
    if total_cost:
        parts.append(f"${total_cost:.2f} total cost")
    console.print(f"  [dim]{' │ '.join(parts)}[/dim]")


@teslaMate_app.command("stats")
def teslaMate_stats() -> None:
    """Show lifetime driving and charging statistics from TeslaMate.

    tesla teslaMate stats
    tesla -j teslaMate stats
    """
    import json as _json

    backend = _backend()
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
    ) as p:
        p.add_task("Loading lifetime stats...", total=None)
        drive_stats = backend.get_stats()
        charge_stats = backend.get_charging_stats()

    combined = {
        "drives": drive_stats,
        "charging": charge_stats,
    }

    if is_json_mode():
        console.print(_json.dumps(combined, indent=2, default=str))
        return

    console.print()
    console.print("  [bold]Lifetime Statistics[/bold]")
    console.print()

    # ── Driving ──
    console.print("  [bold cyan]── Driving ─────────────────────────────────────[/bold cyan]")
    total_drives = drive_stats.get("total_drives") or 0
    total_km = float(drive_stats.get("total_km") or 0)
    total_mi = round(total_km * 0.621371, 0)
    avg_km = drive_stats.get("avg_km_per_trip") or "—"
    longest_km = drive_stats.get("longest_trip_km") or "—"
    total_kwh = drive_stats.get("total_kwh") or "—"
    first_drive = str(drive_stats.get("first_drive") or "—")[:10]
    last_drive = str(drive_stats.get("last_drive") or "—")[:10]

    console.print(f"  Total drives       : [bold]{total_drives}[/bold]")
    console.print(f"  Total distance     : [bold]{total_km:,.0f} km[/bold] ({total_mi:,.0f} mi)")
    console.print(f"  Avg per trip       : {avg_km} km")
    console.print(f"  Longest trip       : {longest_km} km")
    console.print(f"  Energy used        : {total_kwh} kWh")
    console.print(f"  First drive        : {first_drive}")
    console.print(f"  Last drive         : {last_drive}")
    console.print()

    # ── Charging ──
    console.print("  [bold cyan]── Charging ────────────────────────────────────[/bold cyan]")
    sessions = charge_stats.get("total_sessions") or 0
    total_kwh_ch = charge_stats.get("total_kwh_added") or "—"
    total_cost = charge_stats.get("total_cost")
    avg_kwh = charge_stats.get("avg_kwh_per_session") or "—"
    last_session = str(charge_stats.get("last_session") or "—")[:10]

    console.print(f"  Total sessions     : [bold]{sessions}[/bold]")
    console.print(f"  Total kWh added    : [bold]{total_kwh_ch} kWh[/bold]")
    console.print(f"  Avg per session    : {avg_kwh} kWh")
    if total_cost is not None and float(total_cost or 0) > 0:
        console.print(f"  Total cost         : [bold]${total_cost}[/bold]")
    console.print(f"  Last session       : {last_session}")
    console.print()

    # ── Efficiency banner ──
    if total_km > 0 and total_kwh not in ("—", None, 0):
        try:
            wh_per_km = round(float(total_kwh) * 1000 / total_km, 1)
            console.print(f"  [bold]Lifetime avg efficiency: {wh_per_km} Wh/km[/bold]")
            console.print()
        except (ZeroDivisionError, TypeError, ValueError):
            pass


@teslaMate_app.command("heatmap")
def teslaMate_heatmap(
    days: int = typer.Option(365, "--days", "-d", help="Calendar window in days (default 365)"),
    year: int | None = typer.Option(
        None, "--year", "-y", help="Show a specific calendar year (e.g. 2025)"
    ),
) -> None:
    """GitHub-style driving heatmap — calendar grid of active driving days.

    \b
    tesla teslaMate heatmap
    tesla teslaMate heatmap --days 180
    tesla teslaMate heatmap --year 2025
    tesla -j teslaMate heatmap --year 2025
    """
    import datetime as _dt

    backend = _backend()
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
    ) as p:
        p.add_task("Loading drive history...", total=None)
        if year is not None:
            rows = backend.get_drive_days_year(year)
        else:
            rows = backend.get_drive_days(days=days)

    # Build lookup: date-string → km
    activity: dict[str, float] = {str(r["day"]): float(r["km"] or 0) for r in rows}

    if is_json_mode():
        console.print(
            json.dumps(
                [
                    {"date": str(r["day"]), "drives": r["drives"], "km": float(r["km"] or 0)}
                    for r in rows
                ],
                indent=2,
            )
        )
        return

    # ── Calendar grid ─────────────────────────────────────────────────────────
    if year is not None:
        start = _dt.date(year, 1, 1)
        today = min(_dt.date.today(), _dt.date(year, 12, 31))
    else:
        today = _dt.date.today()
        start = today - _dt.timedelta(days=days - 1)
    # Align to Monday of start week
    week_start = start - _dt.timedelta(days=start.weekday())

    # Collect all weeks
    weeks: list[list[_dt.date | None]] = []
    cur = week_start
    while cur <= today:
        week: list[_dt.date | None] = []
        for wd in range(7):
            d = cur + _dt.timedelta(days=wd)
            week.append(d if start <= d <= today else None)
        weeks.append(week)
        cur += _dt.timedelta(weeks=1)

    # Determine month labels (one per column where month changes)
    month_labels: list[str] = []
    prev_month = -1
    for week in weeks:
        # Find first real day in week
        first_real = next((d for d in week if d is not None), None)
        if first_real and first_real.month != prev_month:
            month_labels.append(first_real.strftime("%b"))
            prev_month = first_real.month
        else:
            month_labels.append("   ")

    # ── Legend / thresholds ───────────────────────────────────────────────────
    def _cell(d: _dt.date | None) -> str:
        if d is None:
            return "  "
        km = activity.get(str(d), 0.0)
        if km == 0:
            return "[dim]·[/dim] "
        elif km < 50:
            return "[blue]▪[/blue] "
        elif km < 150:
            return "[yellow]▪[/yellow] "
        else:
            return "[green]█[/green] "

    day_labels = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

    # Print month header row
    header = "    " + "".join(f"{lbl:<3}" for lbl in month_labels)
    console.print()
    console.print("  " + header)

    # Print 7 day-of-week rows
    for wd in range(7):
        cells = "".join(_cell(week[wd]) for week in weeks)
        console.print(f"  {day_labels[wd]}  {cells}")

    # Legend
    console.print()
    total_km = sum(activity.values())
    active_days = len(activity)
    console.print(
        "  [dim]Legend:[/dim]  [dim]·[/dim] no drive  "
        "[blue]▪[/blue] <50 km  [yellow]▪[/yellow] 50–150 km  [green]█[/green] 150+ km"
    )
    period_label = str(year) if year is not None else f"last {days} days"
    console.print(
        f"  [dim]{active_days} active days · {total_km:,.0f} km total · {period_label}[/dim]"
    )
    console.print()


@teslaMate_app.command("timeline")
def teslaMate_timeline(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to include"),
) -> None:
    """Unified event timeline: trips, charges, and OTA updates in chronological order.

    \b
    tesla teslaMate timeline
    tesla teslaMate timeline --days 7
    tesla -j teslaMate timeline | jq '.[].type'
    """
    backend = _backend()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task(f"Loading timeline for last {days} days…", total=None)
        events = backend.get_timeline(days=days)

    if is_json_mode():
        console.print_json(json.dumps(events, indent=2, default=str))
        return

    if not events:
        console.print("[yellow]No events found in the last {days} days.[/yellow]")
        return

    _TYPE_ICON = {"trip": "🚗", "charge": "⚡", "ota": "🔄"}
    _TYPE_COLOR = {"trip": "blue", "charge": "green", "ota": "yellow"}

    table = Table(
        title=f"Event Timeline — Last {days} Days (TeslaMate)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Date", width=17)
    table.add_column("Type", width=9)
    table.add_column("Value", justify="right", width=10)
    table.add_column("Detail", width=32)
    table.add_column("Duration", justify="right", width=10)

    for ev in events:
        ev_type = str(ev.get("type") or "")
        icon = _TYPE_ICON.get(ev_type, "•")
        color = _TYPE_COLOR.get(ev_type, "white")
        date = str(ev.get("start_date") or "")[:16]
        val = ev.get("value")
        detail = str(ev.get("detail") or "")[:30]

        # Format value
        if ev_type == "trip":
            val_str = f"{float(val):.1f} km" if val else "—"
        elif ev_type == "charge":
            val_str = f"+{float(val):.2f} kWh" if val else "—"
        else:
            val_str = "—"

        # Duration
        start = ev.get("start_date")
        end = ev.get("end_date")
        if start and end:
            try:
                import datetime as _dt

                if isinstance(start, str):
                    start = _dt.datetime.fromisoformat(start)
                if isinstance(end, str):
                    end = _dt.datetime.fromisoformat(end)
                delta = end - start
                mins = int(delta.total_seconds() / 60)
                dur_str = f"{mins}m" if mins < 60 else f"{mins // 60}h {mins % 60}m"
            except Exception:
                dur_str = "—"
        else:
            dur_str = "—"

        table.add_row(
            date,
            f"[{color}]{icon} {ev_type}[/{color}]",
            val_str,
            detail,
            dur_str,
        )

    console.print(table)
    counts = {t: sum(1 for e in events if e.get("type") == t) for t in ("trip", "charge", "ota")}
    console.print(
        f"\n  [dim]{counts['trip']} trips · {counts['charge']} charges · {counts['ota']} OTA updates[/dim]"
    )


@teslaMate_app.command("cost-report")
def teslaMate_cost_report(
    month: str | None = typer.Option(
        None, "--month", "-m", help="Filter to YYYY-MM (default: all available)"
    ),
    limit: int = typer.Option(100, "--limit", "-n", help="Max sessions to analyse"),
) -> None:
    """Charging cost report grouped by month, using TeslaMate sessions + cost_per_kwh config.

    \b
    tesla teslaMate cost-report
    tesla teslaMate cost-report --month 2026-03
    tesla -j teslaMate cost-report | jq '.months'
    """
    import collections

    cfg = load_config()
    cost_per_kwh = cfg.general.cost_per_kwh or 0.0
    backend = _backend()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task("Loading charging sessions…", total=None)
        sessions = backend.get_charging_sessions(limit=limit)

    # Optionally filter by month
    if month:
        sessions = [s for s in sessions if str(s.get("start_date") or "").startswith(month)]

    if is_json_mode():
        # Build per-month summary
        by_month: dict[str, dict] = collections.defaultdict(
            lambda: {"sessions": 0, "kwh": 0.0, "cost": 0.0}
        )
        for s in sessions:
            ym = str(s.get("start_date") or "")[:7]
            kwh = float(s.get("energy_added_kwh") or 0)
            by_month[ym]["sessions"] += 1
            by_month[ym]["kwh"] += kwh
            by_month[ym]["cost"] += kwh * cost_per_kwh
        # Round
        for v in by_month.values():
            v["kwh"] = round(v["kwh"], 2)
            v["cost"] = round(v["cost"], 2)
        console.print_json(
            json.dumps(
                {
                    "cost_per_kwh": cost_per_kwh,
                    "months": dict(sorted(by_month.items(), reverse=True)),
                    "sessions": len(sessions),
                },
                indent=2,
                default=str,
            )
        )
        return

    if not sessions:
        console.print("[yellow]No charging sessions found.[/yellow]")
        return

    # Group by month
    by_month_list: dict[str, list] = collections.defaultdict(list)
    for s in sessions:
        ym = str(s.get("start_date") or "")[:7]
        by_month_list[ym].append(s)

    total_kwh = 0.0
    total_cost = 0.0
    total_sessions = 0

    for ym in sorted(by_month_list.keys(), reverse=True):
        sess_list = by_month_list[ym]
        m_kwh = sum(float(s.get("energy_added_kwh") or 0) for s in sess_list)
        m_cost = m_kwh * cost_per_kwh
        total_kwh += m_kwh
        total_cost += m_cost
        total_sessions += len(sess_list)

        t = Table(
            title=f"[bold]{ym}[/bold]  {len(sess_list)} sessions · {m_kwh:.1f} kWh · ${m_cost:.2f}",
            show_header=True,
            header_style="bold cyan",
        )
        t.add_column("Date", width=17)
        t.add_column("Location", width=22)
        t.add_column("SoC %", width=12)
        t.add_column("kWh", justify="right", width=8)
        t.add_column("Cost", justify="right", width=9)

        for s in sess_list:
            date = str(s.get("start_date") or "")[:16]
            loc = str(s.get("location") or "—")[:20]
            soc = f"{s.get('start_battery_level') or '?'}→{s.get('end_battery_level') or '?'}"
            kwh = float(s.get("energy_added_kwh") or 0)
            cost = kwh * cost_per_kwh
            t.add_row(date, loc, soc, f"{kwh:.2f}", f"${cost:.2f}")

        console.print(t)

    rate_note = (
        f" (@ ${cost_per_kwh:.3f}/kWh)"
        if cost_per_kwh
        else " [dim](set cost_per_kwh in config for cost estimates)[/dim]"
    )
    console.print(
        f"\n  [bold]Total:[/bold] {total_sessions} sessions · {total_kwh:.1f} kWh · [green]${total_cost:.2f}[/green]{rate_note}"
    )


@teslaMate_app.command("trip-stats")
def teslaMate_trip_stats(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyse"),
) -> None:
    """Aggregate trip statistics: totals, averages, and top routes.

    \b
    tesla teslaMate trip-stats
    tesla teslaMate trip-stats --days 90
    tesla -j teslaMate trip-stats
    """
    backend = _backend()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task(f"Loading trip stats for last {days} days…", total=None)
        result = backend.get_trip_stats(days=days)

    if is_json_mode():
        console.print_json(json.dumps(result, indent=2, default=str))
        return

    s = result.get("summary") or {}
    routes = result.get("top_routes") or []

    if not s.get("total_trips"):
        console.print("[yellow]No trip data found in the last {days} days.[/yellow]")
        return

    from rich.table import Table as _Table

    # Summary table
    st = _Table(
        title=f"Trip Statistics — Last {days} Days", show_header=False, box=None, padding=(0, 2)
    )
    st.add_column("k", style="dim", width=22)
    st.add_column("v")
    st.add_row("Total trips", str(s.get("total_trips") or "—"))
    st.add_row("Total distance", f"{s.get('total_km') or 0:.1f} km")
    st.add_row("Avg per trip", f"{s.get('avg_km') or 0:.1f} km")
    st.add_row("Longest trip", f"{s.get('longest_km') or 0:.1f} km")
    st.add_row("Shortest trip", f"{s.get('shortest_km') or 0:.1f} km")
    st.add_row("Avg duration", f"{int(s.get('avg_duration_min') or 0)} min")
    console.print(st)

    if routes:
        rt = _Table(title="Top Routes", show_header=True, header_style="bold cyan")
        rt.add_column("From", width=25)
        rt.add_column("To", width=25)
        rt.add_column("Trips", justify="right", width=7)
        for r in routes:
            rt.add_row(
                str(r.get("from_addr") or "—")[:23],
                str(r.get("to_addr") or "—")[:23],
                str(r.get("count") or 0),
            )
        console.print(rt)


@teslaMate_app.command("charging-locations")
def teslaMate_charging_locations(
    days: int = typer.Option(90, "--days", "-d", help="Look-back window in days"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max locations to show"),
) -> None:
    """Top charging locations ranked by session count.

    \b
    tesla teslaMate charging-locations
    tesla teslaMate charging-locations --days 365 --limit 20
    tesla -j teslaMate charging-locations
    """
    backend = _backend()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task(f"Loading charging locations for last {days} days…", total=None)
        rows = backend.get_charging_locations(days=days, limit=limit)

    if is_json_mode():
        console.print_json(json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        console.print(f"[yellow]No charging sessions found in the last {days} days.[/yellow]")
        return

    from rich.table import Table as _Table

    t = _Table(
        title=f"Top Charging Locations — Last {days} Days",
        show_header=True,
        header_style="bold cyan",
    )
    t.add_column("#", width=4, style="dim")
    t.add_column("Location", width=28)
    t.add_column("Sessions", justify="right", width=10)
    t.add_column("Total kWh", justify="right", width=11)
    t.add_column("Avg kWh", justify="right", width=10)
    t.add_column("Last Visit", width=17)

    total_sessions = 0
    total_kwh = 0.0
    for i, r in enumerate(rows, 1):
        loc = str(r.get("location") or "—")[:26]
        sess = int(r.get("sessions") or 0)
        tkwh = float(r.get("total_kwh") or 0)
        akwh = float(r.get("avg_kwh_per_session") or 0)
        last = str(r.get("last_visit") or "—")[:16]
        total_sessions += sess
        total_kwh += tkwh
        t.add_row(str(i), loc, str(sess), f"{tkwh:.1f}", f"{akwh:.1f}", last)

    console.print(t)
    console.print(
        f"\n  [dim]{len(rows)} locations · {total_sessions} sessions · {total_kwh:.1f} kWh total[/dim]"
    )


# ── Grafana ──────────────────────────────────────────────────────────────────

_GRAFANA_DASHBOARDS: dict[str, str] = {
    "overview": "/d/overview/overview",
    "trips": "/d/ZihFSXoZk/trips",
    "charges": "/d/7Cp9k_7Zz/charges",
    "battery": "/d/pf6xQMd7k/battery",
    "efficiency": "/d/5k7CaGFZz/efficiency",
    "locations": "/d/GhFG_aS7k/locations",
    "vampire": "/d/g_EIOX5Zz/vampire-drain",
    "updates": "/d/f4V4XRhZz/updates",
}

_GRAFANA_NAMES = ", ".join(_GRAFANA_DASHBOARDS.keys())


@teslaMate_app.command("grafana")
def teslaMate_grafana(
    dashboard: str = typer.Argument("overview", help=f"Dashboard: {_GRAFANA_NAMES}"),
) -> None:
    """Open a TeslaMate Grafana dashboard in your browser.

    tesla teslaMate grafana
    tesla teslaMate grafana trips
    tesla teslaMate grafana charges
    tesla -j teslaMate grafana battery
    """
    import json as _json
    import webbrowser

    cfg = load_config()
    base = (cfg.grafana.url or "http://localhost:3000").rstrip("/")

    key = dashboard.lower()
    if key not in _GRAFANA_DASHBOARDS:
        console.print(
            f"[red]Unknown dashboard:[/red] {dashboard}\n[dim]Available:[/dim] {_GRAFANA_NAMES}"
        )
        raise typer.Exit(1)

    url = base + _GRAFANA_DASHBOARDS[key]

    if is_json_mode():
        console.print(_json.dumps({"dashboard": key, "url": url}))
        return

    console.print(f"Opening [bold cyan]{key}[/bold cyan] dashboard…  [dim]{url}[/dim]")
    webbrowser.open(url)


@teslaMate_app.command("energy-report")
def teslaMate_energy_report(
    months: int = typer.Option(
        6, "--months", "-m", min=1, max=24, help="Number of months to summarise"
    ),
) -> None:
    """Monthly energy usage summary from TeslaMate.

    tesla teslaMate energy-report
    tesla teslaMate energy-report --months 12
    tesla -j teslaMate energy-report | jq '.[0].kwh'
    """
    import json as _json
    from collections import defaultdict

    backend = _backend()
    days = months * 31
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as p:
        p.add_task(f"Fetching energy data for last {months} months…", total=None)
        daily = backend.get_daily_energy(days=days)

    # Aggregate by YYYY-MM
    by_month: dict[str, dict] = defaultdict(lambda: {"kwh": 0.0, "km": 0.0, "days": 0})
    for row in daily:
        ym = str(row.get("date") or "")[:7]
        kwh = float(row.get("kwh") or 0)
        km = float(row.get("km") or row.get("distance") or 0)
        if ym:
            by_month[ym]["kwh"] = round(by_month[ym]["kwh"] + kwh, 3)
            by_month[ym]["km"] = round(by_month[ym]["km"] + km, 1)
            by_month[ym]["days"] += 1

    rows = [
        {
            "month": ym,
            "kwh": d["kwh"],
            "km": d["km"],
            "wh_per_km": round(d["kwh"] * 1000 / d["km"], 1) if d["km"] > 0 else None,
        }
        for ym, d in sorted(by_month.items(), reverse=True)
    ]

    if is_json_mode():
        console.print(_json.dumps(rows, indent=2))
        return

    if not rows:
        console.print("[yellow]No energy data found in TeslaMate.[/yellow]")
        return

    table = Table(title=f"Energy Report — last {months} months", border_style="green")
    table.add_column("Month", style="bold cyan", width=10)
    table.add_column("kWh", justify="right")
    table.add_column("km", justify="right")
    table.add_column("Wh/km", justify="right")

    for r in rows:
        wh_str = f"{r['wh_per_km']:.1f}" if r["wh_per_km"] is not None else "—"
        table.add_row(
            r["month"],
            f"{r['kwh']:.1f}",
            f"{r['km']:.0f}",
            wh_str,
        )

    total_kwh = sum(r["kwh"] for r in rows)
    total_km = sum(r["km"] for r in rows)
    avg_wh = round(total_kwh * 1000 / total_km, 1) if total_km > 0 else 0
    table.add_section()
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_kwh:.1f}[/bold]",
        f"[bold]{total_km:.0f}[/bold]",
        f"[bold]{avg_wh:.1f}[/bold]",
    )

    console.print(table)


# ── managed stack lifecycle ──


@teslaMate_app.command("sync-tokens")
def teslaMate_sync_tokens() -> None:
    """Sync Tesla API tokens from keyring to TeslaMate.

    Injects the current Fleet API tokens into TeslaMate's database so it can
    start collecting vehicle data without manual sign-in.

    tesla teslaMate sync-tokens
    """
    cfg = load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is not managed by CLI.[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
    if not stack.is_running():
        console.print(
            "[yellow]TeslaMate stack is not running.[/yellow] Start with: tesla teslaMate start"
        )
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Syncing tokens...", total=None)
        ok = stack.sync_tokens_from_keyring()

    if ok:
        render_success("Tokens synced to TeslaMate. It should start collecting data shortly.")
    else:
        console.print(
            "[red]Token sync failed.[/red] Make sure you have valid Fleet API tokens (tesla config auth fleet)."
        )
        raise typer.Exit(1)


@teslaMate_app.command("install")
def teslaMate_install(
    postgres_port: int = typer.Option(5432, "--postgres-port", help="PostgreSQL port"),
    grafana_port: int = typer.Option(3000, "--grafana-port", help="Grafana port"),
    teslamate_port: int = typer.Option(4000, "--teslamate-port", help="TeslaMate web UI port"),
    mqtt_port: int = typer.Option(1883, "--mqtt-port", help="Mosquitto MQTT port"),
    timezone: str = typer.Option("America/Bogota", "--tz", help="Timezone for TeslaMate"),
    force: bool = typer.Option(False, "--force", help="Reinstall even if already installed"),
) -> None:
    """Install and start a fully managed TeslaMate stack (Docker Compose).

    Sets up PostgreSQL, TeslaMate, Grafana, and Mosquitto. Credentials are
    generated automatically and stored in the system keyring.

    tesla teslaMate install
    tesla teslaMate install --grafana-port 3001 --tz America/New_York
    """
    from tesla_cli.core.exceptions import DockerNotFoundError, TeslaMateStackError
    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        task = p.add_task("Checking Docker...", total=None)

        # Port conflict check
        conflicts = stack.check_ports(postgres_port, grafana_port, teslamate_port, mqtt_port)
        if conflicts:
            names = ", ".join(f"{n} (:{p})" for n, p in conflicts)
            console.print(f"[red]Port conflict:[/red] {names} already in use.")
            console.print(
                "[dim]Use --postgres-port, --grafana-port, etc. to pick different ports.[/dim]"
            )
            raise typer.Exit(1)

        p.update(task, description="Installing TeslaMate stack...")
        try:
            result = stack.install(
                postgres_port=postgres_port,
                grafana_port=grafana_port,
                teslamate_port=teslamate_port,
                mqtt_port=mqtt_port,
                timezone=timezone,
                force=force,
            )
        except (DockerNotFoundError, TeslaMateStackError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    # Auto-configure tesla-cli
    cfg = load_config()
    cfg.teslaMate.database_url = result["database_url"]
    cfg.teslaMate.managed = True
    cfg.teslaMate.stack_dir = result["stack_dir"]
    cfg.teslaMate.postgres_port = result["postgres_port"]
    cfg.teslaMate.grafana_port = result["grafana_port"]
    cfg.teslaMate.teslamate_port = result["teslamate_port"]
    cfg.teslaMate.mqtt_port = result["mqtt_port"]
    cfg.grafana.url = f"http://localhost:{result['grafana_port']}"
    cfg.mqtt.broker = "localhost"
    cfg.mqtt.port = result["mqtt_port"]
    save_config(cfg)

    health_icon = "[green]healthy[/green]" if result["healthy"] else "[yellow]starting...[/yellow]"
    render_success("TeslaMate stack installed and running")
    console.print(f"\n  Stack health: {health_icon}")
    console.print(f"  TeslaMate UI: [link]http://localhost:{teslamate_port}[/link]")
    console.print(
        f"  Grafana:      [link]http://localhost:{grafana_port}[/link]  (admin / {result['grafana_password']})"
    )
    console.print(f"  PostgreSQL:   localhost:{postgres_port}")
    console.print(f"  MQTT:         localhost:{mqtt_port}")

    # Auto-sync tokens from keyring → TeslaMate
    import time as _t

    _t.sleep(5)  # Wait for TeslaMate to be ready
    if stack.sync_tokens_from_keyring():
        console.print("\n  [green]Tesla tokens synced automatically.[/green]")
    elif not result["has_tesla_tokens"]:
        console.print("\n[yellow]No Tesla tokens found.[/yellow] Run: tesla config auth fleet")
    console.print()


@teslaMate_app.command("start")
def teslaMate_start() -> None:
    """Start the managed TeslaMate stack.

    tesla teslaMate start
    """
    cfg = load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        console.print("Run [bold]tesla teslaMate install[/bold] to set up a managed stack.")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.core.exceptions import TeslaMateStackError
    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Starting TeslaMate stack...", total=None)
        try:
            stack.start()
        except TeslaMateStackError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    render_success("TeslaMate stack started")

    # Auto-sync tokens
    import time as _t

    _t.sleep(5)
    if stack.sync_tokens_from_keyring():
        console.print("  [green]Tokens synced.[/green]")


@teslaMate_app.command("stop")
def teslaMate_stop() -> None:
    """Stop the managed TeslaMate stack.

    tesla teslaMate stop
    """
    cfg = load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
    stack.stop()
    render_success("TeslaMate stack stopped")


@teslaMate_app.command("restart")
def teslaMate_restart() -> None:
    """Restart the managed TeslaMate stack.

    tesla teslaMate restart
    """
    cfg = load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.core.exceptions import TeslaMateStackError
    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Restarting TeslaMate stack...", total=None)
        try:
            stack.restart()
        except TeslaMateStackError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    render_success("TeslaMate stack restarted")


@teslaMate_app.command("update")
def teslaMate_update() -> None:
    """Pull latest Docker images and recreate containers.

    tesla teslaMate update
    """
    cfg = load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Pulling latest images & restarting...", total=None)
        output = stack.update()

    render_success("TeslaMate stack updated")
    if output:
        for line in output.strip().splitlines()[-5:]:
            console.print(f"  [dim]{line}[/dim]")


@teslaMate_app.command("logs")
def teslaMate_logs(
    service: str | None = typer.Option(
        None, "--service", "-s", help="Service: teslamate, postgres, grafana, mosquitto"
    ),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of log lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """Show logs from the managed TeslaMate stack.

    tesla teslaMate logs
    tesla teslaMate logs --service teslamate --lines 50
    tesla teslaMate logs -f
    """
    cfg = load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    from pathlib import Path

    from tesla_cli.core.exceptions import TeslaMateStackError
    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)

    try:
        result = stack.logs(service=service, lines=lines, follow=follow)
        if follow:
            # Streaming mode — forward output until Ctrl+C
            try:
                for line in result.stdout:  # type: ignore[union-attr]
                    console.print(line, end="", highlight=False)
            except KeyboardInterrupt:
                result.terminate()  # type: ignore[union-attr]
        else:
            if result.stdout:  # type: ignore[union-attr]
                console.print(result.stdout, highlight=False)  # type: ignore[union-attr]
    except TeslaMateStackError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


@teslaMate_app.command("uninstall")
def teslaMate_uninstall(
    remove_data: bool = typer.Option(
        False, "--remove-data", help="Also remove database volumes (destructive)"
    ),
) -> None:
    """Stop and remove managed TeslaMate containers.

    tesla teslaMate uninstall
    tesla teslaMate uninstall --remove-data
    """
    cfg = load_config()
    if not cfg.teslaMate.managed:
        console.print("[yellow]TeslaMate is configured as external (not managed by CLI).[/yellow]")
        raise typer.Exit(1)

    if remove_data:
        console.print(
            "[red]WARNING: This will permanently delete all TeslaMate data (trips, charging history, etc.)[/red]"
        )
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            raise typer.Abort()

    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
    stack.uninstall(remove_volumes=remove_data)

    cfg.teslaMate.managed = False
    cfg.teslaMate.database_url = ""
    cfg.teslaMate.stack_dir = ""
    save_config(cfg)

    render_success(
        "TeslaMate stack removed"
        + (" (data deleted)" if remove_data else " (data volumes preserved)")
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


@teslaMate_app.command("battery-degradation")
def teslaMate_battery_degradation(
    months: int = typer.Option(12, "--months", "-m", help="Months of data to analyze"),
) -> None:
    """Battery degradation trend from TeslaMate charging data.

    Analyzes high-SoC charges (>=95%) to track max rated range over time.
    Shows monthly trend and overall degradation percentage.

    tesla teslaMate battery-degradation
    tesla teslaMate battery-degradation --months 24
    tesla -j teslaMate battery-degradation
    """
    import json as _json

    from rich.table import Table

    backend = _backend()
    data = backend.get_battery_degradation(months=months)

    if is_json_mode():
        console.print_json(_json.dumps(data))
        return

    if data["data_points"] == 0:
        console.print("[yellow]No high-SoC charges (>=95%) found in the last "
                      f"{months} months.[/yellow]")
        console.print("[dim]Tip: charge to 100% occasionally to get degradation data.[/dim]")
        raise typer.Exit(1)

    t = Table(title=f"Battery Degradation — {data['first_month']} to {data['last_month']}")
    t.add_column("Month", style="cyan")
    t.add_column("Max Range (km)", justify="right", style="green")
    t.add_column("Max SoC", justify="right")
    t.add_column("Sessions", justify="right", style="dim")

    for m in data["monthly"]:
        t.add_row(m["month"], f"{m['max_range_km']:.1f}", f"{m['max_soc']}%", str(m["sessions"]))

    console.print(t)

    color = "green" if data["degradation_pct"] < 3 else "yellow" if data["degradation_pct"] < 8 else "red"
    console.print(
        f"\n  [{color}]Degradation: {data['degradation_pct']}%[/{color}]"
        f"  ({data['first_range_km']} km → {data['last_range_km']} km)"
    )
