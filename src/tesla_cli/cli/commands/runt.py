"""RUNT commands."""

from __future__ import annotations

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.cli.output import console, is_json_mode
from tesla_cli.core.backends.runt import RuntBackend, RuntError
from tesla_cli.core.config import load_config, resolve_vin

runt_app = typer.Typer(name="runt", help="RUNT vehicle registry queries.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias (uses default if omitted)")
PlateOption = typer.Option(None, "--plate", "--placa", "-p", help="License plate")


def _render_runt_table(data) -> None:
    table = Table(title="RUNT", show_header=False)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    rows = [
        ("Estado", data.estado),
        ("Placa", data.placa or "-"),
        ("Marca", data.marca),
        ("Línea", data.linea),
        ("Modelo", data.modelo_ano),
        ("Clase", data.clase_vehiculo),
        ("Servicio", data.tipo_servicio or "-"),
        ("Color", data.color),
        ("Combustible", data.tipo_combustible),
        ("Carrocería", data.tipo_carroceria),
        ("VIN", data.numero_vin),
        ("Chasis", data.numero_chasis),
        ("Puertas", str(data.puertas)),
        ("Peso bruto", f"{data.peso_bruto_kg} kg" if data.peso_bruto_kg else "-"),
        ("Pasajeros", str(data.capacidad_pasajeros or "-")),
        ("Ejes", str(data.numero_ejes or "-")),
        ("Gravámenes", "Sí" if data.gravamenes else "No"),
        ("SOAT", "Vigente" if data.soat_vigente else "No registrado"),
        (
            "Tecnomecánica",
            "Vigente" if data.tecnomecanica_vigente else (data.tecnomecanica_vencimiento or "No aplica / no registrada"),
        ),
        ("Fecha matrícula", data.fecha_matricula or "-"),
        ("Autoridad", data.autoridad_transito or "-"),
    ]
    for key, value in rows:
        table.add_row(key, value)
    console.print(table)


@runt_app.command("query")
def runt_query(vin: str | None = VinOption, plate: str | None = PlateOption) -> None:
    """Query RUNT by VIN or plate."""
    backend = RuntBackend()

    if plate:
        label = plate
        query = lambda: backend.query_by_plate(plate)
    else:
        resolved_vin = resolve_vin(load_config(), vin)
        label = resolved_vin
        query = lambda: backend.query_by_vin(resolved_vin)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), transient=True, disable=is_json_mode()
    ) as p:
        p.add_task(f"Querying RUNT for {label}...", total=None)
        try:
            data = query()
        except RuntError as exc:
            console.print(f"[red]RUNT query failed:[/red] {exc}")
            raise typer.Exit(1) from exc

    if is_json_mode():
        console.print_json(data.model_dump_json(indent=2, exclude_none=True))
        return

    _render_runt_table(data)
