"""``teslaMate`` commands — trips (see ``__init__.py``).

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
    render_table,
    teslaMate_app,
    typer,
)
from tesla_cli.cli.commands.teslaMate._analytics import (  # noqa: F401
    _build_geojson,
    _build_gpx,
)


@teslaMate_app.command("trips")
def teslaMate_trips(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of trips to show"),
    csv_out: str | None = typer.Option(None, "--csv", help="Save output to CSV file"),
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
) -> None:
    """Show recent trip history from TeslaMate.

    tesla teslaMate trips
    tesla teslaMate trips --limit 50
    tesla -j teslaMate trips | jq '.[0]'
    """
    backend = _m._backend()

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode() or oneline,
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

    if oneline:
        total_km = sum(float(t.get("distance_km") or 0) for t in trips)
        total_kwh = sum(float(t.get("energy_kwh") or 0) for t in trips)
        total_min = sum(int(t.get("duration_min") or 0) for t in trips)
        wh_km = round(total_kwh * 1000 / total_km, 0) if total_km else 0
        h, m = divmod(total_min, 60)
        parts = [
            f"🚗 {len(trips)} trips",
            f"📏 {total_km:.0f} km",
            f"⏱ {h}h {m}m",
            f"⚡ {wh_km:.0f} Wh/km",
        ]
        console.print(" | ".join(parts))
        return

    if not trips:
        console.print("[yellow]No trips found in TeslaMate.[/yellow]")
        return

    table = Table(
        title=f"Last {len(trips)} Trips (TeslaMate)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="dim", width=6)
    table.add_column("Date", width=17)
    table.add_column("From", width=22)
    table.add_column("To", width=22)
    table.add_column("km", justify="right", width=7)
    table.add_column("min", justify="right", width=5)
    table.add_column("kWh", justify="right", width=7)
    table.add_column("🔋 start→end", width=12)

    for t in trips:
        drive_id = str(t.get("id") or "-")
        date = str(t.get("start_date") or "")[:16]
        frm = (t.get("start_address") or "")[:21]
        to = (t.get("end_address") or "")[:21]
        km = str(t.get("distance_km") or "-")
        mins = str(t.get("duration_min") or "-")
        kwh = str(t.get("energy_kwh") or "-")
        s_batt = t.get("start_battery_level")
        e_batt = t.get("end_battery_level")
        batt = f"{s_batt}% → {e_batt}%" if s_batt is not None else "-"
        table.add_row(drive_id, date, frm, to, km, mins, kwh, batt)

    console.print(table)

    # Summary line
    total_km = sum(float(t.get("distance_km") or 0) for t in trips)
    total_kwh = sum(float(t.get("energy_kwh") or 0) for t in trips)
    console.print(
        f"\n  [dim]Showing {len(trips)} trips │ {total_km:.0f} km │ {total_kwh:.1f} kWh[/dim]"
    )


@teslaMate_app.command("drive-path")
def teslaMate_drive_path(
    drive_id: int = typer.Argument(
        ..., help="Drive ID from TeslaMate (see: tesla teslaMate trips)"
    ),
    fmt: str = typer.Option("gpx", "--format", "-f", help="Export format: gpx or geojson"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Export GPS trace of a drive as GPX or GeoJSON.

    tesla teslaMate drive-path 42
    tesla teslaMate drive-path 42 --format geojson
    tesla teslaMate drive-path 42 --output drive_42.gpx
    tesla -j teslaMate drive-path 42
    """
    backend = _m._backend()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task(f"Fetching GPS positions for drive {drive_id}...", total=None)
        positions = backend.get_drive_path(drive_id)

    if not positions:
        console.print(f"[yellow]No GPS positions found for drive {drive_id}.[/yellow]")
        raise typer.Exit(1)

    # --json mode: raw position data
    if is_json_mode():
        console.print_json(json.dumps(positions, indent=2, default=str))
        return

    fmt = fmt.lower()
    if fmt not in ("gpx", "geojson"):
        console.print(f"[red]Unknown format '{fmt}'. Use 'gpx' or 'geojson'.[/red]")
        raise typer.Exit(1)

    if fmt == "gpx":
        content = _build_gpx(drive_id, positions)
    else:
        content = _build_geojson(drive_id, positions)

    if output:
        import pathlib

        pathlib.Path(output).write_text(content, encoding="utf-8")
        console.print(
            f"  [green]\u2713[/green] Saved {len(positions)} points to [bold]{output}[/bold]"
        )
    else:
        console.print(content)


@teslaMate_app.command("efficiency")
def teslaMate_efficiency(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of trips to analyze"),
    csv_out: str | None = typer.Option(None, "--csv", help="Save output to CSV file"),
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
) -> None:
    """Show per-trip energy efficiency from TeslaMate.

    tesla teslaMate efficiency
    tesla teslaMate efficiency --limit 50
    tesla -j teslaMate efficiency | jq '[.[] | .wh_per_km] | add / length'
    """
    backend = _m._backend()

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode() or oneline,
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

    if oneline:
        wh_vals = [float(t.get("wh_per_km") or 0) for t in trips if t.get("wh_per_km")]
        avg_wh = round(sum(wh_vals) / len(wh_vals), 0) if wh_vals else 0
        best_wh = round(min(wh_vals), 0) if wh_vals else 0
        worst_wh = round(max(wh_vals), 0) if wh_vals else 0
        parts = [
            f"⚡ {avg_wh:.0f} Wh/km avg",
            f"🏆 best {best_wh:.0f}",
            f"📉 worst {worst_wh:.0f}",
        ]
        console.print(" | ".join(parts))
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
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
) -> None:
    """Show vampire drain (battery loss while parked) from TeslaMate.

    tesla teslaMate vampire
    tesla teslaMate vampire --days 90
    tesla -j teslaMate vampire | jq '.avg_pct_per_hour'
    """
    backend = _m._backend()

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode() or oneline,
    ) as p:
        p.add_task(f"Analyzing vampire drain over {days} days...", total=None)
        result = backend.get_vampire_drain(days=days)

    if is_json_mode():
        console.print_json(json.dumps(result, indent=2, default=str))
        return

    daily = result.get("daily", [])
    avg_per_hour = result.get("avg_pct_per_hour")

    if oneline:
        daily_equiv = round(float(avg_per_hour) * 24, 1) if avg_per_hour is not None else 0
        sample_count = sum(int(r.get("periods") or 0) for r in daily)
        parts = [
            f"🧛 {daily_equiv}%/day avg",
            f"📊 {sample_count} samples",
        ]
        console.print(" | ".join(parts))
        return

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

    backend = _m._backend()
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

    backend = _m._backend()
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
    backend = _m._backend()

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
    backend = _m._backend()

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
