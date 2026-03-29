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
    from tesla_cli.models.order import OrderChange

    console.print(f"\n[bold yellow]Changes detected at {time.strftime('%H:%M:%S')}:[/bold yellow]")
    for change in changes:
        if isinstance(change, OrderChange):
            console.print(
                f"  [cyan]{change.field}[/cyan]: "
                f"[red]{change.old_value or '(empty)'}[/red] -> "
                f"[green]{change.new_value}[/green]"
            )

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
