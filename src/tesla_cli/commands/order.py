"""Order tracking commands: tesla order status/watch/details."""

from __future__ import annotations

import time

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from tesla_cli.backends.order import OrderBackend
from tesla_cli.config import load_config
from tesla_cli.output import (
    console,
    is_json_mode,
    render_dict,
    render_model,
    render_success,
    render_table,
    render_warning,
)

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
def order_status() -> None:
    """Check current order status."""
    rn = _get_rn()
    backend = OrderBackend()

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        transient=True, disable=is_json_mode(),
    ) as progress:
        progress.add_task(f"Fetching order {rn}...", total=None)
        status = backend.get_order_status(rn)

    render_model(status, title=f"Order {rn}")


@order_app.command("details")
def order_details() -> None:
    """Show full order details including tasks and configuration."""
    rn = _get_rn()
    backend = OrderBackend()

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        transient=True, disable=is_json_mode(),
    ) as progress:
        progress.add_task(f"Fetching order details {rn}...", total=None)
        details = backend.get_order_details(rn)

    # Show status
    render_model(details.status, title=f"Order {rn} - Status")

    # Show tasks
    if details.tasks:
        task_rows = []
        for t in details.tasks:
            task_rows.append({
                "task": t.task_name or t.task_type,
                "status": t.task_status,
                "completed": "Yes" if t.completed else ("Active" if t.active else "No"),
            })
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
    import_file: str = typer.Option(None, "--import", "-i", help="Import delivery data from a JSON file"),
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
                console.print(f"  [cyan]{c.field}[/cyan]: [red]{c.old_value or '(empty)'}[/red] -> [green]{c.new_value}[/green]")
        return

    if raw:
        cached = backend._load_delivery_cache()
        if cached:
            render_dict(cached, title="Raw Delivery Cache")
        else:
            console.print("[dim]No delivery cache. Import with: tesla order delivery --import ~/Downloads/tesla-delivery.json[/dim]")
        return

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        transient=True, disable=is_json_mode(),
    ) as progress:
        progress.add_task(f"Loading delivery details for {rn}...", total=None)
        appointment = backend.get_delivery_appointment(rn)

    if not appointment.appointment_text and appointment.raw.get("source") in ("no-data", "owner-api-fallback"):
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
                        console.print(f"  [cyan]{c.field}[/cyan]: [red]{c.old_value or '(empty)'}[/red] -> [green]{c.new_value}[/green]")
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
) -> None:
    """Watch for order status changes. Polls every N minutes."""
    rn = _get_rn()
    backend = OrderBackend()

    console.print(f"[bold]Watching order {rn}[/bold] (every {interval} min, Ctrl+C to stop)\n")

    # Initial fetch
    changes = backend.detect_changes(rn)
    if changes:
        _show_changes(changes, notify)
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
                SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task("Checking for changes...", total=None)
                changes = backend.detect_changes(rn)

            if changes:
                _show_changes(changes, notify)
            else:
                console.print(f"[dim]{time.strftime('%H:%M')} No changes[/dim]")

    except KeyboardInterrupt:
        console.print("\n[bold]Stopped watching.[/bold]")


def _show_changes(changes: list, notify: bool) -> None:
    """Display changes and optionally send notifications."""
    from rich.table import Table

    from tesla_cli.models.order import OrderChange

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
            table.add_row(sym, change.field, old or "[dim](empty)[/dim]", arrow, new or "[dim](empty)[/dim]")

    console.print(table)

    if notify:
        _send_notification(changes)


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

    from tesla_cli.backends.dossier import DossierBackend

    backend = DossierBackend()
    history = backend.get_history()

    if not history:
        console.print("[yellow]No dossier history found. Run: tesla dossier build[/yellow]")
        raise typer.Exit(1)

    # Build timeline: compare consecutive snapshots
    TRACK_FIELDS = [
        "order_status", "vin", "delivery_date", "delivery_window_display",
        "runt_status", "in_runt", "has_placa",
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

        timeline.append({
            "timestamp": ts,
            "order_status": status,
            "changes": changes,
        })
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
