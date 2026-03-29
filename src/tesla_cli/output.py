"""Output helpers: Rich formatted display and JSON mode."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
error_console = Console(stderr=True)

# Global flag toggled by --json
_json_mode = False


def set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def is_json_mode() -> bool:
    return _json_mode


def render_model(data: BaseModel, title: str = "") -> None:
    """Render a pydantic model as Rich panel or JSON."""
    if _json_mode:
        console.print(data.model_dump_json(indent=2))
        return
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    for field_name, value in data.model_dump().items():
        display_name = field_name.replace("_", " ").title()
        table.add_row(display_name, _format_value(value))
    console.print(Panel(table, title=f"[bold]{title}[/bold]" if title else "", border_style="blue"))


def render_dict(data: dict[str, Any], title: str = "") -> None:
    """Render a dict as Rich panel or JSON."""
    if _json_mode:
        console.print(json.dumps(data, indent=2, default=str))
        return
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    for key, value in data.items():
        display_name = key.replace("_", " ").title()
        table.add_row(display_name, _format_value(value))
    console.print(Panel(table, title=f"[bold]{title}[/bold]" if title else "", border_style="blue"))


def render_table(
    rows: list[dict[str, Any]], columns: list[str], title: str = ""
) -> None:
    """Render a list of dicts as Rich table or JSON array."""
    if _json_mode:
        console.print(json.dumps(rows, indent=2, default=str))
        return
    table = Table(title=title, border_style="blue")
    for col in columns:
        table.add_column(col.replace("_", " ").title(), style="cyan")
    for row in rows:
        table.add_row(*[_format_value(row.get(c, "")) for c in columns])
    console.print(table)


def render_success(message: str) -> None:
    if _json_mode:
        console.print(json.dumps({"status": "ok", "message": message}))
    else:
        console.print(f"[bold green]OK[/bold green] {message}")


def render_error(message: str, error_type: str = "Error") -> None:
    if _json_mode:
        error_console.print(json.dumps({"error": message, "type": error_type}))
    else:
        error_console.print(Panel(message, title=f"[bold red]{error_type}[/bold red]", border_style="red"))


def render_warning(message: str) -> None:
    if _json_mode:
        return
    console.print(f"[bold yellow]WARNING[/bold yellow] {message}")


def _format_value(value: Any) -> str:
    if value is None:
        return "[dim]--[/dim]"
    if isinstance(value, bool):
        return "[green]Yes[/green]" if value else "[red]No[/red]"
    if isinstance(value, dict):
        return json.dumps(value, default=str)
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "[dim]--[/dim]"
    return str(value)
