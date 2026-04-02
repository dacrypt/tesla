"""RUNT commands: tesla runt query — query Colombia's vehicle registry.

Enriched with additional openquery sources when available:
  • co.simit       — traffic fines for the same plate
  • co.pico_y_placa — driving restriction
  • co.fasecolda   — vehicle reference price
"""

from __future__ import annotations

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.cli.output import console, is_json_mode
from tesla_cli.core.config import load_config, resolve_vin

runt_app = typer.Typer(name="runt", help="RUNT — Colombia vehicle registry queries.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN to query (uses default if omitted)")
PlateOption = typer.Option(None, "--placa", "-p", help="License plate to query")
EnrichOption = typer.Option(
    True, "--enrich/--no-enrich", help="Pull SIMIT, pico y placa and FASECOLDA data (default: on)"
)


@runt_app.command("query")
def runt_query(
    vin: str | None = VinOption,
    placa: str | None = PlateOption,
    enrich: bool = EnrichOption,
) -> None:
    """Query RUNT for vehicle data by VIN or plate.

    Automatically enriches the result with SIMIT traffic fines,
    pico y placa driving restrictions, and FASECOLDA reference price
    when openquery is available and --enrich is enabled (default).
    """
    from tesla_cli.core.backends.runt import RuntBackend, RuntError

    backend = RuntBackend()

    if placa:
        query_label = f"placa {placa}"
        query_fn = lambda: backend.query_by_plate(placa)
    else:
        v = vin or resolve_vin(load_config(), None)
        query_label = f"VIN {v}"
        placa = None  # no plate for enrichment
        query_fn = lambda: backend.query_by_vin(v)

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as p:
        p.add_task(f"Querying RUNT for {query_label}…", total=None)
        try:
            data = query_fn()
        except RuntError as e:
            console.print(f"[red]RUNT query failed: {e}[/red]")
            raise typer.Exit(1)

    # Resolve plate for enrichment queries
    effective_placa = placa or data.placa or None

    if is_json_mode():
        import json as _json

        output = data.model_dump()
        if enrich and effective_placa:
            output["enrichment"] = _fetch_enrichment_json(
                effective_placa, data.marca, data.modelo_ano
            )
        console.print(_json.dumps(output, indent=2, default=str))
        return

    # ── Main RUNT table ───────────────────────────────────────────────────────
    table = Table(title=f"RUNT — {query_label}", show_header=False, border_style="green")
    table.add_column("Campo", style="bold cyan", width=24)
    table.add_column("Valor")

    def _row(label: str, value: str, *, ok: bool | None = None) -> None:
        if ok is True:
            val = f"[green]{value} ✓[/green]"
        elif ok is False:
            val = f"[red]{value} ✗[/red]"
        elif not value or value in ("—", "0"):
            val = f"[dim]{value or '—'}[/dim]"
        else:
            val = value
        table.add_row(label, val)

    _row("Estado", data.estado)
    _row("Placa", data.placa or "—")
    _row("Marca", data.marca)
    _row("Línea", data.linea)
    _row("Modelo (año)", data.modelo_ano)
    _row("Color", data.color)
    _row("Clase", data.clase_vehiculo)
    _row("Tipo servicio", data.tipo_servicio or "—")
    _row("Combustible", data.tipo_combustible)
    _row("Carrocería", data.tipo_carroceria)
    _row("VIN", data.numero_vin)
    _row("Chasis", data.numero_chasis)
    _row("Motor", data.numero_motor or "—")
    _row("Cilindraje", data.cilindraje)
    _row("Puertas", str(data.puertas) if data.puertas else "—")
    _row("Peso bruto (kg)", str(data.peso_bruto_kg) if data.peso_bruto_kg else "—")
    _row("Pasajeros", str(data.capacidad_pasajeros) if data.capacidad_pasajeros else "—")
    _row("Ejes", str(data.numero_ejes) if data.numero_ejes else "—")

    # Legal status with colour coding
    _row("Gravámenes", "Sí" if data.gravamenes else "No", ok=not data.gravamenes)
    _row("Prendas", "Sí" if data.prendas else "No", ok=not data.prendas)
    _row("Repotenciado", "Sí" if data.repotenciado else "No")

    # SOAT & RTM (from openquery's richer RuntResult)
    soat_vigente = getattr(data, "soat_vigente", None)
    soat_aseg = getattr(data, "soat_aseguradora", "") or ""
    soat_venc = getattr(data, "soat_vencimiento", "") or ""
    rtm_vigente = getattr(data, "tecnomecanica_vigente", None)
    rtm_venc = getattr(data, "tecnomecanica_vencimiento", "") or ""

    if soat_vigente is not None:
        soat_label = (
            "Sí"
            + (f" — {soat_aseg}" if soat_aseg else "")
            + (f" (vence {soat_venc})" if soat_venc else "")
        )
        _row("SOAT vigente", soat_label if soat_vigente else "No", ok=soat_vigente)
    if rtm_vigente is not None:
        rtm_label = "Sí" + (f" (vence {rtm_venc})" if rtm_venc else "")
        _row("Tecnomecánica", rtm_label if rtm_vigente else "No", ok=rtm_vigente)

    _row("Fecha matrícula", data.fecha_matricula or "—")
    _row("Autoridad tránsito", data.autoridad_transito or "—")
    _row("País origen", data.nombre_pais or "—")
    _row("Consultado", str(data.queried_at.strftime("%Y-%m-%d %H:%M:%S")))

    console.print(table)

    # ── Enrichment panels ─────────────────────────────────────────────────────
    if enrich and effective_placa:
        _show_enrichment(effective_placa, data.marca, data.modelo_ano)


# ─── Enrichment helpers ───────────────────────────────────────────────────────


def _fetch_enrichment_json(placa: str, marca: str, modelo_ano: str) -> dict:
    """Fetch enrichment data as plain dicts (for JSON mode)."""
    result: dict = {}
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput
    except ImportError:
        return result

    # SIMIT fines
    try:
        simit = get_source("co.simit").query(
            QueryInput(document_type=DocumentType.PLATE, document_number=placa)
        )
        result["simit"] = simit.model_dump(exclude={"audit"})
    except Exception:
        pass

    # Pico y placa
    try:
        pyp = get_source("co.pico_y_placa").query(
            QueryInput(document_type=DocumentType.PLATE, document_number=placa)
        )
        result["pico_y_placa"] = pyp.model_dump(exclude={"audit"})
    except Exception:
        pass

    # FASECOLDA reference price
    if marca:
        try:
            fasec = get_source("co.fasecolda").query(
                QueryInput(
                    document_type=DocumentType.CUSTOM,
                    document_number="",
                    extra={"marca": marca, "modelo": modelo_ano},
                )
            )
            result["fasecolda"] = fasec.model_dump(exclude={"audit"})
        except Exception:
            pass

    return result


def _show_enrichment(placa: str, marca: str, modelo_ano: str) -> None:
    """Query SIMIT, pico y placa and FASECOLDA and print summary panels."""
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput
    except ImportError:
        return  # openquery not installed — skip silently

    console.print()

    # ── SIMIT (multas) ────────────────────────────────────────────────────────
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[dim]{task.description}"),
            transient=True,
            disable=is_json_mode(),
        ) as p:
            p.add_task(f"SIMIT — multas placa {placa}…", total=None)
            simit = get_source("co.simit").query(
                QueryInput(document_type=DocumentType.PLATE, document_number=placa)
            )

        _print_simit_panel(simit, placa)
    except Exception as exc:
        console.print(f"[dim]SIMIT: {exc}[/dim]")

    # ── Pico y placa ──────────────────────────────────────────────────────────
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[dim]{task.description}"),
            transient=True,
            disable=is_json_mode(),
        ) as p:
            p.add_task(f"Pico y placa — {placa}…", total=None)
            pyp = get_source("co.pico_y_placa").query(
                QueryInput(document_type=DocumentType.PLATE, document_number=placa)
            )

        _print_pyp_panel(pyp, placa)
    except Exception as exc:
        console.print(f"[dim]Pico y placa: {exc}[/dim]")

    # ── FASECOLDA (precio de referencia) ──────────────────────────────────────
    if marca:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[dim]{task.description}"),
                transient=True,
                disable=is_json_mode(),
            ) as p:
                p.add_task(f"FASECOLDA — {marca} {modelo_ano}…", total=None)
                fasec = get_source("co.fasecolda").query(
                    QueryInput(
                        document_type=DocumentType.CUSTOM,
                        document_number="",
                        extra={"marca": marca, "modelo": modelo_ano},
                    )
                )

            _print_fasecolda_panel(fasec, marca, modelo_ano)
        except Exception as exc:
            console.print(f"[dim]FASECOLDA: {exc}[/dim]")


def _print_simit_panel(simit, placa: str) -> None:
    border = "green" if simit.paz_y_salvo else "red"
    t = Table(
        title=f"SIMIT — multas placa {placa}",
        show_header=False,
        border_style=border,
        box=None,
        padding=(0, 2),
    )
    t.add_column("k", style="bold dim", width=22)
    t.add_column("v")

    status = "[green]✓ PAZ Y SALVO[/green]" if simit.paz_y_salvo else "[red]✗ TIENE MULTAS[/red]"
    t.add_row("Estado", status)
    if simit.comparendos:
        t.add_row("Comparendos", f"[red]{simit.comparendos}[/red]")
    if simit.multas:
        t.add_row("Multas", f"[red]{simit.multas}[/red]")
    if simit.total_deuda:
        t.add_row("Deuda total", f"[bold red]$ {simit.total_deuda:,.0f}[/bold red]")
    console.print(t)


def _print_pyp_panel(pyp, placa: str) -> None:
    d = pyp.model_dump(exclude={"audit", "queried_at"})
    t = Table(
        title=f"Pico y Placa — {placa}",
        show_header=False,
        border_style="yellow",
        box=None,
        padding=(0, 2),
    )
    t.add_column("k", style="bold dim", width=22)
    t.add_column("v")
    for k, v in d.items():
        if v is None or v == "":
            continue
        if isinstance(v, bool):
            v = "[red]Sí ✗[/red]" if v else "[green]No ✓[/green]"
        t.add_row(k.replace("_", " ").title(), str(v))
    console.print(t)


def _print_fasecolda_panel(fasec, marca: str, modelo_ano: str) -> None:
    d = fasec.model_dump(exclude={"audit", "queried_at"})
    t = Table(
        title=f"FASECOLDA — {marca} {modelo_ano}",
        show_header=False,
        border_style="blue",
        box=None,
        padding=(0, 2),
    )
    t.add_column("k", style="bold dim", width=22)
    t.add_column("v")
    for k, v in d.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, list):
            v = f"({len(v)} items)"
        t.add_row(k.replace("_", " ").title(), str(v))
    console.print(t)
