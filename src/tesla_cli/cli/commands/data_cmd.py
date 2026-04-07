"""tesla data — Data sources, exports, and Colombian public data queries.

Three sections:
1. Vehicle data aggregation: build, history, diff, clean, data-sources
2. Export: export-html, export-pdf
3. Colombian public data (via openquery): runt, simit, procuraduria, policia, etc.

Usage examples:
    tesla data build                             # build/refresh from all sources
    tesla data history                           # show snapshot history
    tesla data diff 1 3                          # compare two snapshots
    tesla data data-sources                      # show 15 sources + cache status
    tesla data export-html --theme light         # export HTML report
    tesla data runt --placa ABC123               # RUNT vehicle registry
    tesla data simit --cedula 12345678           # SIMIT traffic fines
    tesla data run co.combustible --extra '{"municipio": "BOGOTA"}'
"""

from __future__ import annotations

import json as _json
import time

import typer
from rich.table import Table

from tesla_cli.cli.output import console, is_json_mode

data_app = typer.Typer(
    name="data",
    help="Data sources, exports, and Colombian public data via [bold]openquery[/bold].",
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

CedulaOption = typer.Option(None, "--cedula", "-c", help="Cédula / national ID number")
PlacaOption = typer.Option(None, "--placa", "-p", help="License plate (e.g. ABC123)")
VinOption = typer.Option(None, "--vin", "-v", help="VIN number")
ExtraOption = typer.Option(
    None, "--extra", "-e", help='Extra params as JSON, e.g. \'{"ciudad":"Bogota"}\''
)
AuditOption = typer.Option(
    False, "--audit", "-a", help="Capture audit evidence (screenshots + PDF)"
)
AuditDirOpt = typer.Option(None, "--audit-dir", help="Directory for audit files (default: ./audit)")


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
        return QueryInput(
            document_type=DocumentType.CEDULA, document_number=cedula, extra=extra, audit=audit
        )
    if placa:
        return QueryInput(
            document_type=DocumentType.PLATE, document_number=placa, extra=extra, audit=audit
        )
    if vin:
        return QueryInput(
            document_type=DocumentType.VIN, document_number=vin, extra=extra, audit=audit
        )
    if extra:
        return QueryInput(
            document_type=DocumentType.CUSTOM, document_number="", extra=extra, audit=audit
        )

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
        console.print(
            f"[red]Unknown source:[/red] {source_name!r}\n[dim]Available: {available}[/dim]"
        )
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


# ═══════════════════════════════════════════════════════════════════════════════
# Colombian Public Data Queries (via openquery)
# ═══════════════════════════════════════════════════════════════════════════════


@data_app.command("sources")
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
    t.add_column("Source", style="bold cyan", width=24)
    t.add_column("Name", width=30)
    t.add_column("Inputs", width=22)
    t.add_column("Browser", justify="center", width=8)
    t.add_column("CAPTCHA", justify="center", width=8)
    t.add_column("RPM", justify="right", width=5)

    for s in sources:
        m = s.meta()
        inputs = ", ".join(str(i) for i in m.supported_inputs)
        browser = "[green]✓[/green]" if m.requires_browser else "[dim]—[/dim]"
        captcha = "[yellow]✓[/yellow]" if m.requires_captcha else "[dim]—[/dim]"
        t.add_row(m.name, m.display_name, inputs, browser, captcha, str(m.rate_limit_rpm))

    console.print(t)


@data_app.command("run")
def query_run(
    source: str = typer.Argument(..., help="Source name, e.g. co.simit, co.runt"),
    cedula: str | None = CedulaOption,
    placa: str | None = PlacaOption,
    vin: str | None = VinOption,
    extra: str | None = ExtraOption,
    audit: bool = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """Run a query against [bold]any[/bold] openquery source (generic runner)."""
    _require_openquery()
    q = _build_input(cedula, placa, vin, extra, audit)
    _run(source, q, audit_dir)


# ── Convenience: person / document queries ────────────────────────────────────


@data_app.command("simit")
def query_simit(
    cedula: str | None = CedulaOption,
    placa: str | None = PlacaOption,
    audit: bool = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """SIMIT — multas de tránsito Colombia (FCM)."""
    _require_openquery()
    q = _build_input(cedula, placa, None, audit=audit)
    _run("co.simit", q, audit_dir)


@data_app.command("runt")
def query_runt(
    cedula: str | None = CedulaOption,
    placa: str | None = PlacaOption,
    vin: str | None = VinOption,
    audit: bool = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """RUNT — registro nacional de tránsito (vehículo por cédula, placa o VIN).

    If no option is given, uses the default VIN from config.
    """
    _require_openquery()
    if not cedula and not placa and not vin:
        from tesla_cli.core.config import load_config

        cfg = load_config()
        vin = cfg.general.default_vin
        if not vin:
            console.print(
                "[red]No VIN configured.[/red] Pass --vin or run: tesla config set default-vin <VIN>"
            )
            raise typer.Exit(1)
    q = _build_input(cedula, placa, vin, audit=audit)
    _run("co.runt", q, audit_dir)


@data_app.command("procuraduria")
def query_procuraduria(
    cedula: str | None = CedulaOption,
    audit: bool = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """Procuraduría — antecedentes disciplinarios."""
    _require_openquery()
    q = _build_input(cedula, None, None, audit=audit)
    _run("co.procuraduria", q, audit_dir)


@data_app.command("policia")
def query_policia(
    cedula: str | None = CedulaOption,
    audit: bool = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """Policía — antecedentes judiciales."""
    _require_openquery()
    q = _build_input(cedula, None, None, audit=audit)
    _run("co.policia", q, audit_dir)


@data_app.command("adres")
def query_adres(
    cedula: str | None = CedulaOption,
    audit: bool = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """ADRES — afiliación al sistema de salud (EPS)."""
    _require_openquery()
    q = _build_input(cedula, None, None, audit=audit)
    _run("co.adres", q, audit_dir)


@data_app.command("pico-y-placa")
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


@data_app.command("vehiculos")
def query_vehiculos(
    placa: str | None = PlacaOption,
    audit: bool = AuditOption,
    audit_dir: str | None = AuditDirOpt,
) -> None:
    """Parque automotor nacional — consulta por placa."""
    _require_openquery()
    q = _build_input(None, placa, None, audit=audit)
    _run("co.vehiculos", q, audit_dir)


# ── Convenience: API / open-data queries ──────────────────────────────────────


@data_app.command("combustible")
def query_combustible(
    ciudad: str | None = typer.Option(None, "--ciudad", "-C", help="Ciudad/municipio"),
    extra: str | None = ExtraOption,
) -> None:
    """Precios de combustible por ciudad/estación."""
    _require_openquery()
    e: dict = _json.loads(extra) if extra else {}
    if ciudad:
        e.setdefault("municipio", ciudad)
    q = _build_input(None, None, None, extra_json=_json.dumps(e) if e else None)
    _run("co.combustible", q)


@data_app.command("estaciones-ev")
def query_estaciones_ev(
    ciudad: str | None = typer.Option(None, "--ciudad", "-C", help="Ciudad"),
    extra: str | None = ExtraOption,
) -> None:
    """Estaciones de carga EV disponibles."""
    _require_openquery()
    e: dict = _json.loads(extra) if extra else {}
    if ciudad:
        e.setdefault("ciudad", ciudad)
    q = _build_input(None, None, None, extra_json=_json.dumps(e) if e else None)
    _run("co.estaciones_ev", q)


@data_app.command("peajes")
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


@data_app.command("fasecolda")
def query_fasecolda(
    marca: str | None = typer.Option(None, "--marca", help="Marca del vehículo (ej. TESLA)"),
    modelo: str | None = typer.Option(None, "--modelo", help="Año modelo (ej. 2026)"),
    extra: str | None = ExtraOption,
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


@data_app.command("recalls")
def query_recalls(
    marca: str | None = typer.Option(None, "--marca", help="Marca del vehículo (ej. TESLA)"),
    extra: str | None = ExtraOption,
) -> None:
    """Recalls de seguridad vehicular en Colombia."""
    _require_openquery()
    e: dict = _json.loads(extra) if extra else {}
    if marca:
        e.setdefault("marca", marca)
    q = _build_input(None, None, None, extra_json=_json.dumps(e) if e else None)
    _run("co.recalls", q)


@data_app.command("siniestralidad")
def query_siniestralidad(
    extra: str | None = ExtraOption,
) -> None:
    """Puntos críticos de accidentalidad vial."""
    _require_openquery()
    q = _build_input(None, None, None, extra_json=extra)
    _run("co.siniestralidad", q)


@data_app.command("energia")
def query_energia(
    ciudad: str = typer.Option(
        "bogota", "--ciudad", "-c", help="City (bogota, medellin, cali, barranquilla)"
    ),
    estrato: int = typer.Option(0, "--estrato", "-e", help="Estrato 1–6, 0 = all"),
) -> None:
    """Electricity tariff by city and estrato — cost per kWh for EV charging.

    Shows the current electricity price per kWh in your city, useful for
    calculating real charging costs at home.

    Examples:

      tesla data energia --ciudad bogota --estrato 4
      tesla data energia -c medellin
    """
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput
    except ImportError:
        console.print(_NOT_INSTALLED)
        raise typer.Exit(1)

    from rich.progress import Progress, SpinnerColumn, TextColumn

    extra: dict = {"ciudad": ciudad}
    if estrato:
        extra["estrato"] = estrato

    qi = QueryInput(
        document_type=DocumentType.CUSTOM,
        document_number="",
        extra=extra,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as prog:
        prog.add_task("Consultando tarifas de energía…", total=None)
        try:
            src = get_source("co.tarifas_energia")
            result = src.query(qi)
        except KeyError:
            console.print(
                "[red]Source co.tarifas_energia not available in this openquery version.[/red]"
            )
            raise typer.Exit(1)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error consultando tarifas:[/red] {exc}")
            raise typer.Exit(1)

    data = result.model_dump(exclude={"audit", "queried_at"})

    if is_json_mode():
        import json as _j

        console.print(_j.dumps(data, indent=2, ensure_ascii=False))
        return

    # ── Display results ────────────────────────────────────────────────────────
    tarifas: list[dict] = []
    if isinstance(data.get("tarifas"), list):
        tarifas = data["tarifas"]
    elif isinstance(data.get("data"), list):
        tarifas = data["data"]
    else:
        # Fallback: generic display
        t = Table(
            title=f"Tarifas de Energía — {ciudad.title()}",
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        t.add_column("key", style="bold dim", width=28)
        t.add_column("val")
        for k, v in data.items():
            if v is None or v == "" or v == []:
                continue
            t.add_row(k.replace("_", " ").title(), str(v))
        console.print(t)
        return

    # Filter by estrato if specified
    if estrato:
        tarifas = [r for r in tarifas if str(r.get("estrato", "")) == str(estrato)]

    t = Table(
        title=f"Tarifas de Energía — {ciudad.title()}",
        border_style="dim",
    )
    t.add_column("Estrato", justify="center", width=8)
    t.add_column("$/kWh", justify="right", width=10)
    t.add_column("Operador", width=28)
    t.add_column("Municipio", width=18)

    target_tariff: float | None = None
    target_row: dict | None = None

    for row in tarifas:
        est = str(row.get("estrato", "—"))
        kwh = row.get("tarifa_kwh") or row.get("costo_kwh") or row.get("valor_kwh")
        operador = str(row.get("operador") or row.get("empresa") or "—")
        municipio = str(row.get("municipio") or row.get("ciudad") or "—")
        kwh_str = f"${float(kwh):,.4f}" if kwh is not None else "—"

        # Highlight the requested estrato
        highlight = estrato and str(estrato) == est
        style = "bold green" if highlight else ""
        t.add_row(est, kwh_str, operador, municipio, style=style)

        if highlight and kwh is not None:
            target_tariff = float(kwh)
            target_row = row

    console.print(t)

    # ── Offer to update cost_per_kwh ──────────────────────────────────────────
    if target_tariff is not None and target_row is not None:
        from tesla_cli.core.config import load_config, save_config

        cfg = load_config()
        current = cfg.general.cost_per_kwh
        operador = target_row.get("operador") or target_row.get("empresa") or "—"

        console.print()
        console.print(
            f"[dim]Current cost_per_kwh in config:[/dim] "
            f"[{'yellow' if current else 'dim'}]${current:.2f}[/{'yellow' if current else 'dim'}]"
        )
        console.print(
            f"Your estrato [bold]{estrato}[/bold] tariff: "
            f"[bold green]${target_tariff:.4f}/kWh[/bold green] "
            f"[dim]({operador} — {ciudad.title()})[/dim]"
        )
        console.print()

        update = typer.confirm("Update cost_per_kwh in config?", default=False)
        if update:
            cfg.general.cost_per_kwh = target_tariff
            save_config(cfg)
            console.print(
                f"[green]✓[/green] cost_per_kwh updated to [bold]${target_tariff:.4f}[/bold]/kWh"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Vehicle Data Aggregation & Export
# ═══════════════════════════════════════════════════════════════════════════════


@data_app.command("build")
def query_build() -> None:
    """Build/update vehicle data from all sources.

    tesla query build
    """
    from tesla_cli.cli.commands.dossier import dossier_build

    dossier_build()


@data_app.command("history")
def query_history() -> None:
    """Show data snapshot history.

    tesla query history
    tesla -j query history
    """
    from tesla_cli.cli.commands.dossier import dossier_history

    dossier_history()


@data_app.command("diff")
def query_diff(
    snap_a: str | None = typer.Argument(None, help="Snapshot A: index (1-based) or filename"),
    snap_b: str | None = typer.Argument(None, help="Snapshot B: index or filename"),
) -> None:
    """Compare two data snapshots side by side.

    tesla data diff          # compare last two
    tesla data diff 1 3      # compare specific snapshots
    tesla -j data diff
    """
    from tesla_cli.cli.commands.dossier import dossier_diff

    dossier_diff(snap_a=snap_a, snap_b=snap_b)


@data_app.command("export-html")
def query_export_html(
    output: str = typer.Option("dossier.html", "--output", "-o", help="Output HTML file path"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
    theme: str = typer.Option("dark", "--theme", "-t", help="CSS theme: dark or light"),
) -> None:
    """Export vehicle data to standalone HTML report.

    tesla query export-html
    tesla query export-html --theme light
    """
    from tesla_cli.cli.commands.dossier import dossier_export_html

    dossier_export_html(output=output, vin=vin, theme=theme)


@data_app.command("export-pdf")
def query_export_pdf(
    output: str = typer.Option("dossier.pdf", "--output", "-o", help="Output PDF file path"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
) -> None:
    """Export vehicle data to PDF report.

    tesla query export-pdf
    """
    from tesla_cli.cli.commands.dossier import dossier_export_pdf

    dossier_export_pdf(output=output, vin=vin)


@data_app.command("clean")
def query_clean(
    keep: int = typer.Option(10, "--keep", "-n", help="Number of snapshots to keep (most recent)"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without deleting"
    ),
) -> None:
    """Prune old data snapshots.

    tesla data clean
    tesla data clean --keep 5
    tesla data clean --dry-run
    """
    from tesla_cli.cli.commands.dossier import dossier_clean

    dossier_clean(keep=keep, dry_run=dry_run)


@data_app.command("data-sources")
def query_data_sources() -> None:
    """Show all registered Tesla data sources with cache status.

    tesla query data-sources
    tesla -j query data-sources
    """
    from tesla_cli.cli.commands.dossier import dossier_sources

    dossier_sources()


@data_app.command("set-country")
def set_country(
    country: str = typer.Argument(help="ISO country code (e.g. US, CO, BR, MX)"),
) -> None:
    """Set your country to auto-register relevant vehicle data sources.

    tesla data set-country CO
    tesla data set-country US
    """
    from tesla_cli.core.config import load_config, save_config
    from tesla_cli.core.sources import COUNTRY_SOURCES

    code = country.upper().strip()
    known = set(COUNTRY_SOURCES.keys())
    if code and code not in known:
        console.print(
            f"[yellow]Warning:[/yellow] Country '{code}' has no registered sources. "
            f"Known: {', '.join(sorted(known))}"
        )

    cfg = load_config()
    old = cfg.general.country
    cfg.general.country = code
    save_config(cfg)

    if is_json_mode():
        import json as _json2

        console.print(_json2.dumps({"country": code, "previous": old}))
        return

    console.print(f"[green]Country set to:[/green] [bold]{code}[/bold]")
    if code in known:
        count = len(COUNTRY_SOURCES.get(code, []))
        console.print(f"[dim]{count} country-specific source(s) will be active on next load.[/dim]")
    console.print("[dim]Restart the server or re-run any command for sources to take effect.[/dim]")


@data_app.command("available-sources")
def available_sources() -> None:
    """Show all available data sources for your configured country.

    tesla data available-sources
    tesla -j data available-sources
    """
    import json as _json2  # noqa: PLC0415

    from tesla_cli.core.config import load_config
    from tesla_cli.core.sources import _SOURCES, COUNTRY_SOURCES

    cfg = load_config()
    country = cfg.general.country or "(none — showing all)"

    rows = []
    for sid, src in _SOURCES.items():
        rows.append(
            {
                "id": sid,
                "name": src.name,
                "category": src.category,
                "country": src.country,
                "ttl": src.ttl,
                "requires_auth": src.requires_auth,
                "uses_playwright": src.uses_playwright,
            }
        )

    # Also list country sources not yet registered (if a different country is set)
    registered_ids = set(_SOURCES.keys())
    for _c, srcs in COUNTRY_SOURCES.items():
        for src in srcs:
            if src.id not in registered_ids:
                rows.append(
                    {
                        "id": src.id,
                        "name": src.name,
                        "category": src.category,
                        "country": src.country,
                        "ttl": src.ttl,
                        "requires_auth": src.requires_auth,
                        "uses_playwright": src.uses_playwright,
                        "inactive": True,
                    }
                )

    if is_json_mode():
        console.print(_json2.dumps(rows, indent=2))
        return

    t = Table(
        title=f"Available Data Sources  [dim](country: {country})[/dim]",
        border_style="dim",
    )
    t.add_column("ID", style="bold cyan", width=26)
    t.add_column("Name", width=34)
    t.add_column("Category", width=14)
    t.add_column("Country", justify="center", width=8)
    t.add_column("Browser", justify="center", width=8)
    t.add_column("Active", justify="center", width=7)

    for r in sorted(rows, key=lambda x: (x.get("country", ""), x["id"])):
        active = "[green]✓[/green]" if not r.get("inactive") else "[dim]—[/dim]"
        browser = "[yellow]✓[/yellow]" if r.get("uses_playwright") else "[dim]—[/dim]"
        t.add_row(r["id"], r["name"], r["category"], r.get("country", ""), browser, active)

    console.print(t)
