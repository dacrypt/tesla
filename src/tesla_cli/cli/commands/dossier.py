"""Dossier commands: tesla dossier build/show/history/ships."""

from __future__ import annotations

import json

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.cli.output import console, is_json_mode
from tesla_cli.core.backends.dossier import DossierBackend

dossier_app = typer.Typer(name="dossier", help="Complete vehicle intelligence dossier.")


@dossier_app.command("build")
def dossier_build() -> None:
    """Build/update the full vehicle dossier from all sources."""
    backend = DossierBackend()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as progress:
        progress.add_task("Building dossier from all sources...", total=None)
        dossier = backend.build_dossier()

    if is_json_mode():
        console.print_json(dossier.model_dump_json(indent=2, exclude_none=True))
        return

    # ── Real Status (top, most important) ──
    rs = dossier.real_status
    phase_color = {
        "delivered": "bold green",
        "delivery_scheduled": "bold cyan",
        "registered": "bold yellow",
        "in_country": "yellow",
        "shipped": "blue",
        "produced": "dim",
        "ordered": "dim",
    }.get(rs.phase, "white")
    _section("Real Status")
    console.print(f"  [{phase_color}]▸ {rs.phase_description}[/{phase_color}]\n")
    _kv_table(
        [
            ("Phase", rs.phase.upper()),
            ("Tesla API says", rs.tesla_api_status),
            ("RUNT says", rs.runt_status or "(not queried)"),
            ("VIN Assigned", "✅" if rs.vin_assigned else "❌"),
            ("In RUNT", "✅" if rs.in_runt else "❌"),
            ("Has Placa", "✅" if rs.has_placa else "⏳ Pendiente"),
            ("Has SOAT", "✅" if rs.has_soat else "⏳ Pendiente"),
            (
                "Delivery Date",
                rs.delivery_date or "(not set — use: tesla dossier set-delivery YYYY-MM-DD)",
            ),
        ]
    )

    # ── RUNT ──
    r = dossier.runt
    if r.estado:
        _section("RUNT (Registro Nacional de Tránsito)")
        _kv_table(
            [
                ("Estado", r.estado),
                ("Placa", r.placa or "(no asignada)"),
                ("Clase", r.clase_vehiculo),
                ("Marca/Línea", f"{r.marca} {r.linea}"),
                ("Modelo (año)", r.modelo_ano),
                ("Color", r.color),
                ("Combustible", r.tipo_combustible),
                ("Carrocería", r.tipo_carroceria),
                ("Peso bruto", f"{r.peso_bruto_kg} kg"),
                ("Pasajeros", str(r.capacidad_pasajeros)),
                ("Gravámenes", "NO ✅" if not r.gravamenes else "SÍ ⚠️"),
                ("SOAT", "Vigente ✅" if r.soat_vigente else "No registrado"),
                (
                    "Tecnomecánica",
                    "Vigente ✅" if r.tecnomecanica_vigente else "No aplica (vehículo nuevo)",
                ),
            ]
        )

    # ── Identity ──
    _section("Identity")
    _kv_table(
        [
            ("VIN", dossier.vin),
            ("Reservation", dossier.reservation_number),
            ("Manufacturer", dossier.vin_decode.manufacturer),
            ("Model", dossier.vin_decode.model),
            ("Body", dossier.vin_decode.body_type),
            ("Motor/Battery", dossier.vin_decode.motor_battery),
            ("Energy", dossier.vin_decode.energy_type),
            ("Battery Chemistry", dossier.vin_decode.battery_chemistry),
            ("Model Year", dossier.vin_decode.model_year),
            ("Plant", dossier.vin_decode.plant),
            ("Serial", dossier.vin_decode.serial_number),
        ]
    )

    # ── Specs ──
    s = dossier.specs
    _section("Vehicle Specs")
    _kv_table(
        [
            ("Model", f"{s.model} {s.variant}"),
            ("Generation", s.generation),
            ("Year", str(s.model_year)),
            ("Factory", s.factory),
            ("Battery", f"{s.battery_type} ~{s.battery_capacity_kwh} kWh"),
            ("Range", f"{s.range_km} km (WLTP est.)"),
            ("Motor", s.motor_config),
            ("Power", f"~{s.horsepower} hp"),
            ("0-100 km/h", f"{s.zero_to_100_kmh}s"),
            ("Top Speed", f"{s.top_speed_kmh} km/h"),
            ("Weight", f"{s.curb_weight_kg} kg"),
            ("Dimensions", s.dimensions),
            ("Seats", str(s.seating)),
            ("Wheels", s.wheels),
            ("Exterior", s.exterior_color),
            ("Interior", s.interior),
            ("AP Hardware", s.autopilot_hardware),
            ("FSD", "Yes" if s.has_fsd else "No"),
            ("Supercharging", s.supercharging),
            ("Connectivity", s.connectivity),
        ]
    )

    # ── Option Codes ──
    if dossier.option_codes.codes:
        _section("Option Codes")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Code", style="bold")
        table.add_column("Category")
        table.add_column("Description")
        for oc in dossier.option_codes.codes:
            table.add_row(oc.code, oc.category, oc.description_es or oc.description)
        console.print(table)

    # ── Order Status ──
    o = dossier.order
    _section("Order Timeline")
    _kv_table(
        [
            ("Status", f"{o.current.order_status} (substatus: {o.current.order_substatus})"),
            ("Vehicle Map ID", str(o.vehicle_map_id)),
            ("Country", o.country_code),
            ("Locale", o.locale),
            ("B2B", "Yes" if o.is_b2b else "No"),
            ("Used", "Yes" if o.is_used else "No"),
            ("Tesla Assist", "Yes" if o.is_tesla_assist_enabled else "No"),
            ("History entries", str(len(o.history))),
        ]
    )

    # ── Logistics ──
    lg = dossier.logistics
    _section("Logistics / Shipping")
    _kv_table(
        [
            ("Factory", lg.factory),
            ("Departure Port", lg.departure_port),
            ("Arrival Port", lg.arrival_port),
            ("Destination", lg.destination_country),
            ("Est. Transit", f"~{lg.estimated_transit_days} days"),
            ("Carrier", lg.ship.vessel_name or "(tracking...)"),
            ("Ship IMO", lg.ship.imo or "-"),
            ("Track URL", lg.ship.tracking_url or "-"),
        ]
    )

    # ── Recalls ──
    _section("Recalls")
    if dossier.recalls:
        for r in dossier.recalls:
            console.print(f"  [red]{r.recall_id}[/red] — {r.component}: {r.description[:100]}")
    else:
        console.print("  [green]No recalls found[/green]")

    # ── Account ──
    a = dossier.account
    _section("Tesla Account")
    _kv_table(
        [
            ("Name", a.full_name),
            ("Email", a.email),
            ("Vault UUID", a.vault_uuid),
            ("Signaling", str(a.feature_config.get("signaling", {}).get("enabled", "-"))),
            ("Service Scheduling", "Yes" if a.service_scheduling_enabled else "No"),
        ]
    )

    # ── Meta ──
    _section("Dossier Meta")
    _kv_table(
        [
            ("Version", dossier.dossier_version),
            ("Created", str(dossier.created_at)[:19]),
            ("Last Updated", str(dossier.last_updated)[:19]),
            ("Update Count", str(dossier.update_count)),
            (
                "Archive",
                str(
                    DossierBackend._DossierBackend__get_archive_path()
                    if hasattr(DossierBackend, "_DossierBackend__get_archive_path")
                    else "~/.tesla-cli/dossier/"
                ),
            ),
        ]
    )

    console.print()


@dossier_app.command("show")
def dossier_show() -> None:
    """Show the current saved dossier (without fetching new data)."""
    from pathlib import Path

    from rich.panel import Panel

    backend = DossierBackend()
    dossier = backend._load_dossier()
    if not dossier:
        console.print("[yellow]No dossier found. Run: tesla dossier build[/yellow]")
        raise typer.Exit(1)

    # ── Load mission-control-data.json if available ──
    mc_data: dict = {}
    mc_path = Path(__file__).parent.parent.parent.parent / "mission-control-data.json"
    for candidate in [
        mc_path,
        Path.cwd() / "mission-control-data.json",
        Path.home() / ".tesla-cli" / "mission-control-data.json",
    ]:
        if candidate.exists():
            try:
                mc_data = json.loads(candidate.read_text())
            except Exception:
                pass
            break

    if is_json_mode():
        data = json.loads(dossier.model_dump_json(indent=2, exclude_none=True))
        if mc_data:
            data["_mission_control"] = mc_data
        console.print_json(json.dumps(data, indent=2, ensure_ascii=False))
        return

    # ── Header ──
    title_text = (
        f"⚡ TESLA {dossier.specs.model.upper()} {dossier.specs.model_year} — VEHICLE DOSSIER"
    )
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{title_text}[/bold cyan]\n"
            f"[dim]VIN: {dossier.vin} │ Last updated: {str(dossier.last_updated)[:19]} │ Updates: {dossier.update_count}[/dim]",
            expand=True,
            border_style="cyan",
        )
    )

    # ── Quick Summary Dashboard ──
    _render_summary_dashboard(console, dossier, mc_data)

    # ── Render all sections ──
    _render_status(console, dossier.real_status)
    _render_specs(console, dossier.specs, mc_data.get("epa", {}))
    _render_vin_decode(console, dossier.vin, dossier.vin_decode)
    _render_option_codes(console, dossier.option_codes)
    _render_order(console, dossier.order)
    _render_runt(console, dossier.runt)
    _render_logistics(console, dossier.logistics)
    _render_recalls(console, dossier.recalls, mc_data)
    _render_account(console, dossier.account)
    _render_simit(console, dossier.simit, mc_data)
    _render_epa(console, mc_data.get("epa", {}))
    _render_nhtsa(console, mc_data)
    _render_tesla_tasks(console, mc_data.get("tesla_tasks", {}))
    _render_delivery(console, mc_data)
    _render_monitor(console, mc_data)
    _render_sources(console, mc_data)
    _render_meta(console, dossier, mc_data)

    console.print()
    console.print("[dim]Run [bold]tesla dossier build[/bold] to refresh from all sources.[/dim]")
    console.print()


# ── Render helpers for dossier_show ──────────────────────────────────────────


def _render_summary_dashboard(con, dossier, mc_data: dict) -> None:
    """Render the quick summary dashboard panel."""
    from rich.panel import Panel

    rs = dossier.real_status
    s = dossier.specs
    runt = dossier.runt
    simit = mc_data.get("simit", {})
    epa = mc_data.get("epa", {})
    tasks = mc_data.get("tesla_tasks", {})
    recalls = mc_data.get("nhtsa_recalls", {})
    complaints = mc_data.get("nhtsa_complaints", {})
    sources = mc_data.get("sources", {})

    ok_sources = sum(1 for v in sources.values() if v.get("ok"))
    total_sources = len(sources)
    tasks_done = sum(1 for t in tasks.values() if isinstance(t, dict) and t.get("complete"))
    tasks_total = len(tasks)

    placa_str = f"[green]{runt.placa}[/green]" if runt.placa else "[yellow]⏳ Pendiente[/yellow]"
    soat_str = "[green]✅ Sí[/green]" if runt.soat_vigente else "[yellow]⏳ No[/yellow]"
    simit_str = (
        "[green]✅ Paz y salvo[/green]"
        if simit.get("paz_y_salvo")
        else f"[red]⚠ {simit.get('comparendos', '?')} comparendos, ${simit.get('total_deuda', 0):,.0f}[/red]"
        if simit
        else "[dim]No consultado[/dim]"
    )
    recalls_str = (
        f"[yellow]{recalls.get('count', len(dossier.recalls))} abiertos[/yellow]"
        if (recalls.get("count") or dossier.recalls)
        else "[green]0[/green]"
    )

    summary_lines = [
        f"  [bold]{s.model} {s.variant}[/bold] │ {s.generation} │ {s.exterior_color}",
        f"  Motor: [cyan]{epa.get('ev_motor', s.motor_config)}[/cyan] │ {s.range_km} km WLTP │ {s.zero_to_100_kmh}s 0-100 │ {s.top_speed_kmh} km/h",
        "",
        f"  📦 Orden: [cyan]{dossier.order.current.order_status}[/cyan]  │  📋 Tasks: [cyan]{tasks_done}/{tasks_total}[/cyan]  │  📅 Entrega: [bold green]{rs.delivery_date or 'TBD'}[/bold green]",
        f"  🇨🇴 RUNT: [green]{runt.estado or 'N/A'}[/green]  │  🏷️ Placa: {placa_str}  │  🛡️ SOAT: {soat_str}",
        f"  🚦 SIMIT: {simit_str}  │  ⚠️ Recalls: {recalls_str}  │  📊 Quejas NHTSA: [dim]{complaints.get('total', '?')}[/dim]",
        f"  📡 Fuentes: [green]{ok_sources}/{total_sources} OK[/green]  │  🤖 Cron: {mc_data.get('cron_runs', {}).get('total', '?')} runs",
    ]
    con.print(
        Panel(
            "\n".join(summary_lines),
            title="[bold]📊 RESUMEN RÁPIDO[/bold]",
            border_style="bright_blue",
            expand=True,
        )
    )
    con.print()


def _render_status(con, rs) -> None:
    """Render the real status section."""
    phase_color = {
        "delivered": "bold green",
        "delivery_scheduled": "bold cyan",
        "registered": "bold yellow",
        "in_country": "yellow",
        "shipped": "blue",
        "produced": "dim",
        "ordered": "dim",
    }.get(rs.phase, "white")

    _section("🚗 STATUS")
    con.print(f"  [{phase_color}]▸ {rs.phase_description}[/{phase_color}]")
    _kv_table(
        [
            ("Phase", f"[{phase_color}]{rs.phase.upper()}[/{phase_color}]"),
            ("Tesla API", rs.tesla_api_status or "-"),
            ("RUNT Status", rs.runt_status or "(not queried)"),
            ("VIN Assigned", "✅ Yes" if rs.vin_assigned else "❌ No"),
            ("In RUNT", "✅ Yes" if rs.in_runt else "❌ No"),
            ("Has Placa", "✅ Yes" if rs.has_placa else "⏳ Pendiente"),
            ("Has SOAT", "✅ Yes" if rs.has_soat else "⏳ Pendiente"),
            ("Delivery Date", rs.delivery_date or "(not set)"),
            ("Delivery Location", rs.delivery_location or "-"),
            ("Appointment", rs.delivery_appointment or "-"),
        ]
    )
    flags = []
    if rs.is_produced:
        flags.append("✅ Produced")
    if rs.is_shipped:
        flags.append("✅ Shipped")
    if rs.is_in_country:
        flags.append("✅ In Country")
    if rs.is_customs_cleared:
        flags.append("✅ Customs Cleared")
    if rs.is_registered:
        flags.append("✅ RUNT Registered")
    if rs.is_delivery_scheduled:
        flags.append("✅ Delivery Scheduled")
    if rs.is_delivered:
        flags.append("✅ Delivered")
    if flags:
        con.print(f"  [dim]Timeline:[/dim] {' │ '.join(flags)}")


def _render_specs(con, s, epa: dict) -> None:
    """Render the vehicle specs section."""
    _section("📋 VEHICLE SPECS")
    _kv_table(
        [
            ("Model", f"{s.model} {s.variant}"),
            ("Generation", s.generation),
            ("Year", str(s.model_year)),
            ("Factory", s.factory),
            ("Battery", f"{s.battery_type} ~{s.battery_capacity_kwh} kWh"),
            ("Range", f"{s.range_km} km (WLTP est.)"),
            ("Motor", s.motor_config),
            ("Power", f"~{s.horsepower} hp"),
            ("0-100 km/h", f"{s.zero_to_100_kmh}s"),
            ("Top Speed", f"{s.top_speed_kmh} km/h"),
            ("Curb Weight", f"{s.curb_weight_kg} kg"),
            ("Dimensions", s.dimensions),
            ("Seats", str(s.seating)),
            ("Wheels", s.wheels),
            ("Exterior Color", s.exterior_color),
            ("Interior", s.interior),
            ("AP Hardware", s.autopilot_hardware),
            ("FSD", "Yes ✅" if s.has_fsd else "No"),
            ("Supercharging", s.supercharging),
            ("Connectivity", s.connectivity),
        ]
    )


def _render_vin_decode(con, vin: str, vd) -> None:
    """Render the VIN decode section."""
    _section("🔍 VIN DECODE")
    con.print(f"  [bold]{vin}[/bold]")
    _kv_table(
        [
            ("Manufacturer (1-3)", vd.manufacturer),
            ("Model (4)", vd.model),
            ("Body Type (5)", vd.body_type),
            ("Restraint (6)", vd.restraint_system),
            ("Energy (7)", vd.energy_type),
            ("Motor/Battery (8)", vd.motor_battery),
            ("Check Digit (9)", vd.check_digit),
            ("Model Year (10)", vd.model_year),
            ("Plant (11)", vd.plant),
            ("Serial (12-17)", vd.serial_number),
            ("Country", vd.plant_country),
            ("Battery Chemistry", vd.battery_chemistry),
        ]
    )


def _render_option_codes(con, option_codes) -> None:
    """Render the option codes section."""
    if not option_codes.codes:
        return
    _section("🔧 OPTION CODES")
    con.print(f"  [dim]Raw: {option_codes.raw_string}[/dim]")
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Code", style="bold cyan", width=8)
    table.add_column("Category", style="dim", width=14)
    table.add_column("Description")
    for oc in option_codes.codes:
        table.add_row(oc.code, oc.category, oc.description_es or oc.description)
    con.print(table)


def _render_order(con, order) -> None:
    """Render the order section."""
    _section("📦 ORDER")
    _kv_table(
        [
            ("Reservation #", order.reservation_number),
            ("Vehicle Map ID", str(order.vehicle_map_id)),
            ("Status", order.current.order_status),
            ("Substatus", order.current.order_substatus),
            ("Country", order.country_code),
            ("Locale", order.locale),
            ("B2B", "Yes" if order.is_b2b else "No"),
            ("Used Vehicle", "Yes" if order.is_used else "No"),
            ("Tesla Assist", "Yes" if order.is_tesla_assist_enabled else "No"),
            ("History Entries", str(len(order.history))),
        ]
    )
    if order.current.delivery_window_start:
        con.print(
            f"  [dim]Delivery window: {order.current.delivery_window_start} – {order.current.delivery_window_end}[/dim]"
        )


def _render_runt(con, r) -> None:
    """Render the RUNT section."""
    _section(
        f"🇨🇴 RUNT — Registro Nacional de Tránsito  [dim](queried: {str(r.queried_at)[:16]})[/dim]"
    )
    if r.estado:
        estado_color = "green" if r.estado == "REGISTRADO" else "yellow"
        con.print(f"  Estado: [{estado_color}][bold]{r.estado}[/bold][/{estado_color}]")
        _kv_table(
            [
                ("Placa", r.placa if r.placa else "⏳ Pendiente (no asignada)"),
                ("ID Automotor", str(r.id_automotor) if r.id_automotor else "-"),
                ("Licencia Tránsito", r.licencia_transito or "-"),
                ("Tarjeta Registro", r.tarjeta_registro or "-"),
                ("Clase Vehículo", r.clase_vehiculo),
                ("Clasificación", r.clasificacion),
                ("Tipo Servicio", r.tipo_servicio or "-"),
                ("Marca", r.marca),
                ("Línea", r.linea),
                ("Modelo Año", r.modelo_ano),
                ("Color", r.color),
                ("N° Serie", r.numero_serie or "-"),
                ("N° Motor", r.numero_motor or "-"),
                ("N° Chasis", r.numero_chasis or "-"),
                ("VIN", r.numero_vin),
                ("Tipo Combustible", r.tipo_combustible),
                ("Tipo Carrocería", r.tipo_carroceria),
                ("Cilindraje", r.cilindraje or "0"),
                ("Puertas", str(r.puertas)),
                ("Peso Bruto (kg)", str(r.peso_bruto_kg)),
                ("Capacidad Carga", r.capacidad_carga or "-"),
                ("Pasajeros", str(r.capacidad_pasajeros)),
                ("N° Ejes", str(r.numero_ejes)),
                ("Gravámenes", "⚠️ SÍ" if r.gravamenes else "✅ NO"),
                ("Prendas", "⚠️ SÍ" if r.prendas else "✅ NO"),
                ("Repotenciado", "SÍ" if r.repotenciado else "NO"),
                ("Blindaje", "SÍ" if r.blindaje else "NO"),
                ("Antiguo/Clásico", "SÍ" if r.antiguo_clasico else "NO"),
                (
                    "Regrab. Motor",
                    f"SÍ — {r.num_regrabacion_motor}" if r.regrabacion_motor else "NO ✅",
                ),
                (
                    "Regrab. Chasis",
                    f"SÍ — {r.num_regrabacion_chasis}" if r.regrabacion_chasis else "NO ✅",
                ),
                (
                    "Regrab. Serie",
                    f"SÍ — {r.num_regrabacion_serie}" if r.regrabacion_serie else "NO ✅",
                ),
                ("Regrab. VIN", f"SÍ — {r.num_regrabacion_vin}" if r.regrabacion_vin else "NO ✅"),
                ("SOAT Vigente", "✅ Vigente" if r.soat_vigente else "❌ No registrado"),
                ("SOAT Aseguradora", r.soat_aseguradora or "-"),
                ("SOAT Vencimiento", r.soat_vencimiento or "-"),
                (
                    "RTM Vigente",
                    "✅ Vigente" if r.tecnomecanica_vigente else "No aplica (vehículo nuevo)",
                ),
                ("RTM Vencimiento", r.tecnomecanica_vencimiento or "-"),
                ("Fecha Matrícula", r.fecha_matricula or "-"),
                ("Fecha Registro", r.fecha_registro or "-"),
                ("Autoridad Tránsito", r.autoridad_transito or "-"),
                ("Días Matriculado", str(r.dias_matriculado) if r.dias_matriculado else "-"),
                ("Importación", str(r.importacion)),
                ("País Origen", r.nombre_pais or "-"),
                ("Validación DIAN", r.validacion_dian or "-"),
                ("Subpartida", r.subpartida or "-"),
                ("N° Identificación", r.no_identificacion or "-"),
            ]
        )
    else:
        con.print("  [yellow]RUNT not queried yet. Run: tesla dossier build[/yellow]")


def _render_logistics(con, lg) -> None:
    """Render the logistics & shipping section."""
    _section("🚢 LOGISTICS & SHIPPING")
    _kv_table(
        [
            ("Factory", lg.factory),
            ("Departure Port", lg.departure_port),
            ("Arrival Port", lg.arrival_port),
            ("Destination", lg.destination_country),
            ("Est. Transit", f"~{lg.estimated_transit_days} days"),
            ("Customs Status", lg.customs_status or "-"),
            ("Last Mile Status", lg.last_mile_status or "-"),
        ]
    )
    ship = lg.ship
    if ship.vessel_name:
        con.print(f"\n  [bold]Ship: {ship.vessel_name}[/bold]")
        _kv_table(
            [
                ("IMO", ship.imo or "-"),
                ("MMSI", ship.mmsi or "-"),
                ("ETA", ship.eta or "-"),
                ("Track URL", ship.tracking_url or "-"),
            ]
        )
        pos = ship.current_position
        if pos.latitude or pos.longitude:
            con.print(
                f"  [dim]Position: {pos.latitude:.2f}°, {pos.longitude:.2f}° "
                f"| Speed: {pos.speed_knots} kn | Course: {pos.course}°[/dim]"
            )


def _render_recalls(con, recalls, mc_data: dict) -> None:
    """Render the recalls section."""
    _section("⚠️  RECALLS (NHTSA)")
    mc_recalls = mc_data.get("nhtsa_recalls", {})
    recall_count = mc_recalls.get("count", len(recalls))
    if mc_recalls.get("recalls"):
        con.print(f"  [bold yellow]{recall_count} recall(s) found[/bold yellow]")
        table = Table(show_header=True, header_style="bold yellow", box=None, padding=(0, 2))
        table.add_column("ID", style="bold", width=12)
        table.add_column("Date", width=12)
        table.add_column("Component", width=35)
        table.add_column("Remedy")
        for rec in mc_recalls["recalls"]:
            table.add_row(
                rec.get("id", "-"),
                rec.get("date", "-"),
                rec.get("component", "-"),
                (rec.get("remedy", "") or "")[:80]
                + ("…" if len(rec.get("remedy", "")) > 80 else ""),
            )
        con.print(table)
    elif recalls:
        con.print(f"  [bold yellow]{len(recalls)} recall(s) found[/bold yellow]")
        for rec in recalls:
            con.print(f"  [red]{rec.recall_id}[/red] ({rec.date}) — {rec.component}")
            con.print(f"    [dim]{rec.description[:120]}...[/dim]")
    else:
        con.print("  [green]No recalls found ✅[/green]")


def _render_account(con, account) -> None:
    """Render the Tesla account section."""
    _section("👤 TESLA ACCOUNT")
    _kv_table(
        [
            ("Name", account.full_name),
            ("Email", account.email),
            ("Vault UUID", account.vault_uuid),
            ("Signaling", str(account.feature_config.get("signaling", {}).get("enabled", "-"))),
            ("Service Scheduling", "Yes ✅" if account.service_scheduling_enabled else "No"),
        ]
    )


def _render_simit(con, simit, mc_data: dict) -> None:
    """Render the SIMIT traffic fines section."""
    mc_simit = mc_data.get("simit", {})
    has_simit = simit.cedula or mc_simit
    if not has_simit:
        return
    cedula = simit.cedula or mc_simit.get("cedula", "")
    comparendos = simit.comparendos if simit.cedula else mc_simit.get("comparendos", 0)
    multas = simit.multas if simit.cedula else mc_simit.get("multas", 0)
    total = simit.total_deuda if simit.cedula else mc_simit.get("total_deuda", 0.0)
    paz = simit.paz_y_salvo if simit.cedula else mc_simit.get("paz_y_salvo", total == 0)
    _section(f"🚦 SIMIT — Multas de Tránsito  [dim](cédula: {cedula})[/dim]")
    paz_str = "[green]✅ PAZ Y SALVO[/green]" if paz else "[red]⚠️ TIENE DEUDAS[/red]"
    con.print(
        f"  Comparendos: [bold]{comparendos}[/bold]  │  "
        f"Multas: [bold]{multas}[/bold]  │  "
        f"Total: [bold]${total:,.0f}[/bold]  │  {paz_str}"
    )


def _render_epa(con, epa: dict) -> None:
    """Render the EPA specs section."""
    if not epa:
        return
    _section("⚡ EPA SPECS (Official)")
    _kv_table(
        [
            ("Make/Model", f"{epa.get('make', '')} {epa.get('model', '')} {epa.get('year', '')}"),
            ("Drive", epa.get("drive", "-")),
            ("EV Motor", epa.get("ev_motor", "-")),
            ("Range (combined)", f"{epa.get('range_mi', '-')} mi"),
            ("Range (city)", f"{epa.get('range_city_mi', '-')} mi"),
            ("Range (highway)", f"{epa.get('range_hwy_mi', '-')} mi"),
            ("MPGe (combined)", epa.get("mpge_combined", "-")),
            ("MPGe (city)", epa.get("mpge_city", "-")),
            ("MPGe (highway)", epa.get("mpge_highway", "-")),
            ("Annual Fuel Cost", f"${epa.get('fuel_cost_annual', '-')}"),
            ("FE Score", f"{epa.get('fe_score', '-')}/10"),
            ("GHG Score", f"{epa.get('ghg_score', '-')}/10"),
            ("240V Charge Time", f"{epa.get('charge_240v_hrs', '-')} hrs"),
            ("Vehicle Class", epa.get("vehicle_class", "-")),
            ("5-yr Fuel Savings", f"${epa.get('you_save_spend', '-')} vs avg"),
        ]
    )


def _render_nhtsa(con, mc_data: dict) -> None:
    """Render the NHTSA complaints & investigations section."""
    complaints = mc_data.get("nhtsa_complaints", {})
    investigations = mc_data.get("nhtsa_investigations", {})
    if not complaints and not investigations:
        return
    _section("🔎 NHTSA — Complaints & Investigations")
    if complaints:
        total_c = complaints.get("total", 0)
        injuries = complaints.get("injuries", 0)
        con.print(f"  [bold]Complaints:[/bold] {total_c} total  ({injuries} injuries)")
        by_comp = complaints.get("by_component", {})
        if by_comp:
            table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
            table.add_column("Component", width=50)
            table.add_column("Count", justify="right")
            for comp, cnt in sorted(by_comp.items(), key=lambda x: -x[1])[:10]:
                table.add_row(comp, str(cnt))
            con.print(table)
        recent = complaints.get("recent", [])
        if recent:
            con.print("  [dim]Most recent complaints:[/dim]")
            for c in recent[:3]:
                con.print(f"  [dim]{c.get('date', '')} │ {c.get('component', '')}:[/dim]")
                summary = c.get("summary", "")
                con.print(f"    {summary[:120]}{'…' if len(summary) > 120 else ''}")
    if investigations:
        count_i = investigations.get("count", 0)
        con.print(f"\n  [bold]Investigations:[/bold] {count_i}")
        for inv in investigations.get("investigations", [])[:5]:
            subj = inv.get("subject", "")
            con.print(f"  [dim]•[/dim] {subj}")
        if count_i > 5:
            con.print(f"  [dim]... and {count_i - 5} more[/dim]")


def _render_tesla_tasks(con, tasks: dict) -> None:
    """Render the Tesla delivery tasks section."""
    if not tasks:
        return
    _section("✅ TESLA DELIVERY TASKS")
    task_labels = {
        "registration": "Registration",
        "financing": "Financing",
        "scheduling": "Scheduling",
        "finalPayment": "Final Payment",
        "agreements": "Agreements",
        "deliveryAcceptance": "Delivery Acceptance",
    }
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Task", width=22)
    table.add_column("Complete", width=10)
    table.add_column("Enabled", width=10)
    table.add_column("Status")
    for key, label in task_labels.items():
        task = tasks.get(key, {})
        complete = task.get("complete", False)
        enabled = task.get("enabled", False)
        status = task.get("status") or "-"
        complete_str = "✅ Done" if complete else ("⏳" if enabled else "🔒 Disabled")
        enabled_str = "Yes" if enabled else "No"
        table.add_row(label, complete_str, enabled_str, status)
    con.print(table)


def _render_delivery(con, mc_data: dict) -> None:
    """Render the delivery details section."""
    delivery = mc_data.get("delivery", {})
    if not delivery or not delivery.get("delivery_details", {}).get("enabled"):
        return
    dd = delivery["delivery_details"]
    timing = dd.get("deliveryTiming", {})
    _section("📅 DELIVERY DETAILS")
    _kv_table(
        [
            ("Appointment", timing.get("appointment", "-")),
            ("Location", timing.get("pickupLocationTitle", "-")),
            ("Address", timing.get("formattedAddressSingleLine", "-")),
            ("Disclaimer", timing.get("disclaimer", "-")),
            ("Duration", f"{timing.get('duration', '-')} min"),
        ]
    )


def _render_monitor(con, mc_data: dict) -> None:
    """Render the cron monitor status section."""
    cron_runs = mc_data.get("cron_runs", {})
    if not cron_runs:
        return
    _section("🤖 MONITOR STATUS")
    total_runs = cron_runs.get("total", 0)
    ok_runs = cron_runs.get("ok", 0)
    err_runs = cron_runs.get("errors", 0)
    cron_job = mc_data.get("cron_job", {})
    con.print(
        f"  Runs: [bold]{total_runs}[/bold]  │  "
        f"OK: [green]{ok_runs}[/green]  │  "
        f"Errors: [{'red' if err_runs else 'dim'}]{err_runs}[/{'red' if err_runs else 'dim'}]  │  "
        f"Schedule: {cron_job.get('schedule', '-')}  │  "
        f"Status: [{'green' if cron_job.get('last_status') == 'ok' else 'red'}]"
        f"{cron_job.get('last_status', '-')}[/{'green' if cron_job.get('last_status') == 'ok' else 'red'}]"
    )
    last_run = cron_runs.get("runs", [{}])[0]
    if last_run.get("summary"):
        summary_lines = last_run["summary"].strip().split("\n")
        con.print(
            f"  [dim]Last run ({str(last_run.get('timestamp', ''))[:16]}): "
            f"{summary_lines[0][:100]}[/dim]"
        )


def _render_sources(con, mc_data: dict) -> None:
    """Render the data sources status section."""
    sources = mc_data.get("sources", {})
    if not sources:
        return
    _section("📡 DATA SOURCES")
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Source", width=25)
    table.add_column("Status", width=8)
    table.add_column("Last Updated")
    for src_name, src_info in sources.items():
        ok = src_info.get("ok", False)
        ts = str(src_info.get("ts", "-"))[:19]
        status_str = "[green]✅ OK[/green]" if ok else "[red]❌ Error[/red]"
        table.add_row(src_name.replace("_", " ").title(), status_str, ts)
    con.print(table)


def _render_meta(con, dossier, mc_data: dict) -> None:
    """Render the dossier meta section."""
    _section("📊 DOSSIER META")
    _kv_table(
        [
            ("Version", dossier.dossier_version),
            ("Created", str(dossier.created_at)[:19]),
            ("Last Updated", str(dossier.last_updated)[:19]),
            ("Update Count", str(dossier.update_count)),
        ]
    )
    if mc_data.get("generated_at_local"):
        con.print(f"  [dim]Mission Control: {str(mc_data['generated_at_local'])[:19]}[/dim]")


@dossier_app.command("history")
def dossier_history() -> None:
    """Show all historical snapshots of the dossier."""
    backend = DossierBackend()
    history = backend.get_history()

    if not history:
        console.print("[yellow]No history yet. Run: tesla dossier build[/yellow]")
        raise typer.Exit(1)

    if is_json_mode():
        console.print_json(json.dumps(history, indent=2))
        return

    table = Table(title="Dossier Snapshots", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim")
    table.add_column("Timestamp")
    table.add_column("Status")
    table.add_column("File")

    for i, snap in enumerate(history, 1):
        table.add_row(str(i), snap["timestamp"][:19], snap["order_status"], snap["file"])

    console.print(table)


@dossier_app.command("ships")
def dossier_ships() -> None:
    """Show Tesla car carrier ships currently being tracked."""
    from tesla_cli.core.backends.dossier import fetch_tesla_ships

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=is_json_mode(),
    ) as progress:
        progress.add_task("Fetching ship tracking data...", total=None)
        ships = fetch_tesla_ships()

    if is_json_mode():
        data = [s.model_dump(exclude_none=True) for s in ships]
        console.print_json(json.dumps(data, indent=2, default=str))
        return

    if not ships:
        console.print("[yellow]No ship data available.[/yellow]")
        return

    table = Table(title="Tesla Car Carriers", show_header=True, header_style="bold cyan")
    table.add_column("Vessel", style="bold")
    table.add_column("IMO")
    table.add_column("Position")
    table.add_column("Speed")
    table.add_column("Track")

    for s in ships:
        pos = s.current_position
        pos_str = f"{pos.latitude:.2f}°, {pos.longitude:.2f}°" if pos.latitude else "-"
        speed_str = f"{pos.speed_knots} kn" if pos.speed_knots else "-"
        table.add_row(s.vessel_name, s.imo, pos_str, speed_str, s.tracking_url or "-")

    console.print(table)
    console.print("\n[dim]Tip: Open tracking URLs in browser for real-time position.[/dim]")


@dossier_app.command("set-delivery")
def dossier_set_delivery(
    date: str = typer.Argument(..., help="Delivery date (YYYY-MM-DD)"),
) -> None:
    """Set the confirmed delivery date."""
    backend = DossierBackend()
    dossier = backend._load_dossier()
    if not dossier:
        console.print("[yellow]No dossier found. Run: tesla dossier build[/yellow]")
        raise typer.Exit(1)

    dossier.real_status.delivery_date = date
    dossier.real_status.is_delivery_scheduled = True
    dossier.real_status.phase = "delivery_scheduled"
    dossier.real_status.phase_description = f"Entrega programada: {date}"
    backend._save_dossier(dossier)
    console.print(f"[bold green]Delivery date set: {date}[/bold green]")


@dossier_app.command("vin")
def dossier_vin(
    vin: str = typer.Argument(None, help="VIN to decode (default: configured VIN)"),
) -> None:
    """Decode a Tesla VIN position by position."""
    from tesla_cli.core.backends.dossier import decode_vin
    from tesla_cli.core.config import load_config

    if not vin:
        cfg = load_config()
        vin = cfg.general.default_vin

    if not vin:
        console.print("[red]No VIN provided and none configured.[/red]")
        raise typer.Exit(1)

    decoded = decode_vin(vin)

    if is_json_mode():
        console.print_json(decoded.model_dump_json(indent=2))
        return

    table = Table(title=f"VIN Decode: {vin}", show_header=True, header_style="bold cyan")
    table.add_column("Position", style="bold")
    table.add_column("Char", style="cyan")
    table.add_column("Meaning")

    table.add_row("1-3", vin[0:3], decoded.manufacturer)
    table.add_row("4", vin[3], decoded.model)
    table.add_row("5", vin[4], decoded.body_type)
    table.add_row("6", vin[5], decoded.restraint_system)
    table.add_row("7", vin[6], decoded.energy_type)
    table.add_row("8", vin[7], decoded.motor_battery)
    table.add_row("9", vin[8], f"Check digit: {decoded.check_digit}")
    table.add_row("10", vin[9], f"Model Year {decoded.model_year}")
    table.add_row("11", vin[10], decoded.plant)
    table.add_row("12-17", vin[11:17], f"Serial #{decoded.serial_number}")

    console.print(table)
    console.print(
        f"\n  [dim]Country: {decoded.plant_country} | Battery: {decoded.battery_chemistry}[/dim]"
    )


@dossier_app.command("diff")
def dossier_diff(
    snap_a: str = typer.Argument(
        None, help="Snapshot A: index (1-based) or filename. Default: second-to-last"
    ),
    snap_b: str = typer.Argument(None, help="Snapshot B: index or filename. Default: latest"),
) -> None:
    """Compare two dossier snapshots side by side.

    tesla dossier diff              → compare last two snapshots
    tesla dossier diff 1 2          → compare snapshot #1 vs #2
    tesla dossier diff snapshot_... snapshot_...  → by filename
    """
    import json as _json

    from rich.panel import Panel

    backend = DossierBackend()
    history = backend.get_history()

    if len(history) < 2:
        console.print("[yellow]Need at least 2 snapshots. Run: tesla dossier build[/yellow]")
        raise typer.Exit(1)

    def _resolve_snap(ref: str | None, default_idx: int) -> tuple[dict, str]:
        if ref is None:
            entry = history[default_idx]
        elif ref.isdigit():
            idx = int(ref) - 1
            if idx < 0 or idx >= len(history):
                console.print(
                    f"[red]Snapshot #{ref} not found. There are {len(history)} snapshots.[/red]"
                )
                raise typer.Exit(1)
            entry = history[idx]
        else:
            matches = [h for h in history if ref in h["file"]]
            if not matches:
                console.print(f"[red]No snapshot matching '{ref}'[/red]")
                raise typer.Exit(1)
            entry = matches[0]

        from pathlib import Path

        path = Path(entry["file"])
        try:
            data = _json.loads(path.read_text())
        except Exception as exc:
            console.print(f"[red]Cannot read {path}: {exc}[/red]")
            raise typer.Exit(1)
        return data, entry["timestamp"]

    data_a, ts_a = _resolve_snap(snap_a, -2)
    data_b, ts_b = _resolve_snap(snap_b, -1)

    if is_json_mode():
        diff_result = _compute_diff(data_a, data_b)
        console.print_json(_json.dumps(diff_result, indent=2, default=str))
        return

    console.print()
    console.print(
        Panel(
            f"[dim]A:[/dim] [cyan]{ts_a[:19]}[/cyan]  vs  [dim]B:[/dim] [cyan]{ts_b[:19]}[/cyan]",
            title="[bold]Dossier Diff[/bold]",
            border_style="cyan",
        )
    )

    changes = _compute_diff(data_a, data_b)
    if not changes:
        console.print("  [green]No differences found between the two snapshots.[/green]")
        return

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Symbol", width=3, no_wrap=True)
    table.add_column("Field", width=40, no_wrap=True)
    table.add_column("A (old)", style="red", width=35)
    table.add_column("B (new)", style="green")

    added = changed = removed = 0
    for item in changes:
        sym_str = item["symbol"]
        if sym_str == "+":
            sym = "[bold green]+[/bold green]"
            added += 1
        elif sym_str == "−":
            sym = "[bold red]−[/bold red]"
            removed += 1
        else:
            sym = "[bold yellow]≠[/bold yellow]"
            changed += 1
        table.add_row(
            sym, item["path"], str(item.get("old", ""))[:35], str(item.get("new", ""))[:50]
        )

    console.print(table)
    console.print(
        f"\n  [green]+{added} added[/green]  [yellow]≠{changed} changed[/yellow]  [red]−{removed} removed[/red]"
        f"  │  [dim]{len(changes)} total differences[/dim]"
    )


def _compute_diff(a: dict, b: dict, path: str = "") -> list[dict]:
    """Recursively compute differences between two dicts."""
    changes: list[dict] = []
    all_keys = set(a) | set(b)
    SKIP_KEYS = {"last_updated", "created_at", "update_count", "dossier_version", "queried_at"}

    for key in sorted(all_keys):
        if key in SKIP_KEYS:
            continue
        full_path = f"{path}.{key}" if path else key
        val_a = a.get(key)
        val_b = b.get(key)

        if val_a == val_b:
            continue

        if isinstance(val_a, dict) and isinstance(val_b, dict):
            changes.extend(_compute_diff(val_a, val_b, full_path))
        elif val_a is None and val_b is not None:
            changes.append({"symbol": "+", "path": full_path, "old": None, "new": val_b})
        elif val_a is not None and val_b is None:
            changes.append({"symbol": "−", "path": full_path, "old": val_a, "new": None})
        elif (isinstance(val_a, (list, dict)) or isinstance(val_b, (list, dict))) and (
            len(str(val_a)) > 200 or len(str(val_b)) > 200
        ):
            changes.append(
                {
                    "symbol": "≠",
                    "path": full_path,
                    "old": f"[{type(val_a).__name__}]",
                    "new": f"[{type(val_b).__name__}]",
                }
            )
        else:
            changes.append({"symbol": "≠", "path": full_path, "old": val_a, "new": val_b})

    return changes


@dossier_app.command("checklist")
def dossier_checklist(
    mark: str = typer.Option(
        None, "--mark", "-m", help="Mark an item by number as done (e.g. --mark 3)"
    ),
    reset: bool = typer.Option(False, "--reset", help="Reset all items to unchecked"),
) -> None:
    """Interactive Tesla delivery inspection checklist.

    tesla dossier checklist             → show checklist
    tesla dossier checklist --mark 3    → check off item #3
    tesla dossier checklist --reset     → uncheck everything
    """
    import json as _json
    from pathlib import Path

    CHECKLIST_FILE = Path.home() / ".tesla-cli" / "delivery_checklist.json"

    ITEMS = [
        (
            "Exterior",
            [
                "Panel gaps: check all doors, hood, trunk, frunk are even",
                "Paint: no chips, scratches, swirl marks, or clear-coat bubbles",
                "Glass: no cracks or chips on windshield, rear window, sunroof, side windows",
                "Lights: all headlights, taillights, turn signals, DRL operational",
                "Wheels & tires: no curb rash, correct PSI, no sidewall damage",
                "Body trim: all chrome/plastic trim flush and undamaged",
                "Cameras: Autopilot cameras clean and correctly positioned",
                "Door seals: all door and trunk seals present and seated",
            ],
        ),
        (
            "Interior",
            [
                "Seats: no tears, stains, or misalignment (front + rear)",
                "Dashboard & trim: no cracks, loose panels, or scratches",
                "Touchscreen: no dead pixels, scratches, or touch issues",
                "Rear screen (if equipped): functional",
                "Climate vents: all open/close correctly",
                "Speaker grilles: all intact, no rattles",
                "Steering wheel: no scratches or play beyond spec",
                "Center console: all compartments open/close smoothly",
            ],
        ),
        (
            "Mechanicals",
            [
                "Frunk: opens/closes properly, latch secure",
                "Trunk/liftgate: opens/closes, auto-close working",
                "Charging port: opens/closes, correct connector (NACS/CCS)",
                "Charge cable (if included): no damage",
                "Under-frunk storage: present and clean",
                "12V outlet / USB ports: functional",
                "Door handles: all present and functional (auto-present if equipped)",
                "Key cards (2): both work, tap to unlock",
            ],
        ),
        (
            "Electronics & Software",
            [
                "VIN on door jamb matches registration documents",
                "Software version: check Settings > Software",
                "Mobile app: vehicle appears and can be controlled",
                "Autopilot cameras: all visible in Autopilot settings",
                "Sentry Mode: can be enabled",
                "Music / Media: streaming works over LTE",
                "Navigation: GPS accurate",
            ],
        ),
        (
            "Final",
            [
                "Battery state of charge at delivery (note %)",
                "Walk-around video recorded",
                "All documents received: registration, window sticker, owner's manual",
            ],
        ),
    ]

    # Load/init state
    if CHECKLIST_FILE.exists() and not reset:
        try:
            state: dict = _json.loads(CHECKLIST_FILE.read_text())
        except Exception:
            state = {}
    else:
        state = {}

    if reset:
        state = {}
        CHECKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHECKLIST_FILE.write_text(_json.dumps(state))
        console.print("[green]Checklist reset.[/green]")

    # Flatten items with global index
    flat: list[tuple[str, int, str]] = []  # (section, local_idx, text)
    global_idx = 1
    for section, items in ITEMS:
        for item in items:
            flat.append((section, global_idx, item))
            global_idx += 1

    # Apply mark
    if mark:
        nums = [int(x.strip()) for x in mark.split(",") if x.strip().isdigit()]
        for n in nums:
            if 1 <= n <= len(flat):
                state[str(n)] = not state.get(str(n), False)
        CHECKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHECKLIST_FILE.write_text(_json.dumps(state))

    if is_json_mode():
        result = [
            {"index": f[1], "section": f[0], "item": f[2], "done": state.get(str(f[1]), False)}
            for f in flat
        ]
        console.print_json(_json.dumps(result, indent=2))
        return

    # Render
    from rich.panel import Panel

    done_count = sum(1 for i in range(1, len(flat) + 1) if state.get(str(i), False))
    total = len(flat)

    console.print()
    console.print(
        Panel(
            f"[dim]Progress: [bold]{done_count}/{total}[/bold] items checked "
            f"({'[green]COMPLETE[/green]' if done_count == total else f'[yellow]{total - done_count} remaining[/yellow]'})\n"
            f"[dim]Use [bold]--mark N[/bold] to check/uncheck an item, [bold]--reset[/bold] to start over[/dim]",
            title="[bold]🚗 Tesla Delivery Inspection Checklist[/bold]",
            border_style="cyan",
        )
    )

    current_section = ""
    for section, idx, text in flat:
        if section != current_section:
            console.print(f"\n[bold underline]{section}[/bold underline]")
            current_section = section
        done = state.get(str(idx), False)
        checkbox = "[bold green]✅[/bold green]" if done else "[dim]☐[/dim]"
        if done:
            console.print(f"  {checkbox} [dim]{idx:2d}. {text}[/dim]")
        else:
            console.print(f"  {checkbox} {idx:2d}. {text}")

    if done_count == total:
        console.print("\n  [bold green]All items checked! Enjoy your Tesla! ⚡[/bold green]")
    else:
        console.print("\n  [dim]Run: tesla dossier checklist --mark <N> to check item N[/dim]")


@dossier_app.command("gates")
def dossier_gates() -> None:
    """Show the 13-gate delivery journey from order to keys.

    Maps each gate to the current dossier phase and highlights where you are.
    """
    import json as _json

    from rich.panel import Panel

    backend = DossierBackend()
    dossier = backend._load_dossier()

    # Gate definitions: (id, label, phase_trigger)
    GATES = [
        ("01", "Order Placed", "ordered"),
        ("02", "VIN Assigned", "produced"),
        ("03", "Production Started", "produced"),
        ("04", "Quality Control / Exit", "produced"),
        ("05", "Ready for Transport", "shipped"),
        ("06", "Departed Factory", "shipped"),
        ("07", "At Origin Port", "shipped"),
        ("08", "Departed Origin Port", "shipped"),
        ("09", "In Transit (ocean)", "shipped"),
        ("10", "Arrived Destination Port", "in_country"),
        ("11", "Customs Clearance", "in_country"),
        ("12", "In Transit to Delivery", "delivery_scheduled"),
        ("13", "Delivered 🎉", "delivered"),
    ]

    PHASE_ORDER = [
        "ordered",
        "produced",
        "shipped",
        "in_country",
        "registered",
        "delivery_scheduled",
        "delivered",
    ]

    if dossier:
        current_phase = dossier.real_status.phase
        current_idx = PHASE_ORDER.index(current_phase) if current_phase in PHASE_ORDER else 0
    else:
        current_phase = "ordered"
        current_idx = 0

    def _gate_phase_idx(trigger: str) -> int:
        return PHASE_ORDER.index(trigger) if trigger in PHASE_ORDER else 0

    if is_json_mode():
        gates_out = []
        for gid, label, trigger in GATES:
            phase_i = _gate_phase_idx(trigger)
            status = (
                "complete"
                if phase_i < current_idx
                else ("current" if phase_i == current_idx else "pending")
            )
            gates_out.append({"gate": gid, "label": label, "status": status})
        console.print_json(_json.dumps(gates_out, indent=2))
        return

    vin = dossier.vin if dossier else "(no dossier)"
    phase_label = current_phase.replace("_", " ").title() if current_phase else "Unknown"

    console.print()
    console.print(
        Panel(
            f"[dim]VIN:[/dim] [cyan]{vin}[/cyan]  │  [dim]Current phase:[/dim] [bold]{phase_label}[/bold]",
            title="[bold]🚀 Delivery Journey — 13 Gates[/bold]",
            border_style="cyan",
        )
    )
    console.print()

    for gid, label, trigger in GATES:
        phase_i = _gate_phase_idx(trigger)

        if phase_i < current_idx:
            icon = "✅"
            style = "dim"
            badge = "[dim](done)[/dim]"
        elif phase_i == current_idx:
            icon = "▶"
            style = "bold cyan"
            badge = "[bold cyan]← YOU ARE HERE[/bold cyan]"
        else:
            icon = "○"
            style = "dim"
            badge = ""

        console.print(f"  [{style}]{icon}  Gate {gid}: {label}[/{style}]  {badge}")

    console.print()
    if not dossier:
        console.print("[yellow]No dossier found. Run: tesla dossier build for real data.[/yellow]")


@dossier_app.command("estimate")
def dossier_estimate() -> None:
    """Estimate delivery date based on current phase and community timing data.

    tesla dossier estimate
    tesla -j dossier estimate | jq .estimated_delivery_range
    """
    import json as _json
    from datetime import UTC, datetime, timedelta

    from rich.panel import Panel

    # Community-sourced avg calendar days remaining until delivery, by phase.
    # Format: phase → (optimistic_days, typical_days, conservative_days, note)
    PHASE_ESTIMATES: dict[str, tuple[int, int, int, str]] = {
        "ordered": (45, 120, 240, "Highly variable — depends on allocation, market, and model"),
        "produced": (20, 35, 55, "Vehicle built, waiting for transport slot"),
        "shipped": (12, 22, 35, "On a carrier ship — varies by origin port and route"),
        "in_country": (5, 12, 21, "Cleared customs, in local logistics"),
        "registered": (3, 7, 14, "Registration in progress, delivery center prep"),
        "delivery_scheduled": (0, 2, 5, "Delivery appointment set"),
        "delivered": (0, 0, 0, "Already delivered 🎉"),
    }

    backend = DossierBackend()
    dossier = backend._load_dossier()

    phase = dossier.real_status.phase if dossier else "ordered"

    estimates = PHASE_ESTIMATES.get(phase, PHASE_ESTIMATES["ordered"])
    optimistic, typical, conservative, note = estimates

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    opt_date = now + timedelta(days=optimistic)
    typ_date = now + timedelta(days=typical)
    con_date = now + timedelta(days=conservative)

    confirmed_delivery = ""
    if dossier and dossier.real_status.delivery_date:
        confirmed_delivery = str(dossier.real_status.delivery_date)[:10]

    result = {
        "current_phase": phase,
        "optimistic_days": optimistic,
        "typical_days": typical,
        "conservative_days": conservative,
        "estimated_delivery_range": {
            "optimistic": opt_date.strftime("%Y-%m-%d"),
            "typical": typ_date.strftime("%Y-%m-%d"),
            "conservative": con_date.strftime("%Y-%m-%d"),
        },
        "confirmed_delivery_date": confirmed_delivery or None,
        "note": note,
        "data_source": "community-sourced estimates — actual dates vary",
    }

    if is_json_mode():
        console.print_json(_json.dumps(result, indent=2))
        return

    phase_label = phase.replace("_", " ").title()

    # If already delivered
    if phase == "delivered":
        console.print(
            Panel.fit(
                "[bold green]🎉 Delivered![/bold green]\n\n"
                "Your vehicle has been delivered.\n"
                "Run [bold]tesla dossier show[/bold] for full details.",
                border_style="green",
            )
        )
        return

    if confirmed_delivery:
        console.print()
        console.print(
            Panel(
                f"[bold green]📅 Confirmed delivery date: {confirmed_delivery}[/bold green]\n"
                f"[dim]Phase: {phase_label} · Set with: tesla dossier set-delivery {confirmed_delivery}[/dim]",
                title="[bold]Delivery Estimate[/bold]",
                border_style="green",
            )
        )
        return

    # Phase progress bar  (7 phases)
    PHASE_ORDER = [
        "ordered",
        "produced",
        "shipped",
        "in_country",
        "registered",
        "delivery_scheduled",
        "delivered",
    ]
    phase_idx = PHASE_ORDER.index(phase) if phase in PHASE_ORDER else 0
    progress_bar = ""
    for i, _p in enumerate(PHASE_ORDER):
        if i < phase_idx:
            progress_bar += "[dim]●[/dim]"
        elif i == phase_idx:
            progress_bar += "[bold cyan]●[/bold cyan]"
        else:
            progress_bar += "[dim]○[/dim]"

    body = (
        f"Phase:  [bold cyan]{phase_label}[/bold cyan]  {progress_bar}\n\n"
        f"  Optimistic:    [green]{opt_date.strftime('%Y-%m-%d')}[/green]  [dim](+{optimistic}d)[/dim]\n"
        f"  Typical:       [yellow]{typ_date.strftime('%Y-%m-%d')}[/yellow]  [dim](+{typical}d)[/dim]\n"
        f"  Conservative:  [red]{con_date.strftime('%Y-%m-%d')}[/red]  [dim](+{conservative}d)[/dim]\n\n"
        f"[dim]{note}[/dim]\n\n"
        "[dim]Set confirmed date: [bold]tesla dossier set-delivery YYYY-MM-DD[/bold][/dim]"
    )

    console.print()
    console.print(
        Panel(
            body,
            title="[bold]📅 Delivery Estimate[/bold]",
            border_style="cyan",
            subtitle="[dim]community-sourced data — varies by market[/dim]",
        )
    )

    if not dossier:
        console.print(
            "\n[yellow]No dossier found — estimates based on 'ordered' phase. Run: tesla dossier build[/yellow]"
        )


@dossier_app.command("option-codes")
def dossier_option_codes() -> None:
    """Decode and display all option codes from the current dossier.

    tesla dossier option-codes
    tesla -j dossier option-codes | jq '.[] | select(.category == "autopilot")'
    """
    import json as _json

    from rich.table import Table

    from tesla_cli.core.backends.dossier import decode_option_codes

    backend = DossierBackend()
    dossier = backend._load_dossier()

    if not dossier:
        console.print("[yellow]No dossier found. Run: tesla dossier build[/yellow]")
        raise typer.Exit(1)

    raw = dossier.option_codes.raw_string if dossier.option_codes else ""
    if not raw:
        # Try to find option codes in raw order data
        try:
            raw = dossier.order.current.get("mktOptions", "") or ""
        except Exception:
            raw = ""

    if not raw:
        console.print(
            "[yellow]No option codes found in dossier. Try rebuilding: tesla dossier build[/yellow]"
        )
        raise typer.Exit(1)

    decoded = decode_option_codes(raw)

    if is_json_mode():
        out = [
            {"code": c.code, "category": c.category, "description": c.description}
            for c in decoded.codes
        ]
        console.print_json(_json.dumps(out, indent=2))
        return

    # Group by category
    from collections import defaultdict

    by_cat: dict[str, list] = defaultdict(list)
    for c in decoded.codes:
        by_cat[c.category].append(c)

    # Category display order
    CAT_ORDER = [
        "model",
        "motor",
        "paint",
        "interior",
        "wheels",
        "seats",
        "autopilot",
        "charging",
        "connectivity",
        "features",
        "hardware",
        "unknown",
    ]

    total = len(decoded.codes)
    known = sum(1 for c in decoded.codes if c.category != "unknown")

    console.print()
    console.print(f"  [dim]Raw:[/dim] [cyan]{raw}[/cyan]")
    console.print(f"  [dim]{total} codes · {known} decoded · {total - known} unknown[/dim]\n")

    for cat in CAT_ORDER:
        codes = by_cat.get(cat, [])
        if not codes:
            continue
        console.print(f"[bold underline]{cat.title()}[/bold underline]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Code", style="bold cyan", width=8)
        table.add_column("Description")
        for c in codes:
            table.add_row(c.code, c.description)
        console.print(table)
        console.print()


# ── Helpers ──


def _section(title: str) -> None:
    console.print(f"\n[bold underline]{title}[/bold underline]")


def _kv_table(rows: list[tuple[str, str]]) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim", width=20)
    table.add_column("Value")
    for k, v in rows:
        if v:
            table.add_row(k, v)
    console.print(table)


@dossier_app.command("clean")
def dossier_clean(
    keep: int = typer.Option(10, "--keep", "-n", help="Number of snapshots to keep (most recent)"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without deleting"
    ),
) -> None:
    """Prune old dossier snapshots, keeping the N most recent.

    tesla dossier clean             # keep last 10
    tesla dossier clean --keep 5    # keep last 5
    tesla dossier clean --dry-run   # preview without deleting
    """
    import json as _json

    from tesla_cli.core.backends.dossier import SNAPSHOTS_DIR

    if not SNAPSHOTS_DIR.exists():
        console.print("[yellow]No snapshots directory found.[/yellow]")
        return

    all_snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
    total = len(all_snaps)

    if total <= keep:
        if is_json_mode():
            console.print(_json.dumps({"deleted": 0, "kept": total, "files_removed": []}, indent=2))
            return
        console.print(f"  [green]Nothing to clean[/green] — {total} snapshot(s), keep={keep}")
        return

    to_delete = all_snaps[: total - keep]
    to_keep = all_snaps[total - keep :]

    removed_names = [f.name for f in to_delete]

    if not dry_run:
        for f in to_delete:
            f.unlink(missing_ok=True)

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "deleted": len(to_delete),
                    "kept": len(to_keep),
                    "dry_run": dry_run,
                    "files_removed": removed_names,
                },
                indent=2,
            )
        )
        return

    verb = "Would delete" if dry_run else "Deleted"
    console.print(
        f"  {verb} [red]{len(to_delete)}[/red] snapshot(s), kept [green]{len(to_keep)}[/green]"
    )
    if dry_run:
        for name in removed_names:
            console.print(f"    [dim]- {name}[/dim]")


@dossier_app.command("battery-health")
def dossier_battery_health(
    limit: int = typer.Option(50, "--limit", "-n", help="Max snapshots to analyze"),
) -> None:
    """Estimate battery degradation from dossier snapshot history.

    Computes estimated rated range per snapshot and shows the trend.
    The more `tesla dossier build` runs you have, the more accurate this is.

    tesla dossier battery-health
    tesla dossier battery-health --limit 100
    tesla -j dossier battery-health
    """
    import json as _json
    import statistics

    from tesla_cli.core.backends.dossier import SNAPSHOTS_DIR

    if not SNAPSHOTS_DIR.exists():
        console.print("[yellow]No snapshots found. Run: tesla dossier build[/yellow]")
        raise typer.Exit(1)

    all_snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))[-limit:]
    if len(all_snaps) < 2:
        console.print(
            f"[yellow]Need at least 2 snapshots (found {len(all_snaps)}). "
            "Run `tesla dossier build` more often.[/yellow]"
        )
        raise typer.Exit(1)

    points = []
    for snap_path in all_snaps:
        try:
            snap = _json.loads(snap_path.read_text())
            cs = snap.get("charge_state") or snap.get("vehicle", {}).get("charge_state") or {}
            battery_level = cs.get("battery_level") or cs.get("usable_battery_level")
            battery_range = cs.get("battery_range") or cs.get("ideal_battery_range")
            timestamp = snap.get("last_updated") or snap.get("timestamp") or snap_path.stem
            if battery_level and battery_range and float(battery_level) > 10:
                rated = float(battery_range) / (float(battery_level) / 100.0)
                points.append(
                    {
                        "timestamp": str(timestamp)[:16],
                        "battery_level": float(battery_level),
                        "battery_range_mi": float(battery_range),
                        "estimated_rated_range_mi": round(rated, 1),
                    }
                )
        except Exception:
            continue

    if not points:
        console.print("[yellow]No charge state data found in snapshots.[/yellow]")
        raise typer.Exit(1)

    rated_ranges = [p["estimated_rated_range_mi"] for p in points]
    earliest_rated = rated_ranges[0]
    latest_rated = rated_ranges[-1]
    peak_rated = max(rated_ranges)
    degradation_pct = round((1 - latest_rated / peak_rated) * 100, 1) if peak_rated > 0 else 0.0
    avg_rated = round(statistics.mean(rated_ranges), 1)

    summary = {
        "snapshots_analyzed": len(points),
        "earliest_estimated_range_mi": round(earliest_rated, 1),
        "latest_estimated_range_mi": round(latest_rated, 1),
        "peak_estimated_range_mi": round(peak_rated, 1),
        "avg_estimated_range_mi": avg_rated,
        "estimated_degradation_pct": degradation_pct,
        "data_points": points,
    }

    if is_json_mode():
        console.print(_json.dumps(summary, indent=2, default=str))
        return

    from rich.table import Table

    console.print()

    # Summary panel
    deg_color = "green" if degradation_pct < 5 else "yellow" if degradation_pct < 10 else "red"
    console.print(f"  [bold]Battery Health[/bold] — {len(points)} snapshots analyzed")
    console.print(f"  Peak estimated range : [bold]{peak_rated:.0f} mi[/bold]")
    console.print(f"  Latest estimated range: [bold]{latest_rated:.0f} mi[/bold]")
    console.print(f"  Estimated degradation: [{deg_color}]{degradation_pct}%[/{deg_color}]")
    console.print(f"  Average rated range  : [dim]{avg_rated:.0f} mi[/dim]")
    console.print()

    # Recent data table (last 10 points)
    table = Table(
        title="Estimated Rated Range Over Time (last 10 readings)", header_style="bold cyan"
    )
    table.add_column("Timestamp", width=17)
    table.add_column("Batt %", justify="right", width=7)
    table.add_column("Range mi", justify="right", width=9)
    table.add_column("Est. Rated mi", justify="right", width=13)

    for p in points[-10:]:
        table.add_row(
            p["timestamp"],
            f"{p['battery_level']:.0f}%",
            f"{p['battery_range_mi']:.0f}",
            f"{p['estimated_rated_range_mi']:.0f}",
        )
    console.print(table)
    console.print(
        "\n  [dim]Tip: higher sample count = more accurate. "
        "Run `tesla dossier build` regularly to accumulate data.[/dim]"
    )


@dossier_app.command("export-pdf")
def dossier_export_pdf(
    output: str = typer.Option("dossier.pdf", "--output", "-o", help="Output PDF file path"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
) -> None:
    """Export the dossier to a formatted PDF report.

    tesla dossier export-pdf
    tesla dossier export-pdf --output ~/Desktop/my-tesla.pdf
    """
    try:
        from fpdf import FPDF  # type: ignore[import]
    except ImportError:
        console.print(
            "[red]fpdf2 is required for PDF export.[/red]\n"
            "Install with: [bold]uv pip install fpdf2[/bold]"
        )
        raise typer.Exit(1)

    import json as _json
    from pathlib import Path

    from tesla_cli.core.backends.dossier import SNAPSHOTS_DIR

    # Load the latest snapshot if available
    snap_data: dict = {}
    if SNAPSHOTS_DIR.exists():
        snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
        if snaps:
            try:
                snap_data = _json.loads(snaps[-1].read_text())
            except Exception:
                snap_data = {}

    # Gather data sections
    charge_state = (
        snap_data.get("charge_state") or snap_data.get("vehicle", {}).get("charge_state") or {}
    )
    config_data = snap_data.get("vehicle_config") or {}
    order_status = snap_data.get("order_status") or {}
    recalls = snap_data.get("nhtsa_recalls") or []
    vin_decoded = snap_data.get("vin_decode") or {}
    generated_at = snap_data.get("last_updated") or snap_data.get("timestamp") or "unknown"

    # Resolve VIN
    from tesla_cli.core.config import load_config

    cfg = load_config()
    resolved_vin = vin or snap_data.get("vin") or cfg.general.default_vin or "unknown"

    # --- Build PDF ---
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_fill_color(26, 26, 26)
    pdf.set_text_color(255, 255, 255)
    pdf.rect(0, 0, 210, 40, "F")
    pdf.set_xy(10, 10)
    pdf.cell(0, 10, "Tesla Vehicle Dossier", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(10, 22)
    pdf.cell(0, 8, f"VIN: {resolved_vin}   |   Generated: {str(generated_at)[:19]}")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(25)

    def section(title: str) -> None:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(0, 8, f"  {title}", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.ln(2)

    def row(label: str, value: str) -> None:
        if not value or value in ("None", "none", ""):
            return
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(60, 6, f"  {label}:", ln=False)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, str(value)[:80], ln=True)

    # Section 1: Vehicle Identity
    section("Vehicle Identity")
    row("VIN", resolved_vin)
    row("Model", vin_decoded.get("model") or config_data.get("car_type", ""))
    row("Year", vin_decoded.get("model_year") or str(config_data.get("model_year", "")))
    row("Plant", vin_decoded.get("manufacturer") or "")
    row("Exterior Color", config_data.get("exterior_color", ""))
    row("Wheel Type", config_data.get("wheel_type", ""))
    row("Battery Type", config_data.get("battery_type", ""))
    row("Drive Unit", config_data.get("drive_unit", ""))
    pdf.ln(4)

    # Section 2: Charge State
    section("Battery & Charging")
    row("Battery Level", f"{charge_state.get('battery_level', '')}%")
    row("Battery Range", f"{charge_state.get('battery_range', '')} mi")
    row("Charge Limit", f"{charge_state.get('charge_limit_soc', '')}%")
    row("Charging State", charge_state.get("charging_state", ""))
    row("Energy Added", f"{charge_state.get('charge_energy_added', '')} kWh")
    pdf.ln(4)

    # Section 3: Order Status
    if order_status:
        section("Order & Delivery Status")
        for k, v in order_status.items():
            if v and k not in ("vin",):
                row(k.replace("_", " ").title(), str(v)[:80])
        pdf.ln(4)

    # Section 4: NHTSA Recalls
    section(f"NHTSA Recalls ({len(recalls)} found)")
    if recalls:
        for r in recalls[:10]:
            pdf.set_font("Helvetica", "B", 10)
            recall_id = r.get("NHTSACampaignNumber") or r.get("id") or ""
            pdf.cell(0, 6, f"  Recall {recall_id}", ln=True)
            pdf.set_font("Helvetica", "", 9)
            component = r.get("Component") or r.get("component") or ""
            summary = (r.get("Summary") or r.get("consequence") or "")[:120]
            if component:
                pdf.cell(0, 5, f"    Component: {component[:80]}", ln=True)
            if summary:
                pdf.multi_cell(0, 5, f"    {summary}")
            pdf.ln(1)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, "  No open recalls found.", ln=True)
    pdf.ln(4)

    # Section 5: Snapshot summary
    if SNAPSHOTS_DIR.exists():
        all_snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
        section(f"Snapshot History ({len(all_snaps)} snapshots)")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"  First snapshot: {all_snaps[0].stem if all_snaps else 'none'}", ln=True)
        pdf.cell(0, 6, f"  Latest snapshot: {all_snaps[-1].stem if all_snaps else 'none'}", ln=True)
        pdf.ln(2)

    # Footer
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, "Generated by tesla-cli — https://github.com/dacrypt/tesla", align="C")

    # Save
    out_path = Path(output).expanduser()
    pdf.output(str(out_path))
    console.print(f"  [green]\u2713[/green] PDF report saved to [bold]{out_path}[/bold]")


@dossier_app.command("export-html")
def dossier_export_html(
    output: str = typer.Option("dossier.html", "--output", "-o", help="Output HTML file path"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
    theme: str = typer.Option("dark", "--theme", "-t", help="CSS theme: dark (default) or light"),
) -> None:
    """Export the dossier to a standalone HTML report (no extra dependencies required).

    tesla dossier export-html
    tesla dossier export-html --theme light
    tesla dossier export-html --output ~/Desktop/my-tesla.html --theme light
    """
    import html as _html
    import json as _json
    from pathlib import Path

    from tesla_cli.core.backends.dossier import SNAPSHOTS_DIR

    # Load the latest snapshot if available
    snap_data: dict = {}
    if SNAPSHOTS_DIR.exists():
        snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
        if snaps:
            try:
                snap_data = _json.loads(snaps[-1].read_text())
            except Exception:
                snap_data = {}

    # Gather data sections
    charge_state = (
        snap_data.get("charge_state") or snap_data.get("vehicle", {}).get("charge_state") or {}
    )
    config_data = snap_data.get("vehicle_config") or {}
    order_status = snap_data.get("order_status") or {}
    recalls = snap_data.get("nhtsa_recalls") or []
    vin_decoded = snap_data.get("vin_decode") or {}
    generated_at = snap_data.get("last_updated") or snap_data.get("timestamp") or "unknown"

    from tesla_cli.core.config import load_config as _lc

    cfg = _lc()
    resolved_vin = vin or snap_data.get("vin") or cfg.general.default_vin or "unknown"

    def e(v: object) -> str:
        return _html.escape(str(v)) if v else ""

    def kv_row(label: str, value: object) -> str:
        if not value or str(value) in ("None", "none", ""):
            return ""
        return f"<tr><td class='lbl'>{e(label)}</td><td>{e(value)}</td></tr>"

    # Build sections
    identity_rows = "".join(
        [
            kv_row("VIN", resolved_vin),
            kv_row("Model", vin_decoded.get("model") or config_data.get("car_type", "")),
            kv_row("Year", vin_decoded.get("model_year") or config_data.get("model_year", "")),
            kv_row("Plant", vin_decoded.get("manufacturer", "")),
            kv_row("Exterior Color", config_data.get("exterior_color", "")),
            kv_row("Wheel Type", config_data.get("wheel_type", "")),
            kv_row("Battery Type", config_data.get("battery_type", "")),
            kv_row("Drive Unit", config_data.get("drive_unit", "")),
        ]
    )

    battery_level = charge_state.get("battery_level", "")
    bar_pct = battery_level if isinstance(battery_level, (int, float)) else 0
    battery_rows = "".join(
        [
            kv_row("Battery Level", f"{battery_level}%"),
            kv_row("Battery Range", f"{charge_state.get('battery_range', '')} mi"),
            kv_row("Charge Limit", f"{charge_state.get('charge_limit_soc', '')}%"),
            kv_row("Charging State", charge_state.get("charging_state", "")),
            kv_row("Energy Added", f"{charge_state.get('charge_energy_added', '')} kWh"),
            kv_row("Charger Power", f"{charge_state.get('charger_power', '')} kW"),
        ]
    )
    battery_bar = (
        f"<div class='bar-wrap'><div class='bar' style='width:{bar_pct}%'>{bar_pct}%</div></div>"
        if bar_pct
        else ""
    )

    order_rows = ""
    if order_status:
        order_rows = "".join(
            kv_row(k.replace("_", " ").title(), v)
            for k, v in order_status.items()
            if v and k not in ("vin",)
        )

    recall_items = ""
    if recalls:
        for r in recalls[:10]:
            rid = e(r.get("NHTSACampaignNumber") or r.get("id") or "")
            comp = e(r.get("Component") or r.get("component") or "")
            summ = e((r.get("Summary") or r.get("consequence") or "")[:200])
            recall_items += (
                f"<div class='recall'>"
                f"<strong>Recall {rid}</strong>"
                + (f" — <em>{comp}</em>" if comp else "")
                + (f"<br><span class='dim'>{summ}</span>" if summ else "")
                + "</div>"
            )
    else:
        recall_items = "<p class='dim'>No open recalls found.</p>"

    snap_summary = ""
    if SNAPSHOTS_DIR.exists():
        all_snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
        snap_count = len(all_snaps)
        first = all_snaps[0].stem if all_snaps else "none"
        last = all_snaps[-1].stem if all_snaps else "none"
        snap_summary = (
            f"<p>{snap_count} snapshots — "
            f"first: <code>{e(first)}</code>, latest: <code>{e(last)}</code></p>"
        )

    gen_str = e(str(generated_at)[:19])
    vin_str = e(resolved_vin)

    # ── Theme CSS variables ──────────────────────────────────────────────────
    if theme.lower() == "light":
        _css_root = "--bg: #f5f5f5; --card: #ffffff; --border: #d0d0d0;\n    --text: #1a1a1a; --muted: #666; --accent: #c0001a;\n    --label: #444; --bar-bg: #e0e0e0; --bar-fg: #c0001a;"
        _h2_bg = "#f0f0f0"
        _h2_col = "#333"
        _tr_hover = "rgba(0,0,0,0.04)"
        _code_bg = "#ebebeb"
        _recall_bg = "rgba(192,0,26,0.06)"
    else:  # dark (default)
        _css_root = "--bg: #0d0d0d; --card: #1a1a1a; --border: #2e2e2e;\n    --text: #e8e8e8; --muted: #888; --accent: #e82127;\n    --label: #aaa; --bar-bg: #2e2e2e; --bar-fg: #e82127;"
        _h2_bg = "#222"
        _h2_col = "#ccc"
        _tr_hover = "rgba(255,255,255,0.03)"
        _code_bg = "#222"
        _recall_bg = "rgba(232,33,39,0.07)"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tesla Dossier — {vin_str}</title>
<style>
  :root {{
    {_css_root}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: var(--bg); color: var(--text); padding: 24px; }}
  header {{ background: var(--card); border-bottom: 3px solid var(--accent);
            padding: 24px 32px; border-radius: 8px 8px 0 0; margin-bottom: 2px; }}
  header h1 {{ font-size: 1.8rem; letter-spacing: -0.5px; }}
  header .meta {{ color: var(--muted); font-size: 0.85rem; margin-top: 6px; }}
  .section {{ background: var(--card); border: 1px solid var(--border);
              border-radius: 6px; margin: 16px 0; overflow: hidden; }}
  .section h2 {{ background: {_h2_bg}; padding: 10px 16px; font-size: 0.95rem;
                 letter-spacing: 0.5px; text-transform: uppercase; color: {_h2_col}; }}
  .section .body {{ padding: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 5px 8px; font-size: 0.9rem; }}
  td.lbl {{ color: var(--label); width: 38%; font-weight: 500; }}
  tr:hover {{ background: {_tr_hover}; }}
  .bar-wrap {{ background: var(--bar-bg); border-radius: 4px; height: 18px;
               margin: 8px 0 12px; overflow: hidden; }}
  .bar {{ background: var(--bar-fg); height: 100%; border-radius: 4px;
          font-size: 0.75rem; color: #fff; line-height: 18px; text-align: right;
          padding-right: 6px; min-width: 2rem; transition: width 0.3s; }}
  .recall {{ border-left: 3px solid var(--accent); padding: 8px 12px;
             margin-bottom: 10px; background: {_recall_bg}; border-radius: 0 4px 4px 0; }}
  .recall strong {{ font-size: 0.9rem; }}
  .dim {{ color: var(--muted); font-size: 0.85rem; }}
  code {{ background: {_code_bg}; padding: 2px 5px; border-radius: 3px; font-size: 0.82rem; }}
  footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 32px; }}
  a {{ color: var(--accent); text-decoration: none; }}
</style>
</head>
<body>
<header>
  <h1>&#x1F697; Tesla Vehicle Dossier</h1>
  <div class="meta">VIN: <strong>{vin_str}</strong> &nbsp;|&nbsp; Generated: {gen_str}</div>
</header>

<div class="section">
  <h2>&#x1F4CB; Vehicle Identity</h2>
  <div class="body"><table>{identity_rows}</table></div>
</div>

<div class="section">
  <h2>&#x26A1; Battery &amp; Charging</h2>
  <div class="body">
    {battery_bar}
    <table>{battery_rows}</table>
  </div>
</div>

{'<div class="section"><h2>&#x1F4E6; Order &amp; Delivery Status</h2><div class="body"><table>' + order_rows + "</table></div></div>" if order_rows else ""}

<div class="section">
  <h2>&#x26A0;&#xFE0F; NHTSA Recalls</h2>
  <div class="body">{recall_items}</div>
</div>

<div class="section">
  <h2>&#x1F4F8; Snapshot History</h2>
  <div class="body">{snap_summary}</div>
</div>

<footer>
  Generated by <a href="https://github.com/dacrypt/tesla">tesla-cli</a>
</footer>
</body>
</html>
"""

    out_path = Path(output).expanduser()
    out_path.write_text(html_content, encoding="utf-8")
    console.print(f"  [green]\u2713[/green] HTML report saved to [bold]{out_path}[/bold]")
