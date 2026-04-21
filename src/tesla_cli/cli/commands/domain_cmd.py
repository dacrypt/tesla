"""tesla domain — derived domain projections from source-first state."""

from __future__ import annotations

import json

import typer

from tesla_cli.cli.output import console, is_json_mode
from tesla_cli.core import domains

domain_app = typer.Typer(
    name="domain",
    help="Derived domain projections built from source-first state.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@domain_app.command("list")
def domain_list() -> None:
    """List all derived domain projections."""
    from rich.table import Table, box

    items = domains.list_domains()

    if is_json_mode():
        console.print_json(json.dumps(items, indent=2, default=str))
        return

    table = Table(
        title="[bold]Derived Domains[/bold]",
        box=box.SIMPLE_HEAD,
        padding=(0, 1),
    )
    table.add_column("Domain", style="bold")
    table.add_column("Health", width=12)
    table.add_column("Summary")

    for item in items:
        health = item.get("health", {}).get("status", "missing")
        health_color = "green" if health == "ok" else "yellow" if health == "degraded" else "dim"
        table.add_row(
            item.get("domain_id", "-"),
            f"[{health_color}]{health}[/{health_color}]",
            item.get("summary", ""),
        )

    console.print()
    console.print(table)
    console.print()


@domain_app.command("show")
def domain_show(domain_id: str = typer.Argument(..., help="Domain id, e.g. delivery")) -> None:
    """Show one derived domain projection."""
    from rich.panel import Panel
    from rich.table import Table, box

    item = domains.get_domain(domain_id)
    if item is None:
        console.print(f"[red]Unknown domain:[/red] {domain_id}")
        raise typer.Exit(1)

    if is_json_mode():
        console.print_json(json.dumps(item, indent=2, default=str))
        return

    console.print()
    console.print(
        Panel(
            f"[bold cyan]{item['domain_id']}[/bold cyan]\n[dim]{item.get('summary', '')}[/dim]",
            border_style="cyan",
        )
    )

    state = item.get("state", {})
    flags = item.get("derived_flags", {})
    health = item.get("health", {})

    def _table(title: str, data: dict) -> None:
        if not data:
            return
        table = Table(title=title, box=box.SIMPLE_HEAD, padding=(0, 1))
        table.add_column("Key", style="dim", width=24)
        table.add_column("Value")
        for key, value in data.items():
            if value in (None, "", [], {}):
                continue
            table.add_row(
                key.replace("_", " "),
                json.dumps(value) if isinstance(value, (list, dict)) else str(value),
            )
        console.print(table)
        console.print()

    _table("State", state)
    _table("Flags", flags)
    _table("Health", health)
