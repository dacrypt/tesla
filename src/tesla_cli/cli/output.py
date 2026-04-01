"""Output helpers: Rich formatted display and JSON mode."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
error_console = Console(stderr=True)

# Global flag toggled by --json
_json_mode = False

# Global flag toggled by --anon (anonymize PII in output)
_anon_mode = False
_anon_targets: list[tuple[str, str]] = []  # (pattern, replacement)


def set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def is_json_mode() -> bool:
    return _json_mode


def set_anon_mode(enabled: bool, vin: str = "", rn: str = "", email: str = "", name: str = "") -> None:
    """Enable anonymization mode, masking PII in all output."""
    global _anon_mode, _anon_targets
    _anon_mode = enabled
    if enabled:
        _anon_targets = []
        if vin and len(vin) >= 8:
            # Keep first 4 and last 3 chars, mask the rest
            masked_vin = vin[:4] + "*" * (len(vin) - 7) + vin[-3:]
            _anon_targets.append((re.escape(vin), masked_vin))
        if rn:
            masked_rn = rn[:2] + "*" * max(0, len(rn) - 5) + rn[-3:] if len(rn) > 5 else rn[:2] + "***"
            _anon_targets.append((re.escape(rn), masked_rn))
        if email and "@" in email:
            local, domain = email.split("@", 1)
            masked_email = local[0] + "***@" + domain[0] + "***." + domain.split(".")[-1]
            _anon_targets.append((re.escape(email), masked_email))
        if name:
            parts = name.split()
            masked_name = " ".join(p[0] + "***" for p in parts)
            _anon_targets.append((re.escape(name), masked_name))


def is_anon_mode() -> bool:
    return _anon_mode


def anonymize(text: str) -> str:
    """Replace known PII patterns with masked versions."""
    if not _anon_mode or not text:
        return text
    for pattern, replacement in _anon_targets:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    # Also mask generic VIN-like patterns (17 alphanum) not already caught
    text = re.sub(r'\b[A-HJ-NPR-Z0-9]{17}\b', lambda m: m.group(0)[:4] + "***" + m.group(0)[-3:], text)
    return text


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
