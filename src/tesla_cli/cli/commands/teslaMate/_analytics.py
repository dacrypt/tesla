"""``teslaMate`` commands — analytics (see ``__init__.py``).

Names tests patch on ``tesla_cli.cli.commands.teslaMate`` are looked up as ``_m.<name>``.
"""

from __future__ import annotations

from tesla_cli.cli.commands import teslaMate as _m
from tesla_cli.cli.commands.teslaMate import (  # noqa: F401
    Progress,
    SpinnerColumn,
    Table,
    TextColumn,
    console,
    is_json_mode,
    json,
    teslaMate_app,
    typer,
)


def _build_gpx(drive_id: int, positions: list[dict]) -> str:
    """Build GPX XML string from a list of position dicts."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="tesla-cli" xmlns="http://www.topografix.com/GPX/1/1">',
        "  <trk>",
        f"    <name>Drive {drive_id}</name>",
        "    <trkseg>",
    ]
    for pt in positions:
        lat = pt.get("latitude", 0)
        lon = pt.get("longitude", 0)
        ele = pt.get("elevation")
        speed = pt.get("speed")
        ts = pt.get("timestamp")
        ts_str = str(ts).replace(" ", "T") if ts else ""
        if not ts_str.endswith("Z") and ts_str:
            ts_str += "Z"
        lines.append(f'      <trkpt lat="{lat}" lon="{lon}">')
        if ele is not None:
            lines.append(f"        <ele>{ele}</ele>")
        if ts_str:
            lines.append(f"        <time>{ts_str}</time>")
        if speed is not None:
            lines.append(f"        <speed>{speed}</speed>")
        lines.append("      </trkpt>")
    lines += ["    </trkseg>", "  </trk>", "</gpx>"]
    return "\n".join(lines)


def _build_geojson(drive_id: int, positions: list[dict]) -> str:
    """Build GeoJSON Feature string from a list of position dicts."""
    coordinates = []
    for pt in positions:
        lat = pt.get("latitude", 0)
        lon = pt.get("longitude", 0)
        ele = pt.get("elevation")
        if ele is not None:
            coordinates.append([lon, lat, ele])
        else:
            coordinates.append([lon, lat])

    feature = {
        "type": "Feature",
        "properties": {"drive_id": drive_id, "points": len(positions)},
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates,
        },
    }
    return json.dumps(feature, indent=2)


@teslaMate_app.command("charging")
def teslaMate_charging(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of sessions to show"),
    csv_out: str | None = typer.Option(None, "--csv", help="Save output to CSV file"),
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
) -> None:
    """Show recent charging session history from TeslaMate.

    tesla teslaMate charging
    tesla teslaMate charging --limit 50
    tesla -j teslaMate charging | jq '.[] | select(.cost != null)'
    """
    backend = _m._backend()

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode() or oneline,
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

    if oneline:
        total_kwh = sum(float(s.get("energy_added_kwh") or 0) for s in sessions)
        total_cost = sum(float(s.get("cost") or 0) for s in sessions)
        parts = [
            f"⚡ {len(sessions)} sessions",
            f"🔋 {total_kwh:.1f} kWh",
            f"💰 ${total_cost:.2f}",
        ]
        console.print(" | ".join(parts))
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
    backend = _m._backend()

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

    backend = _m._backend()
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

    backend = _m._backend()
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

    backend = _m._backend()
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

    backend = _m._backend()
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


@teslaMate_app.command("cost-report")
def teslaMate_cost_report(
    month: str | None = typer.Option(
        None, "--month", "-m", help="Filter to YYYY-MM (default: all available)"
    ),
    limit: int = typer.Option(100, "--limit", "-n", help="Max sessions to analyse"),
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
) -> None:
    """Charging cost report grouped by month, using TeslaMate sessions + cost_per_kwh config.

    \b
    tesla teslaMate cost-report
    tesla teslaMate cost-report --month 2026-03
    tesla -j teslaMate cost-report | jq '.months'
    """
    import collections

    cfg = _m.load_config()
    cost_per_kwh = cfg.general.cost_per_kwh or 0.0
    backend = _m._backend()

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode() or oneline,
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

    if oneline:
        total_kwh = sum(float(s.get("energy_added_kwh") or 0) for s in sessions)
        total_cost = total_kwh * cost_per_kwh
        rate_per_kwh = cost_per_kwh * 100  # convert $/kWh → ¢/kWh
        parts = [
            f"💰 ${total_cost:.2f} total",
            f"⚡ {total_kwh:.1f} kWh",
            f"📊 {rate_per_kwh:.1f} ¢/kWh",
        ]
        console.print(" | ".join(parts))
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
    backend = _m._backend()

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

    backend = _m._backend()
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
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
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

    backend = _m._backend()

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode() or oneline,
    ) as p:
        p.add_task(f"Analyzing battery degradation over {months} months...", total=None)
        data = backend.get_battery_degradation(months=months)

    if is_json_mode():
        console.print_json(_json.dumps(data))
        return

    if data["data_points"] == 0:
        console.print(
            f"[yellow]No high-SoC charges (>=95%) found in the last {months} months.[/yellow]"
        )
        console.print("[dim]Tip: charge to 100% occasionally to get degradation data.[/dim]")
        raise typer.Exit(1)

    if oneline:
        health_pct = round(100 - data["degradation_pct"], 1)
        deg_per_year = round(data["degradation_pct"] / max(months / 12, 1), 1)
        last_range = data.get("last_range_km", 0)
        parts = [
            f"🔋 {health_pct}% health",
            f"📉 {deg_per_year}%/year",
            f"📏 {last_range} km range",
        ]
        console.print(" | ".join(parts))
        return

    t = Table(title=f"Battery Degradation — {data['first_month']} to {data['last_month']}")
    t.add_column("Month", style="cyan")
    t.add_column("Max Range (km)", justify="right", style="green")
    t.add_column("Max SoC", justify="right")
    t.add_column("Sessions", justify="right", style="dim")

    for m in data["monthly"]:
        t.add_row(m["month"], f"{m['max_range_km']:.1f}", f"{m['max_soc']}%", str(m["sessions"]))

    console.print(t)

    color = (
        "green"
        if data["degradation_pct"] < 3
        else "yellow"
        if data["degradation_pct"] < 8
        else "red"
    )
    console.print(
        f"\n  [{color}]Degradation: {data['degradation_pct']}%[/{color}]"
        f"  ({data['first_range_km']} km → {data['last_range_km']} km)"
    )


@teslaMate_app.command("monthly-cost")
def teslaMate_monthly_cost(
    months: int = typer.Option(6, "--months", "-m", help="Number of months to show"),
) -> None:
    """Monthly charging cost trend — compare this month vs previous months.

    tesla teslaMate monthly-cost
    tesla teslaMate monthly-cost --months 12
    tesla -j teslaMate monthly-cost
    """
    import json as _json

    from rich.table import Table

    backend = _m._backend()
    data = backend.get_cost_report(limit=months)

    if is_json_mode():
        console.print_json(_json.dumps(data, default=str))
        return

    if not data:
        console.print("[yellow]No charging cost data available.[/yellow]")
        raise typer.Exit(1)

    t = Table(title=f"Monthly Charging Cost (last {months} months)")
    t.add_column("Month", style="cyan")
    t.add_column("kWh", justify="right", style="green")
    t.add_column("Cost", justify="right")
    t.add_column("Sessions", justify="right", style="dim")
    t.add_column("Trend", justify="center")

    prev_cost = None
    for m in data:
        kwh = m.get("total_kwh") or m.get("kwh_added") or 0
        cost = m.get("total_cost") or m.get("cost") or 0
        sessions = m.get("session_count") or m.get("sessions") or 0
        month_str = m.get("month", "?")

        trend = ""
        if prev_cost is not None and prev_cost > 0 and cost > 0:
            change = ((cost - prev_cost) / prev_cost) * 100
            if change > 5:
                trend = f"[red]+{change:.0f}%[/red]"
            elif change < -5:
                trend = f"[green]{change:.0f}%[/green]"
            else:
                trend = "[dim]~[/dim]"

        t.add_row(
            str(month_str),
            f"{float(kwh):.1f}",
            f"${float(cost):.2f}" if cost else "—",
            str(sessions),
            trend,
        )
        prev_cost = float(cost) if cost else None

    console.print(t)
