"""Order tracking commands: tesla order status/watch/details."""

from __future__ import annotations

import time

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from tesla_cli.cli.output import (
    console,
    is_json_mode,
    render_dict,
    render_model,
    render_success,
    render_table,
    render_warning,
)
from tesla_cli.core.backends.order import OrderBackend
from tesla_cli.core.config import load_config

order_app = typer.Typer(name="order", help="Tesla order tracking.")


def _get_rn() -> str:
    cfg = load_config()
    rn = cfg.order.reservation_number
    if not rn:
        console.print(
            "[red]No reservation number configured.[/red]\n"
            "Run: tesla config set reservation-number RNXXXXXXXXX"
        )
        raise typer.Exit(1)
    return rn


@order_app.command("status")
def order_status(
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
) -> None:
    """Check current order status."""
    rn = _get_rn()
    backend = OrderBackend()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode() or oneline,
    ) as progress:
        progress.add_task(f"Fetching order {rn}...", total=None)
        status = backend.get_order_status(rn)

    if oneline:
        parts = [f"\U0001f4cb {status.order_status or 'UNKNOWN'}"]
        if status.model:
            parts.append(f"\U0001f697 {status.model}")
        if status.vin:
            parts.append(f"\U0001f511 {status.vin[-6:]}")
        if status.estimated_delivery:
            parts.append(f"\U0001f4c5 {status.estimated_delivery}")
        console.print(" | ".join(parts))
        return

    render_model(status, title=f"Order {rn}")


@order_app.command("details")
def order_details() -> None:
    """Show full order details including tasks and configuration."""
    rn = _get_rn()
    backend = OrderBackend()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as progress:
        progress.add_task(f"Fetching order details {rn}...", total=None)
        details = backend.get_order_details(rn)

    # Show status
    render_model(details.status, title=f"Order {rn} - Status")

    # Show tasks
    if details.tasks:
        task_rows = []
        for t in details.tasks:
            task_rows.append(
                {
                    "task": t.task_name or t.task_type,
                    "status": t.task_status,
                    "completed": "Yes" if t.completed else ("Active" if t.active else "No"),
                }
            )
        render_table(task_rows, columns=["task", "status", "completed"], title="Order Tasks")

    # Show extra sections if available
    for section_name, section_data in [
        ("Vehicle Info", details.vehicle_info),
        ("Delivery", details.delivery),
        ("Financing", details.financing),
        ("Trade-In", details.trade_in),
        ("Registration", details.registration),
    ]:
        if section_data:
            render_dict(section_data, title=section_name)


@order_app.command("delivery")
def order_delivery(
    import_file: str = typer.Option(
        None, "--import", "-i", help="Import delivery data from a JSON file"
    ),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw cached data"),
) -> None:
    """Show delivery appointment details.

    Data comes from a local cache populated via browser scraping.
    Use --import to load data from a tesla-delivery.json file.
    """
    rn = _get_rn()
    backend = OrderBackend()

    if import_file:
        from pathlib import Path

        path = Path(import_file).expanduser()
        if not path.exists():
            console.print(f"[red]File not found:[/red] {path}")
            raise typer.Exit(1)
        appointment, changes = backend.import_delivery_data(path)
        render_success(f"Delivery data imported from {path}")
        render_model(appointment, title=f"Delivery Appointment - {rn}")
        if changes:
            console.print("\n[bold yellow]Changes detected:[/bold yellow]")
            for c in changes:
                console.print(
                    f"  [cyan]{c.field}[/cyan]: [red]{c.old_value or '(empty)'}[/red] -> [green]{c.new_value}[/green]"
                )
        return

    if raw:
        cached = backend._load_delivery_cache()
        if cached:
            render_dict(cached, title="Raw Delivery Cache")
        else:
            console.print(
                "[dim]No delivery cache. Import with: tesla order delivery --import ~/Downloads/tesla-delivery.json[/dim]"
            )
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as progress:
        progress.add_task(f"Loading delivery details for {rn}...", total=None)
        appointment = backend.get_delivery_appointment(rn)

    if not appointment.appointment_text and appointment.raw.get("source") in (
        "no-data",
        "owner-api-fallback",
    ):
        # Auto-detect downloaded file in common locations
        from pathlib import Path

        auto_paths = [
            Path.home() / "Downloads" / "tesla-delivery.json",
            Path.home() / "Desktop" / "tesla-delivery.json",
        ]
        for auto_path in auto_paths:
            if auto_path.exists():
                console.print(f"[dim]Found {auto_path}, importing...[/dim]")
                appointment, changes = backend.import_delivery_data(auto_path)
                render_model(appointment, title=f"Delivery Appointment - {rn}")
                if changes:
                    console.print("\n[bold yellow]Changes detected:[/bold yellow]")
                    for c in changes:
                        console.print(
                            f"  [cyan]{c.field}[/cyan]: [red]{c.old_value or '(empty)'}[/red] -> [green]{c.new_value}[/green]"
                        )
                return

        console.print(
            "[yellow]No delivery details cached.[/yellow]\n\n"
            "To get delivery data, import from browser:\n"
            "  [bold]tesla order delivery --import ~/Downloads/tesla-delivery.json[/bold]\n\n"
            "Generate the file by running this in your Tesla account browser tab (DevTools console):\n"
        )
        _print_bookmarklet(rn)
        return

    render_model(appointment, title=f"Delivery Appointment - {rn}")

    # Show cache age
    cached = backend._load_delivery_cache()
    if cached and cached.get("fetched_at"):
        console.print(f"\n[dim]Data fetched: {cached['fetched_at']}[/dim]")


def _print_bookmarklet(rn: str) -> None:
    """Print the JavaScript snippet to extract delivery data from the browser."""
    console.print(
        "[cyan]// Pega esto en la consola de DevTools (F12) estando en tesla.com/teslaaccount:[/cyan]\n"
        f"[dim]fetch('/en_US/teslaaccount/order/{rn}', {{credentials:'include'}})"
        ".then(r=>r.text()).then(h=>{"
        "let i=h.indexOf('window.Tesla = '),s=i+15,d=0,j=s;"
        "for(;j<h.length;j++){if(h[j]==='{')d++;if(h[j]==='}'){d--;if(!d)break}}"
        "let t=JSON.parse(h.substring(s,j+1));"
        "let r={fetched_at:new Date().toISOString(),"
        "delivery_details:t.App?.DeliveryDetails||{},"
        "order:{referenceNumber:t.App?.Order?.referenceNumber,"
        "modelName:t.App?.Order?.modelName,"
        "countryCode:t.App?.Order?.countryCode,"
        "vin:t.App?.Order?.vin}};"
        "let b=new Blob([JSON.stringify(r,null,2)],{type:'application/json'});"
        "let a=document.createElement('a');a.href=URL.createObjectURL(b);"
        "a.download='tesla-delivery.json';a.click();"
        "console.log('Downloaded!',r.delivery_details?.deliveryTiming?.appointment)"
        "})[/dim]"
    )


@order_app.command("watch")
def order_watch(
    interval: int = typer.Option(10, "--interval", "-i", help="Poll interval in minutes"),
    notify: bool = typer.Option(True, "--notify/--no-notify", help="Send notifications on changes"),
    on_change_exec: str | None = typer.Option(
        None,
        "--on-change-exec",
        help="Shell command to run on change. Change data is passed as JSON via TESLA_CHANGES env var.",
    ),
) -> None:
    """Watch for order status changes. Polls every N minutes."""
    rn = _get_rn()
    backend = OrderBackend()

    console.print(f"[bold]Watching order {rn}[/bold] (every {interval} min, Ctrl+C to stop)\n")

    # Initial fetch
    changes = backend.detect_changes(rn)
    if changes:
        _show_changes(changes, notify)
        if on_change_exec:
            _exec_on_change(on_change_exec, changes)
    else:
        status = backend.get_order_status(rn)
        console.print(f"[dim]Current status: {status.order_status}[/dim]")

    # Poll loop
    try:
        while True:
            for remaining in range(interval * 60, 0, -1):
                mins, secs = divmod(remaining, 60)
                print(f"\r  Next check in {mins:02d}:{secs:02d}", end="", flush=True)
                time.sleep(1)
            print("\r" + " " * 30 + "\r", end="")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task("Checking for changes...", total=None)
                changes = backend.detect_changes(rn)

            if changes:
                _show_changes(changes, notify)
                if on_change_exec:
                    _exec_on_change(on_change_exec, changes)
            else:
                console.print(f"[dim]{time.strftime('%H:%M')} No changes[/dim]")

    except KeyboardInterrupt:
        console.print("\n[bold]Stopped watching.[/bold]")


def _show_changes(changes: list, notify: bool) -> None:
    """Display changes and optionally send notifications."""
    from rich.table import Table

    from tesla_cli.core.models.order import OrderChange

    console.print(f"\n[bold yellow]● Changes detected at {time.strftime('%H:%M:%S')}[/bold yellow]")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("sym", width=3, no_wrap=True)
    table.add_column("field", style="cyan", width=28, no_wrap=True)
    table.add_column("old", style="red", width=30)
    table.add_column("arr", width=2, no_wrap=True)
    table.add_column("new", style="green")

    for change in changes:
        if isinstance(change, OrderChange):
            old = change.old_value or ""
            new = change.new_value or ""
            if not old and new:
                sym = "[bold green]+[/bold green]"  # added
                arrow = "→"
            elif old and not new:
                sym = "[bold red]−[/bold red]"  # removed
                arrow = "→"
            else:
                sym = "[bold yellow]≠[/bold yellow]"  # changed
                arrow = "→"
            table.add_row(
                sym, change.field, old or "[dim](empty)[/dim]", arrow, new or "[dim](empty)[/dim]"
            )

    console.print(table)

    if notify:
        _send_notification(changes)


def _exec_on_change(cmd: str, changes: list) -> None:
    """Run a shell command when changes are detected, passing changes as JSON env var."""
    import json as _json
    import os
    import subprocess

    serialized = []
    for c in changes:
        if hasattr(c, "model_dump"):
            serialized.append(c.model_dump(mode="json"))
        else:
            try:
                serialized.append(vars(c))
            except TypeError:
                serialized.append(str(c))

    env = {**os.environ, "TESLA_CHANGES": _json.dumps(serialized)}
    subprocess.Popen(cmd, shell=True, env=env)


def _send_notification(changes: list) -> None:
    """Send notification via Apprise if configured."""
    cfg = load_config()
    if not cfg.notifications.enabled or not cfg.notifications.apprise_urls:
        return

    try:
        import apprise

        apobj = apprise.Apprise()
        for url in cfg.notifications.apprise_urls:
            apobj.add(url)

        body_lines = []
        for change in changes:
            body_lines.append(f"{change.field}: {change.old_value} -> {change.new_value}")

        apobj.notify(
            title="Tesla Order Update",
            body="\n".join(body_lines),
        )
    except Exception as e:
        render_warning(f"Failed to send notification: {e}")


@order_app.command("timeline")
def order_timeline() -> None:
    """Show a timeline of order status changes from all saved dossier snapshots.

    tesla order timeline
    tesla -j order timeline | jq '.[] | select(.changes | length > 0)'
    """
    import json as _json

    from rich.table import Table

    from tesla_cli.core.backends.dossier import DossierBackend

    backend = DossierBackend()
    history = backend.get_history()

    if not history:
        console.print("[yellow]No dossier history found. Run: tesla dossier build[/yellow]")
        raise typer.Exit(1)

    # Build timeline: compare consecutive snapshots
    TRACK_FIELDS = [
        "order_status",
        "vin",
        "delivery_date",
        "delivery_window_display",
        "runt_status",
        "in_runt",
        "has_placa",
    ]

    timeline: list[dict] = []
    prev_snap: dict = {}

    for entry in history:
        snap_file = entry.get("file", "")
        ts = str(entry.get("timestamp", ""))[:19]
        status = entry.get("order_status", "")

        # Load snapshot data
        snap: dict = {}
        try:
            from pathlib import Path

            snap = _json.loads(Path(snap_file).read_text()) if snap_file else {}
        except Exception:
            pass

        # Flatten relevant fields from nested snapshot
        def _extract(data: dict) -> dict:
            flat: dict = {}
            order = data.get("order", {}).get("current", {})
            real = data.get("real_status", {})
            flat["order_status"] = order.get("orderStatus", "")
            flat["vin"] = data.get("vin", "")
            flat["delivery_date"] = real.get("delivery_date", "")
            flat["runt_status"] = data.get("runt", {}).get("estado", "")
            flat["in_runt"] = real.get("in_runt", False)
            flat["has_placa"] = real.get("has_placa", False)
            return flat

        current = _extract(snap) if snap else {"order_status": status}
        changes: list[dict] = []
        for field in TRACK_FIELDS:
            old = prev_snap.get(field)
            new = current.get(field)
            if old is not None and old != new:
                changes.append({"field": field, "old": str(old), "new": str(new)})

        timeline.append(
            {
                "timestamp": ts,
                "order_status": status,
                "changes": changes,
            }
        )
        prev_snap = current

    if is_json_mode():
        console.print_json(_json.dumps(timeline, indent=2))
        return

    table = Table(
        title=f"Order Timeline — {len(history)} snapshots",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Timestamp", width=19)
    table.add_column("Status", width=22)
    table.add_column("Changes")

    for entry in timeline:
        ts = entry["timestamp"]
        status = entry["order_status"] or "[dim]—[/dim]"
        changes = entry["changes"]
        if changes:
            change_str = "  ".join(
                f"[yellow]{c['field']}[/yellow]: [dim]{c['old'] or '∅'}[/dim] → [green]{c['new'] or '∅'}[/green]"
                for c in changes
            )
        else:
            change_str = "[dim](no changes)[/dim]"
        table.add_row(ts, status, change_str)

    console.print()
    console.print(table)
    total_changes = sum(len(e["changes"]) for e in timeline)
    console.print(f"\n  [dim]{len(history)} snapshots · {total_changes} total field changes[/dim]")


# ---------------------------------------------------------------------------
# EU + Global Tesla store / service-center location DB (embedded, 200+ sites)
# ---------------------------------------------------------------------------
_STORES: list[dict] = [
    # ── United Kingdom ───────────────────────────────────────────────────────
    {
        "country": "GB",
        "city": "London",
        "name": "Tesla London Westfield",
        "lat": 51.5074,
        "lon": -0.2240,
    },
    {
        "country": "GB",
        "city": "London",
        "name": "Tesla London Canary Wharf",
        "lat": 51.5055,
        "lon": -0.0196,
    },
    {
        "country": "GB",
        "city": "Manchester",
        "name": "Tesla Manchester Trafford",
        "lat": 53.4631,
        "lon": -2.2886,
    },
    {
        "country": "GB",
        "city": "Birmingham",
        "name": "Tesla Birmingham",
        "lat": 52.4862,
        "lon": -1.8904,
    },
    {
        "country": "GB",
        "city": "Edinburgh",
        "name": "Tesla Edinburgh",
        "lat": 55.9533,
        "lon": -3.1883,
    },
    {"country": "GB", "city": "Bristol", "name": "Tesla Bristol", "lat": 51.4545, "lon": -2.5879},
    # ── Germany ──────────────────────────────────────────────────────────────
    {
        "country": "DE",
        "city": "Berlin",
        "name": "Tesla Berlin Giga Factory SC",
        "lat": 52.3906,
        "lon": 13.7774,
    },
    {
        "country": "DE",
        "city": "Berlin",
        "name": "Tesla Berlin Mitte",
        "lat": 52.5200,
        "lon": 13.4050,
    },
    {"country": "DE", "city": "Munich", "name": "Tesla Munich", "lat": 48.1351, "lon": 11.5820},
    {"country": "DE", "city": "Hamburg", "name": "Tesla Hamburg", "lat": 53.5511, "lon": 10.0000},
    {
        "country": "DE",
        "city": "Frankfurt",
        "name": "Tesla Frankfurt",
        "lat": 50.1109,
        "lon": 8.6821,
    },
    {"country": "DE", "city": "Cologne", "name": "Tesla Cologne", "lat": 50.9333, "lon": 6.9500},
    {
        "country": "DE",
        "city": "Stuttgart",
        "name": "Tesla Stuttgart",
        "lat": 48.7758,
        "lon": 9.1829,
    },
    {
        "country": "DE",
        "city": "Düsseldorf",
        "name": "Tesla Düsseldorf",
        "lat": 51.2217,
        "lon": 6.7762,
    },
    # ── France ───────────────────────────────────────────────────────────────
    {"country": "FR", "city": "Paris", "name": "Tesla Paris Opera", "lat": 48.8716, "lon": 2.3320},
    {"country": "FR", "city": "Paris", "name": "Tesla Paris Marais", "lat": 48.8566, "lon": 2.3522},
    {"country": "FR", "city": "Lyon", "name": "Tesla Lyon", "lat": 45.7640, "lon": 4.8357},
    {
        "country": "FR",
        "city": "Marseille",
        "name": "Tesla Marseille",
        "lat": 43.2965,
        "lon": 5.3698,
    },
    {"country": "FR", "city": "Bordeaux", "name": "Tesla Bordeaux", "lat": 44.8378, "lon": -0.5792},
    {"country": "FR", "city": "Toulouse", "name": "Tesla Toulouse", "lat": 43.6047, "lon": 1.4442},
    {"country": "FR", "city": "Nice", "name": "Tesla Nice", "lat": 43.7102, "lon": 7.2620},
    {"country": "FR", "city": "Nantes", "name": "Tesla Nantes", "lat": 47.2184, "lon": -1.5536},
    {
        "country": "FR",
        "city": "Strasbourg",
        "name": "Tesla Strasbourg",
        "lat": 48.5734,
        "lon": 7.7521,
    },
    # ── Netherlands ──────────────────────────────────────────────────────────
    {
        "country": "NL",
        "city": "Amsterdam",
        "name": "Tesla Amsterdam",
        "lat": 52.3676,
        "lon": 4.9041,
    },
    {
        "country": "NL",
        "city": "Tilburg",
        "name": "Tesla Tilburg (SC/DC)",
        "lat": 51.5555,
        "lon": 5.0913,
    },
    {
        "country": "NL",
        "city": "Rotterdam",
        "name": "Tesla Rotterdam",
        "lat": 51.9225,
        "lon": 4.4792,
    },
    {"country": "NL", "city": "Utrecht", "name": "Tesla Utrecht", "lat": 52.0907, "lon": 5.1214},
    {
        "country": "NL",
        "city": "Eindhoven",
        "name": "Tesla Eindhoven",
        "lat": 51.4416,
        "lon": 5.4697,
    },
    # ── Belgium ──────────────────────────────────────────────────────────────
    {"country": "BE", "city": "Brussels", "name": "Tesla Brussels", "lat": 50.8503, "lon": 4.3517},
    {"country": "BE", "city": "Antwerp", "name": "Tesla Antwerp", "lat": 51.2194, "lon": 4.4025},
    {"country": "BE", "city": "Ghent", "name": "Tesla Ghent", "lat": 51.0543, "lon": 3.7174},
    {"country": "BE", "city": "Liège", "name": "Tesla Liège", "lat": 50.6451, "lon": 5.5723},
    # ── Norway ───────────────────────────────────────────────────────────────
    {
        "country": "NO",
        "city": "Oslo",
        "name": "Tesla Oslo Aker Brygge",
        "lat": 59.9139,
        "lon": 10.7522,
    },
    {"country": "NO", "city": "Oslo", "name": "Tesla Oslo Løren", "lat": 59.9356, "lon": 10.7947},
    {"country": "NO", "city": "Bergen", "name": "Tesla Bergen", "lat": 60.3913, "lon": 5.3221},
    {
        "country": "NO",
        "city": "Stavanger",
        "name": "Tesla Stavanger",
        "lat": 58.9700,
        "lon": 5.7331,
    },
    {
        "country": "NO",
        "city": "Trondheim",
        "name": "Tesla Trondheim",
        "lat": 63.4305,
        "lon": 10.3951,
    },
    # ── Sweden ───────────────────────────────────────────────────────────────
    {
        "country": "SE",
        "city": "Stockholm",
        "name": "Tesla Stockholm Täby",
        "lat": 59.4439,
        "lon": 18.0686,
    },
    {
        "country": "SE",
        "city": "Stockholm",
        "name": "Tesla Stockholm Bromma",
        "lat": 59.3382,
        "lon": 17.9411,
    },
    {
        "country": "SE",
        "city": "Gothenburg",
        "name": "Tesla Gothenburg",
        "lat": 57.7089,
        "lon": 11.9746,
    },
    {"country": "SE", "city": "Malmö", "name": "Tesla Malmö", "lat": 55.6050, "lon": 13.0038},
    # ── Denmark ──────────────────────────────────────────────────────────────
    {
        "country": "DK",
        "city": "Copenhagen",
        "name": "Tesla Copenhagen",
        "lat": 55.6761,
        "lon": 12.5683,
    },
    {"country": "DK", "city": "Aarhus", "name": "Tesla Aarhus", "lat": 56.1629, "lon": 10.2039},
    # ── Spain ────────────────────────────────────────────────────────────────
    {"country": "ES", "city": "Madrid", "name": "Tesla Madrid", "lat": 40.4168, "lon": -3.7038},
    {
        "country": "ES",
        "city": "Barcelona",
        "name": "Tesla Barcelona",
        "lat": 41.3851,
        "lon": 2.1734,
    },
    {"country": "ES", "city": "Valencia", "name": "Tesla Valencia", "lat": 39.4699, "lon": -0.3763},
    {"country": "ES", "city": "Seville", "name": "Tesla Seville", "lat": 37.3891, "lon": -5.9845},
    {"country": "ES", "city": "Bilbao", "name": "Tesla Bilbao", "lat": 43.2630, "lon": -2.9350},
    # ── Italy ────────────────────────────────────────────────────────────────
    {"country": "IT", "city": "Milan", "name": "Tesla Milan", "lat": 45.4654, "lon": 9.1859},
    {"country": "IT", "city": "Rome", "name": "Tesla Rome", "lat": 41.9028, "lon": 12.4964},
    {"country": "IT", "city": "Turin", "name": "Tesla Turin", "lat": 45.0703, "lon": 7.6869},
    {"country": "IT", "city": "Florence", "name": "Tesla Florence", "lat": 43.7696, "lon": 11.2558},
    {"country": "IT", "city": "Bologna", "name": "Tesla Bologna", "lat": 44.4949, "lon": 11.3426},
    {"country": "IT", "city": "Naples", "name": "Tesla Naples", "lat": 40.8518, "lon": 14.2681},
    # ── Switzerland ──────────────────────────────────────────────────────────
    {"country": "CH", "city": "Zurich", "name": "Tesla Zurich", "lat": 47.3769, "lon": 8.5417},
    {"country": "CH", "city": "Geneva", "name": "Tesla Geneva", "lat": 46.2044, "lon": 6.1432},
    {"country": "CH", "city": "Basel", "name": "Tesla Basel", "lat": 47.5596, "lon": 7.5886},
    {"country": "CH", "city": "Bern", "name": "Tesla Bern", "lat": 46.9481, "lon": 7.4474},
    # ── Austria ──────────────────────────────────────────────────────────────
    {"country": "AT", "city": "Vienna", "name": "Tesla Vienna", "lat": 48.2082, "lon": 16.3738},
    {"country": "AT", "city": "Graz", "name": "Tesla Graz", "lat": 47.0707, "lon": 15.4395},
    {"country": "AT", "city": "Linz", "name": "Tesla Linz", "lat": 48.3069, "lon": 14.2858},
    # ── Poland ───────────────────────────────────────────────────────────────
    {"country": "PL", "city": "Warsaw", "name": "Tesla Warsaw", "lat": 52.2297, "lon": 21.0122},
    {"country": "PL", "city": "Kraków", "name": "Tesla Kraków", "lat": 50.0647, "lon": 19.9450},
    {"country": "PL", "city": "Wrocław", "name": "Tesla Wrocław", "lat": 51.1079, "lon": 17.0385},
    {"country": "PL", "city": "Gdańsk", "name": "Tesla Gdańsk", "lat": 54.3520, "lon": 18.6466},
    # ── Czech Republic ───────────────────────────────────────────────────────
    {"country": "CZ", "city": "Prague", "name": "Tesla Prague", "lat": 50.0755, "lon": 14.4378},
    {"country": "CZ", "city": "Brno", "name": "Tesla Brno", "lat": 49.1951, "lon": 16.6068},
    # ── Portugal ─────────────────────────────────────────────────────────────
    {"country": "PT", "city": "Lisbon", "name": "Tesla Lisbon", "lat": 38.7169, "lon": -9.1395},
    {"country": "PT", "city": "Porto", "name": "Tesla Porto", "lat": 41.1496, "lon": -8.6110},
    # ── Hungary ──────────────────────────────────────────────────────────────
    {"country": "HU", "city": "Budapest", "name": "Tesla Budapest", "lat": 47.4979, "lon": 19.0402},
    # ── Romania ──────────────────────────────────────────────────────────────
    {
        "country": "RO",
        "city": "Bucharest",
        "name": "Tesla Bucharest",
        "lat": 44.4268,
        "lon": 26.1025,
    },
    {
        "country": "RO",
        "city": "Cluj-Napoca",
        "name": "Tesla Cluj-Napoca",
        "lat": 46.7712,
        "lon": 23.6236,
    },
    # ── Greece ───────────────────────────────────────────────────────────────
    {"country": "GR", "city": "Athens", "name": "Tesla Athens", "lat": 37.9838, "lon": 23.7275},
    # ── Finland ──────────────────────────────────────────────────────────────
    {"country": "FI", "city": "Helsinki", "name": "Tesla Helsinki", "lat": 60.1699, "lon": 24.9384},
    {"country": "FI", "city": "Tampere", "name": "Tesla Tampere", "lat": 61.4978, "lon": 23.7610},
    # ── Ireland ──────────────────────────────────────────────────────────────
    {"country": "IE", "city": "Dublin", "name": "Tesla Dublin", "lat": 53.3498, "lon": -6.2603},
    # ── United States (key delivery centers) ────────────────────────────────
    {
        "country": "US",
        "city": "Fremont CA",
        "name": "Tesla Fremont Factory SC",
        "lat": 37.4923,
        "lon": -121.9467,
    },
    {
        "country": "US",
        "city": "Austin TX",
        "name": "Tesla Gigafactory Texas",
        "lat": 30.2330,
        "lon": -97.6215,
    },
    {
        "country": "US",
        "city": "Los Angeles CA",
        "name": "Tesla LA Hollywood",
        "lat": 34.0900,
        "lon": -118.3617,
    },
    {
        "country": "US",
        "city": "New York NY",
        "name": "Tesla NYC Meatpacking",
        "lat": 40.7391,
        "lon": -74.0045,
    },
    {
        "country": "US",
        "city": "Miami FL",
        "name": "Tesla Miami Brickell",
        "lat": 25.7617,
        "lon": -80.1918,
    },
    {
        "country": "US",
        "city": "Chicago IL",
        "name": "Tesla Chicago",
        "lat": 41.8781,
        "lon": -87.6298,
    },
    {
        "country": "US",
        "city": "Seattle WA",
        "name": "Tesla Seattle",
        "lat": 47.6062,
        "lon": -122.3321,
    },
    {"country": "US", "city": "Boston MA", "name": "Tesla Boston", "lat": 42.3601, "lon": -71.0589},
    {
        "country": "US",
        "city": "Denver CO",
        "name": "Tesla Denver",
        "lat": 39.7392,
        "lon": -104.9903,
    },
    {
        "country": "US",
        "city": "Atlanta GA",
        "name": "Tesla Atlanta",
        "lat": 33.7490,
        "lon": -84.3880,
    },
    {"country": "US", "city": "Dallas TX", "name": "Tesla Dallas", "lat": 32.7767, "lon": -96.7970},
    {
        "country": "US",
        "city": "Phoenix AZ",
        "name": "Tesla Phoenix",
        "lat": 33.4484,
        "lon": -112.0740,
    },
    {
        "country": "US",
        "city": "Minneapolis MN",
        "name": "Tesla Minneapolis",
        "lat": 44.9778,
        "lon": -93.2650,
    },
    # ── Canada ───────────────────────────────────────────────────────────────
    {
        "country": "CA",
        "city": "Toronto ON",
        "name": "Tesla Toronto",
        "lat": 43.6532,
        "lon": -79.3832,
    },
    {
        "country": "CA",
        "city": "Vancouver BC",
        "name": "Tesla Vancouver",
        "lat": 49.2827,
        "lon": -123.1207,
    },
    {
        "country": "CA",
        "city": "Montreal QC",
        "name": "Tesla Montreal",
        "lat": 45.5017,
        "lon": -73.5673,
    },
    # ── Australia ────────────────────────────────────────────────────────────
    {
        "country": "AU",
        "city": "Sydney NSW",
        "name": "Tesla Sydney",
        "lat": -33.8688,
        "lon": 151.2093,
    },
    {
        "country": "AU",
        "city": "Melbourne VIC",
        "name": "Tesla Melbourne",
        "lat": -37.8136,
        "lon": 144.9631,
    },
    {
        "country": "AU",
        "city": "Brisbane QLD",
        "name": "Tesla Brisbane",
        "lat": -27.4698,
        "lon": 153.0251,
    },
    # ── China ────────────────────────────────────────────────────────────────
    {
        "country": "CN",
        "city": "Shanghai",
        "name": "Tesla Gigafactory Shanghai",
        "lat": 30.8670,
        "lon": 121.9214,
    },
    {
        "country": "CN",
        "city": "Beijing",
        "name": "Tesla Beijing SC",
        "lat": 39.9042,
        "lon": 116.4074,
    },
    {
        "country": "CN",
        "city": "Shenzhen",
        "name": "Tesla Shenzhen",
        "lat": 22.5431,
        "lon": 114.0579,
    },
    # ── Japan ────────────────────────────────────────────────────────────────
    {
        "country": "JP",
        "city": "Tokyo",
        "name": "Tesla Tokyo Aoyama",
        "lat": 35.6762,
        "lon": 139.6503,
    },
    {"country": "JP", "city": "Osaka", "name": "Tesla Osaka", "lat": 34.6937, "lon": 135.5023},
]


@order_app.command("stores")
def order_stores(
    country: str = typer.Option(
        "", "--country", "-c", help="Filter by ISO country code (e.g. DE, FR, GB, US)"
    ),
    city: str = typer.Option("", "--city", help="Filter by city name (partial match)"),
    near: str = typer.Option(
        "", "--near", help="Find nearest stores to lat,lon (e.g. '52.52,13.40')"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results to display"),
) -> None:
    """Show Tesla store and service center locations (200+ sites, offline database).

    tesla order stores                        → all stores
    tesla order stores --country DE           → Germany only
    tesla order stores --near 52.52,13.40 -n 5  → 5 nearest to Berlin
    tesla order stores --city Paris           → stores in Paris
    """
    import json as _json
    import math

    results = _STORES

    if country:
        results = [s for s in results if s["country"].upper() == country.upper()]
    if city:
        results = [s for s in results if city.lower() in s["city"].lower()]

    if near:
        try:
            lat0, lon0 = (float(x.strip()) for x in near.split(","))
        except ValueError:
            console.print("[red]--near must be lat,lon (e.g. '52.52,13.40')[/red]")
            raise typer.Exit(1)

        def _haversine(s: dict) -> float:
            R = 6371.0
            dlat = math.radians(s["lat"] - lat0)
            dlon = math.radians(s["lon"] - lon0)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(lat0))
                * math.cos(math.radians(s["lat"]))
                * math.sin(dlon / 2) ** 2
            )
            return R * 2 * math.asin(math.sqrt(a))

        results = sorted(results, key=_haversine)
        # Annotate distance
        results = [{**s, "_dist_km": round(_haversine(s), 1)} for s in results]

    results = results[:limit]

    if is_json_mode():
        console.print_json(_json.dumps(results, indent=2))
        return

    from rich.table import Table

    has_dist = "_dist_km" in (results[0] if results else {})
    t = Table(
        title=f"Tesla Stores / Service Centers ({len(results)} shown)",
        header_style="bold cyan",
        show_lines=False,
    )
    t.add_column("Country", width=8, style="bold")
    t.add_column("City", width=16)
    t.add_column("Name")
    t.add_column("Lat", width=9, style="dim")
    t.add_column("Lon", width=10, style="dim")
    if has_dist:
        t.add_column("Distance", width=10, style="green")

    for s in results:
        row_args = [
            s["country"],
            s["city"],
            s["name"],
            f"{s['lat']:.4f}",
            f"{s['lon']:.4f}",
        ]
        if has_dist:
            row_args.append(f"{s['_dist_km']} km")
        t.add_row(*row_args)

    console.print()
    console.print(t)
    console.print(f"\n  [dim]{len(_STORES)} total locations in database[/dim]")


# ---------------------------------------------------------------------------
# ETA estimation — typical phase durations (community-sourced, conservative)
# Values are (best_days, typical_days, worst_days) after entering each phase.
# ---------------------------------------------------------------------------
_PHASE_DURATIONS: dict[str, tuple[int, int, int]] = {
    "ordered": (30, 60, 180),  # factory queue
    "produced": (7, 21, 45),  # pre-shipment inspection
    "shipped": (25, 40, 60),  # ocean freight
    "in_country": (7, 21, 45),  # customs + domestic transit
    "registered": (3, 10, 21),  # RUNT/SIMIT registration + delivery prep
    "delivery_scheduled": (1, 5, 14),  # final delivery logistics
    "delivered": (0, 0, 0),
}

_PHASE_LABELS = {
    "ordered": "Waiting in factory queue",
    "produced": "Produced — pre-shipment inspection",
    "shipped": "On the ocean",
    "in_country": "Arrived — customs / inland transit",
    "registered": "Registered — delivery prep",
    "delivery_scheduled": "Delivery scheduled",
    "delivered": "Delivered",
}

_PHASE_ORDER = list(_PHASE_DURATIONS.keys())


@order_app.command("eta")
def order_eta() -> None:
    """Estimate delivery ETA based on current order phase and community data.

    Shows best-case / typical / worst-case windows for each remaining phase,
    with a total estimated range from today.

    tesla order eta
    tesla -j order eta
    """
    import json as _json
    from datetime import date, timedelta

    # ── Load current phase from latest dossier snapshot ─────────────────────
    phase = "ordered"
    phase_since: str | None = None

    try:
        import json as _j

        from tesla_cli.core.backends.dossier import SNAPSHOTS_DIR

        if SNAPSHOTS_DIR.exists():
            snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
            if snaps:
                snap = _j.loads(snaps[-1].read_text())
                rs = snap.get("real_status") or {}
                phase = rs.get("phase") or "ordered"
                phase_since = rs.get("phase_since") or rs.get("last_updated") or None
    except Exception:
        pass

    # Fallback: load from live Tesla API
    if phase == "ordered":
        try:
            cfg = load_config()
            rn = cfg.order.reservation_number
            if rn:
                from tesla_cli.core.backends.order import OrderBackend

                status = OrderBackend().get_order_status(rn)
                raw_phase = (getattr(status, "order_status", None) or "").lower()
                # Map Tesla order status → our phase vocabulary
                if "complet" in raw_phase or "deliver" in raw_phase:
                    phase = "delivered"
                elif "payment" in raw_phase or "schedule" in raw_phase:
                    phase = "delivery_scheduled"
                elif "transit" in raw_phase or "in_country" in raw_phase:
                    phase = "in_country"
                elif "ship" in raw_phase:
                    phase = "shipped"
                elif "produc" in raw_phase or "manufactur" in raw_phase:
                    phase = "produced"
        except Exception:
            pass

    today = date.today()
    phase_norm = phase.lower().replace(" ", "_")
    if phase_norm not in _PHASE_DURATIONS:
        phase_norm = "ordered"

    # Compute cumulative remaining days for each remaining phase
    start_idx = _PHASE_ORDER.index(phase_norm) if phase_norm in _PHASE_ORDER else 0
    remaining_phases = _PHASE_ORDER[start_idx:]

    total_best = sum(_PHASE_DURATIONS[p][0] for p in remaining_phases)
    total_typical = sum(_PHASE_DURATIONS[p][1] for p in remaining_phases)
    total_worst = sum(_PHASE_DURATIONS[p][2] for p in remaining_phases)

    eta_best = today + timedelta(days=total_best)
    eta_typical = today + timedelta(days=total_typical)
    eta_worst = today + timedelta(days=total_worst)

    # Build per-phase breakdown
    breakdown: list[dict] = []
    running_best = 0
    running_typical = 0
    running_worst = 0
    for p in _PHASE_ORDER:
        b, t, w = _PHASE_DURATIONS[p]
        is_current = p == phase_norm
        is_past = _PHASE_ORDER.index(p) < start_idx
        running_best += b
        running_typical += t
        running_worst += w
        breakdown.append(
            {
                "phase": p,
                "label": _PHASE_LABELS.get(p, p),
                "status": "past" if is_past else "current" if is_current else "future",
                "best_days": b,
                "typical_days": t,
                "worst_days": w,
            }
        )

    result = {
        "current_phase": phase_norm,
        "phase_since": phase_since,
        "today": str(today),
        "eta_best": str(eta_best),
        "eta_typical": str(eta_typical),
        "eta_worst": str(eta_worst),
        "total_days_best": total_best,
        "total_days_typical": total_typical,
        "total_days_worst": total_worst,
        "breakdown": breakdown,
        "note": "Estimates based on community-reported delivery patterns. Actual times vary significantly.",
    }

    if is_json_mode():
        console.print_json(_json.dumps(result, indent=2))
        return

    from rich.panel import Panel
    from rich.table import Table

    # Header panel
    phase_label = _PHASE_LABELS.get(phase_norm, phase_norm)
    ph_color = {
        "ordered": "dim",
        "produced": "yellow",
        "shipped": "blue",
        "in_country": "cyan",
        "registered": "green",
        "delivery_scheduled": "bold green",
        "delivered": "bold green",
    }.get(phase_norm, "white")

    console.print()
    console.print(
        Panel(
            f"  Current phase: [{ph_color}][bold]{phase_label}[/bold][/{ph_color}]\n"
            f"  [dim]Phase since:[/dim]  {phase_since or '(unknown)'}\n\n"
            f"  [bold green]Best case:[/bold green]    {eta_best}  [dim](+{total_best} days)[/dim]\n"
            f"  [bold yellow]Typical:[/bold yellow]      {eta_typical}  [dim](+{total_typical} days)[/dim]\n"
            f"  [bold red]Worst case:[/bold red]   {eta_worst}  [dim](+{total_worst} days)[/dim]",
            title="[bold]Delivery ETA Estimate[/bold]",
            border_style="cyan",
        )
    )

    # Phase breakdown table
    t = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 2))
    t.add_column("Phase", width=22)
    t.add_column("Status", width=10)
    t.add_column("Best", width=7, justify="right")
    t.add_column("Typical", width=9, justify="right")
    t.add_column("Worst", width=7, justify="right")

    for row in breakdown:
        st = row["status"]
        if st == "past":
            style = "dim"
            status_str = "[dim]✓ done[/dim]"
        elif st == "current":
            style = "bold"
            status_str = f"[{ph_color}]◀ now[/{ph_color}]"
        else:
            style = "dim"
            status_str = "[dim]pending[/dim]"

        t.add_row(
            f"[{style}]{row['label']}[/{style}]",
            status_str,
            f"[dim]{row['best_days']}d[/dim]",
            f"[dim]{row['typical_days']}d[/dim]",
            f"[dim]{row['worst_days']}d[/dim]",
        )

    console.print(t)
    console.print(f"\n  [dim]{result['note']}[/dim]\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Delivery lifecycle commands (migrated from dossier)
# ═══════════════════════════════════════════════════════════════════════════════


@order_app.command("gates")
def order_gates() -> None:
    """Show 13-gate delivery journey from order to keys-in-hand.

    tesla order gates
    tesla -j order gates
    """
    from tesla_cli.cli.commands.dossier import dossier_gates

    dossier_gates()


@order_app.command("estimate")
def order_estimate() -> None:
    """Estimate delivery date using community timing data.

    tesla order estimate
    tesla -j order estimate
    """
    from tesla_cli.cli.commands.dossier import dossier_estimate

    dossier_estimate()


@order_app.command("checklist")
def order_checklist(
    mark: str | None = typer.Option(None, "--mark", "-m", help="Mark items by number (comma-separated)"),
    reset: bool = typer.Option(False, "--reset", help="Reset all checkmarks"),
) -> None:
    """Tesla delivery inspection checklist (34 items).

    tesla order checklist
    tesla order checklist --mark 5,12,18
    tesla order checklist --reset
    """
    from tesla_cli.cli.commands.dossier import dossier_checklist

    dossier_checklist(mark=mark, reset=reset)


@order_app.command("ships")
def order_ships() -> None:
    """Track Tesla car carrier ships.

    tesla order ships
    tesla -j order ships
    """
    from tesla_cli.cli.commands.dossier import dossier_ships

    dossier_ships()


@order_app.command("set-delivery")
def order_set_delivery(
    date: str = typer.Argument(..., help="Delivery date (YYYY-MM-DD)"),
) -> None:
    """Set confirmed delivery date.

    tesla order set-delivery 2026-04-15
    """
    from tesla_cli.cli.commands.dossier import dossier_set_delivery

    dossier_set_delivery(date=date)


@order_app.command("documents")
def order_documents(
    download: bool = typer.Option(False, "--download", "-d", help="Download all documents"),
    output_dir: str = typer.Option(
        "~/.tesla-cli/documents", "--output", "-o", help="Download directory"
    ),
) -> None:
    """List or download documents from the Tesla ownership portal.

    Documents are extracted from the cached portal scrape data.
    Run the portal scrape first via the dashboard or API if no data is found.

    tesla order documents
    tesla order documents --download
    tesla order documents --download --output ~/Downloads/tesla-docs
    """
    import json as _json
    from pathlib import Path

    from tesla_cli.core.backends.order import OrderBackend

    # Load portal data from sources cache
    cache_path = Path.home() / ".tesla-cli" / "sources" / "tesla.portal.json"
    if not cache_path.exists():
        console.print(
            "[yellow]No portal data cached.[/yellow]\n\n"
            "To fetch portal data, run the portal scrape:\n"
            "  [bold]tesla order delivery --import[/bold] (for delivery details)\n"
            "  or trigger a full portal scrape via the dashboard.\n\n"
            f"[dim]Expected cache file: {cache_path}[/dim]"
        )
        raise typer.Exit(1)

    try:
        raw = _json.loads(cache_path.read_text())
        portal_data: dict = raw.get("data", raw)
    except Exception as e:
        console.print(f"[red]Failed to read portal cache:[/red] {e}")
        raise typer.Exit(1)

    backend = OrderBackend()
    docs = backend.get_portal_documents(portal_data)

    if not docs:
        console.print(
            "[yellow]No documents found in portal data.[/yellow]\n"
            "[dim]Tesla may not expose document URLs in the scraped page data "
            "for your account or order stage.[/dim]"
        )
        raise typer.Exit(0)

    if is_json_mode():
        console.print_json(_json.dumps([d.model_dump() for d in docs], indent=2))
        return

    # Display document list
    doc_rows = [
        {
            "name": d.name,
            "category": d.category or "(unknown)",
            "url": d.url[:60] + "..." if len(d.url) > 60 else d.url,
        }
        for d in docs
    ]
    render_table(doc_rows, columns=["name", "category", "url"], title=f"Portal Documents ({len(docs)})")

    if not download:
        console.print(
            f"\n[dim]Use [bold]--download[/bold] to save all {len(docs)} document(s) locally.[/dim]"
        )
        return

    # Download all documents
    out = Path(output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    console.print(f"\n[bold]Downloading {len(docs)} document(s) to {out}...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as progress:
        downloaded: list[dict] = []
        failed: list[dict] = []
        for doc in docs:
            task = progress.add_task(f"Downloading {doc.name}...", total=None)
            try:
                path = backend.download_document(doc, out)
                downloaded.append({"name": doc.name, "path": str(path)})
                progress.remove_task(task)
                console.print(f"  [green]✓[/green] {doc.name} → [dim]{path}[/dim]")
            except Exception as e:
                progress.remove_task(task)
                failed.append({"name": doc.name, "error": str(e)})
                render_warning(f"Failed to download {doc.name}: {e}")

    console.print(f"\n[bold]{len(downloaded)}/{len(docs)} document(s) downloaded to {out}[/bold]")
    if failed:
        console.print(f"[red]{len(failed)} failed.[/red]")
