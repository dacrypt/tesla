"""Top-level CLI surfaces for source-first events and alerts."""

from __future__ import annotations

import json

import typer

from tesla_cli.cli.output import console, is_json_mode
from tesla_cli.core import events as event_store


def alerts_command(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum alerts to show"),
    all_alerts: bool = typer.Option(False, "--all", help="Include resolved alerts"),
    ack: str = typer.Option("", "--ack", help="Acknowledge one alert id"),
) -> None:
    """Show source/domain alerts or acknowledge one."""
    from rich.table import Table, box

    if ack:
        result = event_store.ack_alert(ack)
        if result is None:
            console.print(f"[red]Unknown alert:[/red] {ack}")
            raise typer.Exit(1)
        if is_json_mode():
            console.print_json(json.dumps(result, indent=2, default=str))
            return
        console.print(f"[green]Acknowledged:[/green] {result['alert_id']}")
        return

    rows = event_store.list_alerts(limit=limit, active_only=not all_alerts)
    if is_json_mode():
        console.print_json(json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        console.print("[dim]No alerts.[/dim]")
        return

    table = Table(title="[bold]Alerts[/bold]", box=box.SIMPLE_HEAD, padding=(0, 1))
    table.add_column("Severity", width=10)
    table.add_column("Title", width=18)
    table.add_column("Message")
    table.add_column("State", width=12)
    table.add_column("When", width=19)

    for row in rows:
        severity = row.get("severity", "info")
        color = "red" if severity == "critical" else "yellow" if severity in {"high", "warning"} else "cyan"
        state = "resolved" if row.get("resolved_at") else "acked" if row.get("acked_at") else "active"
        table.add_row(
            f"[{color}]{severity}[/{color}]",
            row.get("title", "-"),
            row.get("message", ""),
            state,
            str(row.get("created_at", ""))[:19],
        )

    console.print()
    console.print(table)
    console.print()


def events_command(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum events to show"),
) -> None:
    """Show recent source/domain events."""
    from rich.table import Table, box

    rows = event_store.list_events(limit=limit)
    if is_json_mode():
        console.print_json(json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        console.print("[dim]No events.[/dim]")
        return

    table = Table(title="[bold]Events[/bold]", box=box.SIMPLE_HEAD, padding=(0, 1))
    table.add_column("Kind", width=14)
    table.add_column("Title", width=18)
    table.add_column("Message")
    table.add_column("When", width=19)

    for row in rows:
        kind = row.get("kind", "-")
        color = "cyan" if kind == "domain_change" else "yellow" if kind == "source_change" else "dim"
        table.add_row(
            f"[{color}]{kind}[/{color}]",
            row.get("title", "-"),
            row.get("message", ""),
            str(row.get("created_at", row.get("timestamp", "")))[:19],
        )

    console.print()
    console.print(table)
    console.print()
