"""tesla query — Query Colombian public data sources via openquery.

Usage examples:
    tesla query sources                          # list all available sources
    tesla query simit --cedula 12345678          # SIMIT traffic fines
    tesla query runt --placa ABC123              # RUNT vehicle registry (plate)
    tesla query runt --vin LRWYGCEK3TC512197     # RUNT vehicle registry (VIN)
    tesla query procuraduria --cedula 12345678   # disciplinary records
    tesla query policia --cedula 12345678        # criminal background
    tesla query adres --cedula 12345678          # health system (EPS)
    tesla query pico-y-placa --placa ABC123      # driving restrictions
    tesla query vehiculos --placa ABC123         # national vehicle fleet
    tesla query run co.combustible --extra '{"municipio": "BOGOTA"}'
    tesla query run co.estaciones-ev --extra '{"ciudad": "Medellin"}'
    tesla query run co.fasecolda --extra '{"marca": "TESLA", "modelo": "2026"}'
"""

from __future__ import annotations

import json as _json
import time

import typer
from rich.table import Table

from tesla_cli.cli.output import console, is_json_mode

query_app = typer.Typer(
    name="query",
    help="Query Colombian public data sources via [bold]openquery[/bold].",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# ─── Install hint ─────────────────────────────────────────────────────────────

_NOT_INSTALLED = (
    "[red]✗[/red] [bold]openquery[/bold] is not installed.\n"
    "  Install: [bold cyan]pip install 'tesla-cli[query]'[/bold cyan]"
    "  or:      [bold cyan]uv add openquery[/bold cyan]"
)

# ─── Common options ───────────────────────────────────────────────────────────

CedulaOption  = typer.Option(None, "--cedula", "-c", help="Cédula / national ID number")
PlacaOption   = typer.Option(None, "--placa",  "-p", help="License plate (e.g. ABC123)")
VinOption     = typer.Option(None, "--vin",    "-v", help="VIN number")
ExtraOption   = typer.Option(None, "--extra",  "-e", help='Extra params as JSON, e.g. \'{"ciudad":"Bogota"}\'')
AuditOption   = typer.Option(False, "--audit", "-a", help="Capture audit evidence (screenshots + PDF)")
AuditDirOpt   = typer.Option(None, "--audit-dir", help="Directory for audit files (default: ./audit)")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _require_openquery() -> None:
    try:
        import openquery  # noqa: F401
    except ImportError:
        console.print(_NOT_INSTALLED)
        raise typer.Exit(1)


def _build_input(
    cedula: str | None,
    placa: str | None,
    vin: str | None,
    extra_json: str | None = None,
    audit: bool = False,
):
    from openquery.sources.base import DocumentType, QueryInput

    extra: dict = {}
    if extra_json:
        try:
            extra = _json.loads(extra_json)
        except _json.JSONDecodeError as exc:
            console.print(f"[red]--extra must be valid JSON:[/red] {exc}")
            raise typer.Exit(1)

    if cedula:
        return QueryInput(document_type=DocumentType.CEDULA, document_number=cedula,
                          extra=extra, audit=audit)
    if placa:
        return QueryInput(document_type=DocumentType.PLATE, document_number=placa,
                          extra=extra, audit=audit)
    if vin:
        return QueryInput(document_type=DocumentType.VIN, document_number=vin,
                          extra=extra, audit=audit)
    if extra:
        return QueryInput(document_type=DocumentType.CUSTOM, document_number="",
                          extra=extra, audit=audit)

    console.print("[red]Provide at least one of: --cedula, --placa, --vin, or --extra[/red]")
    raise typer.Exit(1)


def _run(source_name: str, q_input, audit_dir: str | None = None) -> None:
    """Dispatch query to openquery source and display results."""
    from openquery.sources import get_source

    try:
        src = get_source(source_name)
    except KeyError:
        from openquery.sources import list_sources
        available = ", ".join(sorted(s.meta().name for s in list_sources()))
        console.print(f"[red]Unknown source:[/red] {source_name!r}\n"
                      f"[dim]Available: {available}[/dim]")
        raise typer.Exit(1)

    meta = src.meta()
    label = q_input.document_number or source_name

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as prog:
        prog.add_task(f"Querying {meta.display_name}…", total=None)
        t0 = time.monotonic()
        try:
            result = src.query(q_input)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]✗ {meta.display_name} failed:[/red] {exc}")
            raise typer.Exit(1)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

    # ── JSON output ──
    if is_json_mode():
        console.print(result.model_dump_json(indent=2))
        return

    # ── Rich table ──
    data = result.model_dump(exclude={"audit", "queried_at", "historial"})
    t = Table(
        title=f"[bold]{meta.display_name}[/bold] — {label}  [dim]({elapsed_ms} ms)[/dim]",
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    t.add_column("key", style="bold dim", width=28)
    t.add_column("val")

    for k, v in data.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, bool):
            val_str = "[green]Sí ✓[/green]" if v else "[red]No ✗[/red]"
        elif isinstance(v, float):
            val_str = f"$ {v:,.0f}" if v else "0"
        elif isinstance(v, list):
            val_str = f"[dim]({len(v)} items)[/dim]"
        else:
            val_str = str(v)
        t.add_row(k.replace("_", " ").title(), val_str)

    console.print(t)

    # Historial sub-table (SIMIT)
    historial = getattr(result, "historial", [])
    if historial:
        console.print()
        ht = Table(title=f"Historial ({len(historial)} registros)", border_style="blue")
        ht.add_column("Comparendo", style="dim")
        ht.add_column("Secretaría")
        ht.add_column("Fecha curso")
        ht.add_column("Ciudad")
        ht.add_column("Estado")
        for rec in historial:
            ht.add_row(
                str(rec.get("comparendo", ""))[:24],
                str(rec.get("secretaria", "")),
                str(rec.get("fecha_curso", "")),
                str(rec.get("ciudad", "")),
                str(rec.get("estado", "")),
            )
        console.print(ht)

    # Audit evidence
    if q_input.audit and hasattr(result, "audit") and result.audit is not None:
        _save_audit(result.audit, source_name, label, audit_dir)


def _save_audit(audit_record, source: str, label: str, audit_dir: str | None) -> None:
    """Persist audit evidence (screenshots + PDF) to disk."""
    import base64
    from pathlib import Path

    out = Path(audit_dir) if audit_dir else Path.cwd() / "audit"
    out.mkdir(parents=True, exist_ok=True)
    ts = audit_record.queried_at.strftime("%Y%m%d_%H%M%S")
    prefix = f"{source}_{label[:12]}_{ts}"

    if getattr(audit_record, "pdf_base64", None):
        path = out / f"{prefix}_evidence.pdf"
        path.write_bytes(base64.b64decode(audit_record.pdf_base64))
        console.print(f"[green]PDF saved:[/green] {path}")

    for ss in getattr(audit_record, "screenshots", []):
        if getattr(ss, "png_base64", None):
            path = out / f"{prefix}_{ss.label}.png"
            path.write_bytes(base64.b64decode(ss.png_base64))
            console.print(f"[green]Screenshot:[/green] {path}")

    meta_path = out / f"{prefix}_audit.json"
    meta_dict = audit_record.model_dump(mode="json")
    meta_dict.pop("pdf_base64", None)
    for sc in meta_dict.get("screenshots", []):
        sc.pop("png_base64", None)
    meta_path.write_text(_json.dumps(meta_dict, indent=2, ensure_ascii=False))
    console.print(f"[green]Audit log:[/green] {meta_path}")


# ─── Commands ─────────────────────────────────────────────────────────────────

@query_app.command("sources")
def query_sources() -> None:
    """List all available openquery data sources."""
    _require_openquery()
    from openquery.sources import list_sources

    sources = sorted(list_sources(), key=lambda s: s.meta().name)

    if is_json_mode():
        data = [
            {
                "name": s.meta().name,
                "display_name": s.meta().display_name,
                "description": s.meta().description,
                "country": s.meta().country,
                "inputs": [str(i) for i in s.meta().supported_inputs],
                "requires_browser": s.meta().requires_browser,
                "requires_captcha": s.meta().requires_captcha,
                "rate_limit_rpm": s.meta().rate_limit_rpm,
            }
            for s in sources
        ]
        console.print(_json.dumps(data, indent=2, ensure_ascii=False))
        return

    t = Table(title="OpenQuery Sources", border_style="dim")
    t.add_column("Source",   style="bold cyan", width=24)
    t.add_column("Name",     width=30)
    t.add_column("Inputs",   width=22)
    t.add_column("Browser",  justify="center", width=8)
    t.add_column("CAPTCHA",  justify="center", width=8)
    t.add_column("RPM",      justify="right",  width=5)

    for s in sources:
        m = s.meta()
        inputs  = ", ".join(str(i) for i in m.supported_inputs)
        browser = "[green]✓[/green]" if m.requires_browser else "[dim]—[/dim]"
        captcha = "[yellow]✓[/yellow]" if m.requires_captcha else "[dim]—[/dim]"
        t.add_row(m.name, m.display_name, inputs, browser, captcha, str(m.rate_limit_rpm))

    console.print(t)


@query_app.command("run")
def query_run(
    source:    str      = typer.Argument(..., help="Source name, e.g. co.simit, co.runt"),
    cedula:    str | None = CedulaOption,
    placa:     str | None = PlacaOption,
    vin:       str | None = VinOption,
    extra:     str | None = ExtraOption,
    audit:     bool       = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """Run a query against [bold]any[/bold] openquery source (generic runner)."""
    _require_openquery()
    q = _build_input(cedula, placa, vin, extra, audit)
    _run(source, q, audit_dir)


# ── Convenience: person / document queries ────────────────────────────────────

@query_app.command("simit")
def query_simit(
    cedula:    str | None = CedulaOption,
    placa:     str | None = PlacaOption,
    audit:     bool       = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """SIMIT — multas de tránsito Colombia (FCM)."""
    _require_openquery()
    q = _build_input(cedula, placa, None, audit=audit)
    _run("co.simit", q, audit_dir)


@query_app.command("runt")
def query_runt(
    cedula:    str | None = CedulaOption,
    placa:     str | None = PlacaOption,
    vin:       str | None = VinOption,
    audit:     bool       = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """RUNT — registro nacional de tránsito (vehículo por cédula, placa o VIN)."""
    _require_openquery()
    q = _build_input(cedula, placa, vin, audit=audit)
    _run("co.runt", q, audit_dir)


@query_app.command("procuraduria")
def query_procuraduria(
    cedula:    str | None = CedulaOption,
    audit:     bool       = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """Procuraduría — antecedentes disciplinarios."""
    _require_openquery()
    q = _build_input(cedula, None, None, audit=audit)
    _run("co.procuraduria", q, audit_dir)


@query_app.command("policia")
def query_policia(
    cedula:    str | None = CedulaOption,
    audit:     bool       = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """Policía — antecedentes judiciales."""
    _require_openquery()
    q = _build_input(cedula, None, None, audit=audit)
    _run("co.policia", q, audit_dir)


@query_app.command("adres")
def query_adres(
    cedula:    str | None = CedulaOption,
    audit:     bool       = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """ADRES — afiliación al sistema de salud (EPS)."""
    _require_openquery()
    q = _build_input(cedula, None, None, audit=audit)
    _run("co.adres", q, audit_dir)


@query_app.command("pico-y-placa")
def query_pico_y_placa(
    placa: str | None = PlacaOption,
    ciudad: str | None = typer.Option(None, "--ciudad", help="Ciudad (default: Bogotá)"),
) -> None:
    """Pico y placa — restricción de circulación por placa y ciudad."""
    _require_openquery()
    extra = {}
    if ciudad:
        extra["ciudad"] = ciudad
    q = _build_input(None, placa, None, extra_json=_json.dumps(extra) if extra else None)
    _run("co.pico_y_placa", q)


@query_app.command("vehiculos")
def query_vehiculos(
    placa:     str | None = PlacaOption,
    audit:     bool       = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """Parque automotor nacional — consulta por placa."""
    _require_openquery()
    q = _build_input(None, placa, None, audit=audit)
    _run("co.vehiculos", q, audit_dir)


# ── Convenience: API / open-data queries ──────────────────────────────────────

@query_app.command("combustible")
def query_combustible(
    ciudad: str | None = typer.Option(None, "--ciudad", "-C", help="Ciudad/municipio"),
    extra:  str | None = ExtraOption,
) -> None:
    """Precios de combustible por ciudad/estación."""
    _require_openquery()
    e: dict = _json.loads(extra) if extra else {}
    if ciudad:
        e.setdefault("municipio", ciudad)
    q = _build_input(None, None, None, extra_json=_json.dumps(e) if e else None)
    _run("co.combustible", q)


@query_app.command("estaciones-ev")
def query_estaciones_ev(
    ciudad: str | None = typer.Option(None, "--ciudad", "-C", help="Ciudad"),
    extra:  str | None = ExtraOption,
) -> None:
    """Estaciones de carga EV disponibles."""
    _require_openquery()
    e: dict = _json.loads(extra) if extra else {}
    if ciudad:
        e.setdefault("ciudad", ciudad)
    q = _build_input(None, None, None, extra_json=_json.dumps(e) if e else None)
    _run("co.estaciones_ev", q)


@query_app.command("peajes")
def query_peajes(
    peaje: str | None = typer.Option(None, "--peaje", help="Nombre del peaje"),
    extra: str | None = ExtraOption,
) -> None:
    """Tarifas de peajes en Colombia."""
    _require_openquery()
    e: dict = _json.loads(extra) if extra else {}
    if peaje:
        e.setdefault("peaje", peaje)
    q = _build_input(None, None, None, extra_json=_json.dumps(e) if e else None)
    _run("co.peajes", q)


@query_app.command("fasecolda")
def query_fasecolda(
    marca:   str | None = typer.Option(None, "--marca", help="Marca del vehículo (ej. TESLA)"),
    modelo:  str | None = typer.Option(None, "--modelo", help="Año modelo (ej. 2026)"),
    extra:   str | None = ExtraOption,
) -> None:
    """FASECOLDA — precios de referencia de vehículos."""
    _require_openquery()
    e: dict = _json.loads(extra) if extra else {}
    if marca:
        e.setdefault("marca", marca)
    if modelo:
        e.setdefault("modelo", modelo)
    q = _build_input(None, None, None, extra_json=_json.dumps(e) if e else None)
    _run("co.fasecolda", q)


@query_app.command("recalls")
def query_recalls(
    marca:  str | None = typer.Option(None, "--marca", help="Marca del vehículo (ej. TESLA)"),
    extra:  str | None = ExtraOption,
) -> None:
    """Recalls de seguridad vehicular en Colombia."""
    _require_openquery()
    e: dict = _json.loads(extra) if extra else {}
    if marca:
        e.setdefault("marca", marca)
    q = _build_input(None, None, None, extra_json=_json.dumps(e) if e else None)
    _run("co.recalls", q)


@query_app.command("siniestralidad")
def query_siniestralidad(
    extra: str | None = ExtraOption,
) -> None:
    """Puntos críticos de accidentalidad vial."""
    _require_openquery()
    q = _build_input(None, None, None, extra_json=extra)
    _run("co.siniestralidad", q)
