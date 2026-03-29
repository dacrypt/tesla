"""RUNT commands: tesla runt query — query Colombia's vehicle registry."""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.config import load_config, resolve_vin
from tesla_cli.output import console, is_json_mode

runt_app = typer.Typer(name="runt", help="RUNT — Colombia vehicle registry queries.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN to query (uses default if omitted)")
PlateOption = typer.Option(None, "--placa", "-p", help="License plate to query")


@runt_app.command("query")
def runt_query(
    vin: Optional[str] = VinOption,
    placa: Optional[str] = PlateOption,
) -> None:
    """Query RUNT for vehicle data by VIN or plate."""
    from tesla_cli.backends.runt import RuntBackend, RuntError

    backend = RuntBackend()

    if placa:
        label = f"plate {placa}"
        query_fn = lambda: backend.query_by_plate(placa)
    else:
        v = vin or resolve_vin(load_config(), None)
        label = f"VIN {v}"
        query_fn = lambda: backend.query_by_vin(v)

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as p:
        p.add_task(f"Querying RUNT for {label}...", total=None)
        try:
            data = query_fn()
        except RuntError as e:
            console.print(f"[red]RUNT query failed: {e}[/red]")
            raise typer.Exit(1)

    if is_json_mode():
        console.print(data.model_dump_json(indent=2))
        return

    # Rich table display
    table = Table(title=f"RUNT — {label}", show_header=False, border_style="green")
    table.add_column("Campo", style="bold cyan", width=22)
    table.add_column("Valor")

    fields = [
        ("Estado", data.estado),
        ("Placa", data.placa or "—"),
        ("Marca", data.marca),
        ("Línea", data.linea),
        ("Modelo (año)", data.modelo_ano),
        ("Color", data.color),
        ("Clase", data.clase_vehiculo),
        ("Tipo servicio", data.tipo_servicio or "—"),
        ("Combustible", data.tipo_combustible),
        ("Carrocería", data.tipo_carroceria),
        ("VIN", data.numero_vin),
        ("Chasis", data.numero_chasis),
        ("Cilindraje", data.cilindraje),
        ("Puertas", str(data.puertas)),
        ("Peso bruto (kg)", str(data.peso_bruto_kg)),
        ("Pasajeros", str(data.capacidad_pasajeros)),
        ("Ejes", str(data.numero_ejes)),
        ("Gravámenes", "Sí" if data.gravamenes else "No"),
        ("SOAT vigente", "Sí" if data.soat_vigente else "No"),
        ("SOAT aseguradora", data.soat_aseguradora or "—"),
        ("RTM vigente", "Sí" if data.tecnomecanica_vigente else "No"),
        ("Fecha matrícula", data.fecha_matricula or "—"),
        ("Autoridad tránsito", data.autoridad_transito or "—"),
        ("Consultado", str(data.queried_at)),
    ]

    for label_text, value in fields:
        if value and value != "—" and value != "0":
            table.add_row(label_text, value)
        else:
            table.add_row(label_text, f"[dim]{value}[/dim]")

    console.print(table)
