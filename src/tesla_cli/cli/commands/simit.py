"""SIMIT commands: tesla simit query."""

from __future__ import annotations

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.cli.output import console, is_json_mode
from tesla_cli.core.backends.dossier import DossierBackend
from tesla_cli.core.backends.simit import SimitBackend, SimitError
from tesla_cli.core.config import load_config
from tesla_cli.core.sources import get_cached

simit_app = typer.Typer(name="simit", help="SIMIT, Colombia traffic fines.")


def _resolve_default_cedula() -> str:
    dossier = DossierBackend()._load_dossier()
    if dossier and dossier.runt.no_identificacion:
        return dossier.runt.no_identificacion

    cfg = load_config()
    if cfg.general.cedula:
        return cfg.general.cedula

    runt_cache = get_cached("co.runt") or {}
    if runt_cache.get("no_identificacion"):
        return runt_cache["no_identificacion"]

    raise typer.BadParameter(
        "No cédula found. Pass --cedula, or configure general.cedula, or build the dossier first."
    )


@simit_app.command("query")
def simit_query(
    cedula: str | None = typer.Option(None, "--cedula", "-c", help="Cédula to query"),
    placa: str | None = typer.Option(None, "--placa", "-p", help="License plate to query"),
) -> None:
    """Query SIMIT by cédula or plate."""
    backend = SimitBackend(timeout=30.0)

    if placa:
        label = f"placa {placa}"
        fn = lambda: backend.query_by_placa(placa)
    else:
        doc = cedula or _resolve_default_cedula()
        label = f"cédula {doc}"
        fn = lambda: backend.query_by_cedula(doc)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as progress:
        progress.add_task(f"Querying SIMIT for {label}...", total=None)
        try:
            data = fn()
        except SimitError as exc:
            console.print(f"[red]SIMIT query failed:[/red] {exc}")
            raise typer.Exit(1)

    if is_json_mode():
        console.print_json(data.model_dump_json(indent=2))
        return

    table = Table(title=f"SIMIT, {label}", show_header=False, border_style="green")
    table.add_column("Field", style="bold cyan", width=22)
    table.add_column("Value")
    table.add_row("Comparendos", str(data.comparendos))
    table.add_row("Multas", str(data.multas))
    table.add_row("Acuerdos de pago", str(data.acuerdos_pago))
    table.add_row("Total deuda", f"$ {data.total_deuda:,.0f}")
    table.add_row("Paz y salvo", "Sí" if data.paz_y_salvo else "No")
    table.add_row("Consultado", data.queried_at.strftime("%Y-%m-%d %H:%M:%S"))
    console.print(table)

    if data.historial:
        hist = Table(title=f"Historial ({len(data.historial)})", border_style="blue")
        hist.add_column("Comparendo")
        hist.add_column("Secretaría")
        hist.add_column("Fecha curso")
        hist.add_column("Ciudad")
        hist.add_column("Estado")
        for row in data.historial:
            hist.add_row(
                row.get("comparendo", ""),
                row.get("secretaria", ""),
                row.get("fecha_curso", ""),
                row.get("ciudad", ""),
                row.get("estado", ""),
            )
        console.print(hist)
