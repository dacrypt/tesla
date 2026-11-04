"""``dossier`` commands — tools (see ``__init__.py``).

Names tests patch on ``tesla_cli.cli.commands.dossier`` are looked up as ``_m.<name>``.
"""

from __future__ import annotations

from tesla_cli.cli.commands import dossier as _m
from tesla_cli.cli.commands.dossier import (  # noqa: F401
    Progress,
    SpinnerColumn,
    Table,
    TextColumn,
    console,
    is_json_mode,
    json,
    typer,
)


def dossier_history() -> None:
    """Show all historical snapshots of the dossier."""
    backend = _m.DossierBackend()
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


def dossier_set_delivery(
    date: str = typer.Argument(..., help="Delivery date (YYYY-MM-DD)"),
) -> None:
    """Set the confirmed delivery date."""
    backend = _m.DossierBackend()
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

    backend = _m.DossierBackend()
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


def dossier_gates() -> None:
    """Show the 13-gate delivery journey from order to keys.

    Maps each gate to the current dossier phase and highlights where you are.
    """
    import json as _json

    from rich.panel import Panel

    backend = _m.DossierBackend()
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

    backend = _m.DossierBackend()
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


def dossier_option_codes() -> None:
    """Decode and display all option codes from the current dossier.

    tesla dossier option-codes
    tesla -j dossier option-codes | jq '.[] | select(.category == "autopilot")'
    """
    import json as _json

    from rich.table import Table

    from tesla_cli.core.backends.dossier import decode_option_codes

    backend = _m.DossierBackend()
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


def dossier_sources() -> None:
    """Show all registered data sources with cache status.

    tesla dossier sources
    tesla -j dossier sources
    """
    import json as _json

    from rich.table import Table

    from tesla_cli.cli.output import console, is_json_mode
    from tesla_cli.core.sources import list_sources

    sources = list_sources()

    if is_json_mode():
        console.print_json(_json.dumps(sources, default=str))
        return

    t = Table(title=f"Data Sources ({len(sources)} registered)")
    t.add_column("ID", style="cyan")
    t.add_column("Name")
    t.add_column("Category", style="dim")
    t.add_column("TTL")
    t.add_column("Status", justify="center")
    t.add_column("Last Refresh", style="dim")

    for s in sources:
        ttl_h = s["ttl"] / 3600
        ttl_str = f"{ttl_h:.0f}h" if ttl_h >= 1 else f"{s['ttl'] / 60:.0f}m"

        if s["error"]:
            status = "[red]✗ error[/red]"
        elif s["has_data"] and not s["stale"]:
            status = "[green]✓ fresh[/green]"
        elif s["has_data"] and s["stale"]:
            status = "[yellow]⟳ stale[/yellow]"
        else:
            status = "[dim]— empty[/dim]"

        refreshed = s["refreshed_at"] or "never"
        if isinstance(refreshed, str) and len(refreshed) > 16:
            refreshed = refreshed[:16]

        t.add_row(s["id"], s["name"], s["category"], ttl_str, status, str(refreshed))

    console.print(t)

    fresh = sum(1 for s in sources if s["has_data"] and not s["stale"])
    stale = sum(1 for s in sources if s["has_data"] and s["stale"])
    empty = sum(1 for s in sources if not s["has_data"])
    console.print(
        f"\n  [green]{fresh} fresh[/green]  |  [yellow]{stale} stale[/yellow]  |  "
        f"[dim]{empty} empty[/dim]"
    )
