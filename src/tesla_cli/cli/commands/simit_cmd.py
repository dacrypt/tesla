"""SIMIT commands: tesla simit query — query Colombia's traffic fines system."""

from __future__ import annotations

import os

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.cli.output import console, is_json_mode

simit_app = typer.Typer(name="simit", help="SIMIT — Colombia traffic fines queries.")

CedulaOption = typer.Option(None, "--cedula", "-c", help="Cédula number to query")
PlacaOption = typer.Option(None, "--placa", "-p", help="License plate to query")

DEFAULT_CEDULA = os.environ.get("TESLA_OWNER_CEDULA", "")


def _resolve_cedula() -> str:
    """Try to get cédula from Tesla tasks data, fallback to default."""
    import json
    from pathlib import Path

    # Try dossier file for owner info
    dossier_file = Path.home() / ".tesla-cli" / "dossier" / "dossier.json"
    if dossier_file.exists():
        try:
            dossier = json.loads(dossier_file.read_text())
            # Check for owner ID in raw snapshots
            for snap in dossier.get("raw_snapshots", []):
                tasks = snap.get("tasks", {})
                reg = tasks.get("registration", {})
                reg_data = reg.get("regData", {}).get("regDetails", {})
                owner = reg_data.get("owner", {}).get("user", {})
                if owner.get("idNumber"):
                    return owner["idNumber"]
        except Exception:
            pass

    # Try mission-control-data.json
    mc_file = Path(__file__).parent.parent.parent.parent / "mission-control-data.json"
    if mc_file.exists():
        try:
            mc = json.loads(mc_file.read_text())
            if mc.get("simit_cedula"):
                return mc["simit_cedula"]
        except Exception:
            pass

    return DEFAULT_CEDULA


EnrichOption = typer.Option(
    True, "--enrich/--no-enrich",
    help="Also query Procuraduría and Policía when querying by cédula (default: on)",
)


@simit_app.command("query")
def simit_query(
    cedula: str | None = CedulaOption,
    placa: str | None = PlacaOption,
    enrich: bool = EnrichOption,
) -> None:
    """Query SIMIT for traffic fines by cédula or plate.

    When querying by cédula and openquery is installed, also shows
    Procuraduría (disciplinary) and Policía (criminal) background records.
    """
    from tesla_cli.core.backends.simit import SimitBackend, SimitError

    backend = SimitBackend()

    if placa:
        label = f"placa {placa}"
        query_fn = lambda: backend.query_by_placa(placa)
    else:
        c = cedula or _resolve_cedula()
        label = f"cédula {c}"
        query_fn = lambda: backend.query_by_cedula(c)

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as p:
        p.add_task(f"Querying SIMIT for {label}...", total=None)
        try:
            data = query_fn()
        except SimitError as e:
            console.print(f"[red]SIMIT query failed: {e}[/red]")
            raise typer.Exit(1)

    if is_json_mode():
        console.print(data.model_dump_json(indent=2))
        return

    # Rich table display
    if data.paz_y_salvo:
        console.print(f"\n[bold green]✅ PAZ Y SALVO[/bold green] — {label}\n")
    else:
        console.print(f"\n[bold red]⚠️  FINES FOUND[/bold red] — {label}\n")

    table = Table(title=f"SIMIT — {label}", show_header=False, border_style="green" if data.paz_y_salvo else "red")
    table.add_column("Campo", style="bold cyan", width=22)
    table.add_column("Valor")

    table.add_row("Cédula / Placa", data.cedula)
    table.add_row("Comparendos", str(data.comparendos))
    table.add_row("Multas", str(data.multas))
    table.add_row("Acuerdos de pago", str(data.acuerdos_pago))

    total_style = "green" if data.total_deuda == 0 else "bold red"
    table.add_row("Total deuda", f"[{total_style}]$ {data.total_deuda:,.0f}[/{total_style}]")
    table.add_row("Paz y salvo", "[green]Sí[/green]" if data.paz_y_salvo else "[red]No[/red]")
    table.add_row("Consultado", str(data.queried_at.strftime("%Y-%m-%d %H:%M:%S")))

    console.print(table)

    # Show historial if available
    if data.historial:
        console.print()
        hist_table = Table(title=f"Historial ({len(data.historial)} registros)", border_style="blue")
        hist_table.add_column("Comparendo", style="dim")
        hist_table.add_column("Secretaría")
        hist_table.add_column("Fecha curso")
        hist_table.add_column("Ciudad")
        hist_table.add_column("Centro")
        hist_table.add_column("Estado")

        for record in data.historial:
            hist_table.add_row(
                record.get("comparendo", "")[:20] + "..." if len(record.get("comparendo", "")) > 20 else record.get("comparendo", ""),
                record.get("secretaria", ""),
                record.get("fecha_curso", ""),
                record.get("ciudad", ""),
                record.get("centro_instruccion", ""),
                record.get("estado", ""),
            )

        console.print(hist_table)

    # ── Enrichment: Procuraduría + Policía (cédula queries only) ─────────────
    effective_cedula = None if placa else (cedula or _resolve_cedula())
    if enrich and effective_cedula:
        _show_background_checks(effective_cedula)


def _show_background_checks(cedula: str) -> None:
    """Query Procuraduría and Policía antecedentes via openquery."""
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput
    except ImportError:
        return  # openquery not installed — skip silently

    console.print()

    for source_name, title in [
        ("co.procuraduria", "Procuraduría — antecedentes disciplinarios"),
        ("co.policia",      "Policía — antecedentes judiciales"),
    ]:
        try:
            with Progress(SpinnerColumn(), TextColumn("[dim]{task.description}"),
                          transient=True, disable=is_json_mode()) as p:
                p.add_task(f"{title}…", total=None)
                result = get_source(source_name).query(
                    QueryInput(document_type=DocumentType.CEDULA, document_number=cedula))

            d = result.model_dump(exclude={"audit", "queried_at"})
            t = Table(title=title, show_header=False, box=None, padding=(0, 2),
                      border_style="green" if d.get("sin_antecedentes") else "yellow")
            t.add_column("k", style="bold dim", width=28)
            t.add_column("v")
            for k, v in d.items():
                if v is None or v == "" or v == []:
                    continue
                if isinstance(v, bool):
                    v_str = ("[green]Sí ✓[/green]" if v else "[red]No ✗[/red]")
                elif isinstance(v, list):
                    v_str = f"[dim]({len(v)} items)[/dim]"
                else:
                    v_str = str(v)
                t.add_row(k.replace("_", " ").title(), v_str)
            console.print(t)
        except Exception as exc:
            console.print(f"[dim]{title}: {exc}[/dim]")
        console.print()
