"""Charge commands: tesla charge status|start|stop|limit|amps|port-open|port-close|schedule|history."""

from __future__ import annotations

import typer

from tesla_cli.cli.commands.vehicle import _with_wake
from tesla_cli.cli.output import (
    console,
    is_json_mode,
    render_model,
    render_success,
)
from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.models.charge import ChargeState

charge_app = typer.Typer(name="charge", help="Battery and charging management.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _backend():
    return get_vehicle_backend(load_config())


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@charge_app.command("status")
def charge_status(
    watch: bool = typer.Option(False, "--watch", "-w", help="Live monitor (refresh every 30s)"),
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
    interval: int = typer.Option(30, "--interval", "-i", help="Watch refresh interval in seconds"),
    vin: str | None = VinOption,
) -> None:
    """Show current charge state.

    tesla charge status                # detailed view
    tesla charge status --oneline      # 🔋 72% | ⚡ 11kW | 1h30m to 80%
    tesla charge status --watch        # live monitor (30s refresh)
    tesla charge status --watch -i 10  # live monitor (10s refresh)
    """
    import time as _time

    from tesla_cli.cli.output import console

    v = _vin(vin)

    def _render_once() -> None:
        data = _with_wake(lambda b, v: b.get_charge_state(v), v)

        if oneline:
            level = data.get("battery_level", "?")
            state = data.get("charging_state", "?")
            parts = [f"\U0001f50b {level}%"]
            if state == "Charging":
                power = data.get("charger_power", 0)
                eta = data.get("time_to_full_charge", 0)
                limit = data.get("charge_limit_soc", "?")
                eta_str = f"{int(eta)}h{int((eta % 1) * 60):02d}m" if eta else ""
                parts.append(f"\u26a1 {power}kW")
                if eta_str:
                    parts.append(f"{eta_str} to {limit}%")
                added = data.get("charge_energy_added", 0)
                if added:
                    parts.append(f"+{added:.1f}kWh")
            else:
                parts.append(state)
            typer.echo(" | ".join(parts))
            return

        cs = ChargeState.model_validate(data)
        render_model(cs, title="Charge State")

        cfg = load_config()
        cost_per_kwh = cfg.general.cost_per_kwh
        energy_added = data.get("charge_energy_added")
        if cost_per_kwh and cost_per_kwh > 0 and energy_added:
            estimated_cost = float(energy_added) * float(cost_per_kwh)
            console.print(
                f"  [dim]Estimated session cost:[/dim] [bold]${estimated_cost:.2f}[/bold] "
                f"[dim]({energy_added} kWh \xd7 ${cost_per_kwh:.4f}/kWh)[/dim]"
            )

    if watch:
        try:
            while True:
                _render_once()
                if not oneline:
                    console.print(f"\n  [dim]Refreshing in {interval}s... (Ctrl+C to stop)[/dim]")
                _time.sleep(interval)
                if not oneline:
                    console.print("\033[2J\033[H", end="")  # clear screen
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")
    else:
        _render_once()


@charge_app.command("start")
def charge_start(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview action without executing"),
    vin: str | None = VinOption,
) -> None:
    """Start charging."""
    v = _vin(vin)
    if dry_run:
        console.print(f"[dim]Dry run:[/dim] Would start charging for VIN ...{v[-6:]}")
        return
    _with_wake(lambda b, v: b.command(v, "charge_start"), v)
    render_success("Charging started")


@charge_app.command("stop")
def charge_stop(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview action without executing"),
    vin: str | None = VinOption,
) -> None:
    """Stop charging."""
    v = _vin(vin)
    if dry_run:
        console.print(f"[dim]Dry run:[/dim] Would stop charging for VIN ...{v[-6:]}")
        return
    _with_wake(lambda b, v: b.command(v, "charge_stop"), v)
    render_success("Charging stopped")


@charge_app.command("limit")
def charge_limit(
    percent: int | None = typer.Argument(
        None, help="Charge limit percentage (50-100). Omit to show current."
    ),
    vin: str | None = VinOption,
) -> None:
    """Show or set charge limit percentage.

    tesla charge limit          → show current limit
    tesla charge limit 80       → set to 80%
    tesla -j charge limit       → JSON output
    """
    import json as _json

    v = _vin(vin)
    if percent is None:
        data = _with_wake(lambda b, v: b.get_charge_state(v), v)
        limit = data.get("charge_limit_soc")
        if is_json_mode():
            console.print(_json.dumps({"charge_limit_soc": limit}))
            return
        render_success(f"Current charge limit: {limit}%")
        return
    if not 50 <= percent <= 100:
        raise typer.BadParameter("Charge limit must be between 50 and 100.")
    _with_wake(lambda b, v: b.command(v, "set_charge_limit", percent=percent), v)
    if is_json_mode():
        console.print(_json.dumps({"charge_limit_soc": percent, "status": "ok"}))
        return
    render_success(f"Charge limit set to {percent}%")


@charge_app.command("amps")
def charge_amps(
    amps: int | None = typer.Argument(None, help="Charging amps (1-48). Omit to show current."),
    vin: str | None = VinOption,
) -> None:
    """Show or set charging amperage.

    tesla charge amps           → show current amps
    tesla charge amps 32        → set to 32A
    tesla -j charge amps        → JSON output
    """
    import json as _json

    v = _vin(vin)
    if amps is None:
        data = _with_wake(lambda b, v: b.get_charge_state(v), v)
        current = data.get("charge_amps") or data.get("charger_actual_current")
        if is_json_mode():
            console.print(_json.dumps({"charge_amps": current}))
            return
        render_success(f"Current charge amps: {current}A")
        return
    if not 1 <= amps <= 48:
        raise typer.BadParameter("Amps must be between 1 and 48.")
    _with_wake(lambda b, v: b.command(v, "set_charging_amps", charging_amps=amps), v)
    if is_json_mode():
        console.print(_json.dumps({"charge_amps": amps, "status": "ok"}))
        return
    render_success(f"Charging amps set to {amps}A")


@charge_app.command("port-open")
def charge_port_open(vin: str | None = VinOption) -> None:
    """Open charge port door."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "charge_port_door_open"), v)
    render_success("Charge port opened")


@charge_app.command("port-close")
def charge_port_close(vin: str | None = VinOption) -> None:
    """Close charge port door."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "charge_port_door_close"), v)
    render_success("Charge port closed")


@charge_app.command("schedule")
def charge_schedule(
    enable: bool = typer.Argument(..., help="Enable or disable scheduled charging"),
    time: int = typer.Option(0, "--time", "-t", help="Minutes after midnight to start charging"),
    vin: str | None = VinOption,
) -> None:
    """Enable/disable scheduled charging."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "set_scheduled_charging", enable=enable, time=time), v)
    status = "enabled" if enable else "disabled"
    render_success(f"Scheduled charging {status}")


@charge_app.command("departure")
def charge_departure(
    time: str = typer.Argument(..., help="Departure time (HH:MM, 24h)"),
    precondition: bool = typer.Option(
        False, "--precondition/--no-precondition", help="Enable cabin preconditioning"
    ),
    off_peak: bool = typer.Option(
        False, "--off-peak/--no-off-peak", help="Enable off-peak charging window"
    ),
    off_peak_end: str = typer.Option(
        "07:00", "--off-peak-end", help="Off-peak charging end time (HH:MM)"
    ),
    disable: bool = typer.Option(False, "--disable", help="Disable scheduled departure"),
    vin: str | None = VinOption,
) -> None:
    """Set scheduled departure time with optional preconditioning and off-peak charging.

    tesla charge departure 07:30
    tesla charge departure 08:00 --precondition
    tesla charge departure 06:00 --off-peak --off-peak-end 07:00
    tesla charge departure --disable
    """
    import json as _json

    v = _vin(vin)

    def _parse_time(t: str) -> int:
        """Convert HH:MM to minutes after midnight."""
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    if disable:
        _with_wake(
            lambda b, v: b.command(v, "set_scheduled_departure", enable=False, departure_time=0),
            v,
        )
        if is_json_mode():
            from tesla_cli.cli.output import console

            console.print(_json.dumps({"scheduled_departure": False}, indent=2))
            return
        render_success("Scheduled departure disabled")
        return

    dep_minutes = _parse_time(time)
    end_minutes = _parse_time(off_peak_end)

    _with_wake(
        lambda b, v: b.command(
            v,
            "set_scheduled_departure",
            enable=True,
            departure_time=dep_minutes,
            preconditioning_enabled=precondition,
            off_peak_charging_enabled=off_peak,
            end_off_peak_time=end_minutes,
        ),
        v,
    )

    if is_json_mode():
        from tesla_cli.cli.output import console

        console.print(
            _json.dumps(
                {
                    "scheduled_departure": True,
                    "time": time,
                    "time_minutes": dep_minutes,
                    "precondition": precondition,
                    "off_peak": off_peak,
                },
                indent=2,
            )
        )
        return

    msg = f"Scheduled departure set to {time}"
    if precondition:
        msg += " with preconditioning"
    if off_peak:
        msg += f" (off-peak until {off_peak_end})"
    render_success(msg)


@charge_app.command("schedule-preview")
def charge_schedule_preview(
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output for tmux/cron"),
    vin: str | None = VinOption,
) -> None:
    """Show current scheduled charge and departure settings in one consolidated view.

    tesla charge schedule-preview
    tesla charge schedule-preview --oneline
    """
    import json as _json

    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_charge_state(v), v)

    # Extract scheduling fields
    sched_mode = data.get("scheduled_charging_mode", "Off")
    sched_start = data.get("scheduled_charging_start_time_app")  # minutes after midnight
    sched_start_utc = data.get("scheduled_charging_start_time")
    dep_mode = data.get("scheduled_departure_time_minutes")  # minutes after midnight
    dep_time = data.get("scheduled_departure_time")  # epoch
    precond = data.get("preconditioning_enabled", False)
    precond_wkd = data.get("preconditioning_weekdays_only", False)
    off_peak = data.get("off_peak_charging_enabled", False)
    off_peak_end = data.get("off_peak_hours_end_time")  # minutes after midnight

    def _minutes_to_hhmm(mins: int | None) -> str:
        if mins is None:
            return "—"
        return f"{int(mins) // 60:02d}:{int(mins) % 60:02d}"

    if oneline:
        parts = []
        if sched_mode and sched_mode != "Off":
            parts.append(f"\U0001f50c Charge @ {_minutes_to_hhmm(sched_start)}")
        else:
            parts.append("\U0001f50c Charge: off")
        if dep_mode:
            parts.append(f"\U0001f697 Depart @ {_minutes_to_hhmm(dep_mode)}")
            if precond:
                parts.append("precond ON")
            if off_peak:
                parts.append(f"off-peak until {_minutes_to_hhmm(off_peak_end)}")
        typer.echo(" | ".join(parts))
        return

    if is_json_mode():
        from tesla_cli.cli.output import console as _con

        _con.print(
            _json.dumps(
                {
                    "scheduled_charging_mode": sched_mode,
                    "scheduled_charging_start": _minutes_to_hhmm(sched_start),
                    "scheduled_charging_start_utc": sched_start_utc,
                    "scheduled_departure_time": _minutes_to_hhmm(dep_mode),
                    "scheduled_departure_epoch": dep_time,
                    "preconditioning_enabled": precond,
                    "preconditioning_weekdays_only": precond_wkd,
                    "off_peak_charging_enabled": off_peak,
                    "off_peak_hours_end_time": _minutes_to_hhmm(off_peak_end),
                },
                indent=2,
            )
        )
        return

    from rich.panel import Panel
    from rich.table import Table

    from tesla_cli.cli.output import console as _con

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("Key", style="dim", width=32)
    t.add_column("Value", style="bold")

    # Scheduled charging section
    t.add_row("[bold cyan]── Scheduled Charging ──[/bold cyan]", "")
    sc_color = "green" if sched_mode and sched_mode != "Off" else "dim"
    t.add_row("Mode", f"[{sc_color}]{sched_mode or 'Off'}[/{sc_color}]")
    if sched_start is not None:
        t.add_row("Start Time", _minutes_to_hhmm(sched_start))

    # Scheduled departure section
    t.add_row("", "")
    t.add_row("[bold cyan]── Scheduled Departure ──[/bold cyan]", "")
    dep_color = "green" if dep_mode else "dim"
    t.add_row("Departure Time", f"[{dep_color}]{_minutes_to_hhmm(dep_mode)}[/{dep_color}]")
    t.add_row("Preconditioning", "[green]On[/green]" if precond else "[dim]Off[/dim]")
    if precond:
        t.add_row("  Weekdays Only", "Yes" if precond_wkd else "No")
    t.add_row("Off-Peak Charging", "[green]On[/green]" if off_peak else "[dim]Off[/dim]")
    if off_peak and off_peak_end is not None:
        t.add_row("  Off-Peak Ends", _minutes_to_hhmm(off_peak_end))

    _con.print(Panel(t, title="[bold]Charge & Departure Schedule[/bold]", border_style="blue"))


@charge_app.command("profile")
def charge_profile(
    limit: int | None = typer.Option(
        None, "--limit", "-l", min=50, max=100, help="Charge limit percent (50–100)"
    ),
    amps: int | None = typer.Option(
        None, "--amps", "-a", min=1, max=48, help="Charge current amps (1–48)"
    ),
    schedule: str | None = typer.Option(
        None, "--schedule", "-s", help="Scheduled charge ON time HH:MM (empty string to disable)"
    ),
    vin: str | None = VinOption,
) -> None:
    """View or set a charge profile (limit + amps + schedule in one command).

    \b
    tesla charge profile                               # show current profile
    tesla charge profile --limit 80                   # set limit only
    tesla charge profile --limit 80 --amps 16         # set limit + amps
    tesla charge profile --limit 80 --amps 16 --schedule 23:00
    tesla -j charge profile
    """
    import json as _json

    from tesla_cli.core.exceptions import VehicleAsleepError

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    b = get_vehicle_backend(cfg)

    # ── No args → show current profile ──────────────────────────────────────
    if limit is None and amps is None and schedule is None:
        try:
            cs = b.get_charge_state(v)
        except VehicleAsleepError:
            console.print("[yellow]Vehicle is asleep. Wake it first.[/yellow]")
            raise typer.Exit(1)

        if is_json_mode():
            console.print(
                _json.dumps(
                    {
                        "charge_limit_soc": cs.get("charge_limit_soc"),
                        "charge_amps": cs.get("charge_amps"),
                        "scheduled_charging_pending": cs.get("scheduled_charging_pending"),
                        "scheduled_charging_start_time": str(
                            cs.get("scheduled_charging_start_time") or ""
                        ),
                    }
                )
            )
            return

        from rich.table import Table

        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_column("k", style="dim", width=26)
        t.add_column("v")
        t.add_row("Charge limit", f"{cs.get('charge_limit_soc', '?')}%")
        t.add_row("Charge amps", f"{cs.get('charge_amps', '?')} A")
        t.add_row("Scheduled pending", str(cs.get("scheduled_charging_pending", "?")))
        t.add_row("Scheduled time", str(cs.get("scheduled_charging_start_time") or "—"))
        console.print(t)
        return

    # ── Set profile fields ───────────────────────────────────────────────────
    results: dict[str, bool] = {}
    if limit is not None:
        r = b.command(v, "set_charge_limit", {"percent": limit})
        results["limit"] = bool(r.get("result"))
    if amps is not None:
        r = b.command(v, "set_charging_amps", {"charging_amps": amps})
        results["amps"] = bool(r.get("result"))
    if schedule is not None:
        if schedule == "":
            r = b.command(v, "set_scheduled_charging", {"enable": False, "time": 0})
        else:
            h, m = (int(x) for x in schedule.split(":"))
            r = b.command(v, "set_scheduled_charging", {"enable": True, "time": h * 60 + m})
        results["schedule"] = bool(r.get("result"))

    ok = all(results.values())

    if is_json_mode():
        console.print(_json.dumps({"ok": ok, "results": results}))
        return

    if ok:
        parts = []
        if limit is not None:
            parts.append(f"limit=[bold]{limit}%[/bold]")
        if amps is not None:
            parts.append(f"amps=[bold]{amps}A[/bold]")
        if schedule is not None:
            parts.append(f"schedule=[bold]{'off' if schedule == '' else schedule}[/bold]")
        render_success("Charge profile updated: " + "  ".join(parts))
    else:
        console.print(f"[red]Some updates failed:[/red] {results}")
        raise typer.Exit(1)


@charge_app.command("schedule-amps")
def charge_schedule_amps(
    schedule_time: str = typer.Argument(
        ..., metavar="HH:MM", help="Scheduled charge start time (24-hour)"
    ),
    amps: int = typer.Argument(..., help="Charge current in amps (1–48)"),
    vin: str | None = VinOption,
) -> None:
    """Enable scheduled charging at a specific time and amperage in one command.

    \b
    tesla charge schedule-amps 02:00 8     # charge at 2 AM with 8 A (off-peak)
    tesla charge schedule-amps 23:30 16    # charge at 11:30 PM with 16 A
    tesla -j charge schedule-amps 02:00 8
    """
    import json as _json

    if amps < 1 or amps > 48:
        console.print("[red]Amps must be between 1 and 48.[/red]")
        raise typer.Exit(1)

    try:
        hh, mm = schedule_time.split(":")
        minutes = int(hh) * 60 + int(mm)
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError
    except ValueError:
        console.print("[red]Invalid time format — use HH:MM (e.g. 02:00)[/red]")
        raise typer.Exit(1)

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    b = get_vehicle_backend(cfg)

    b.command(v, "set_charging_amps", {"charging_amps": amps})
    b.set_scheduled_charging(v, enable=True, time_minutes=minutes)

    if is_json_mode():
        console.print(_json.dumps({"ok": True, "schedule": schedule_time, "amps": amps, "vin": v}))
        return

    render_success(f"Scheduled charging set: [bold]{schedule_time}[/bold] at [bold]{amps} A[/bold]")


@charge_app.command("forecast")
def charge_forecast(vin: str | None = VinOption) -> None:
    """Estimate time to reach charge limit based on current charge rate.

    \b
    tesla charge forecast
    tesla -j charge forecast
    """
    import datetime as _dt
    import json as _json

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    b = get_vehicle_backend(cfg)

    try:
        cs = b.get_charge_state(v)
    except Exception as exc:
        console.print(f"[red]Failed to get charge state:[/red] {exc}")
        raise typer.Exit(1)

    level = cs.get("battery_level") or 0
    limit = cs.get("charge_limit_soc") or 80
    rate_kw = float(cs.get("charger_power") or 0)
    range_mi = float(cs.get("battery_range") or 0)
    ttf_hrs = float(cs.get("time_to_full_charge") or 0)
    state = cs.get("charging_state") or "Unknown"

    # Compute estimated completion time
    if ttf_hrs > 0:
        eta_dt = _dt.datetime.now() + _dt.timedelta(hours=ttf_hrs)
        eta_str = eta_dt.strftime("%H:%M")
        mins = int(ttf_hrs * 60)
        dur_str = f"{mins // 60}h {mins % 60}m" if mins >= 60 else f"{mins}m"
    else:
        eta_str = "—"
        dur_str = "—"

    # kWh needed estimate
    # battery_range gives rated miles at current SOC; scale to full vs limit
    kwh_needed = round(rate_kw * ttf_hrs, 2) if ttf_hrs > 0 and rate_kw > 0 else None

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "battery_level": level,
                    "charge_limit_soc": limit,
                    "charging_state": state,
                    "charger_power_kw": rate_kw,
                    "time_to_full_hrs": ttf_hrs,
                    "time_to_full_str": dur_str,
                    "eta": eta_str,
                    "kwh_needed": kwh_needed,
                    "battery_range_mi": range_mi,
                }
            )
        )
        return

    from rich.table import Table

    t = Table(title="Charge Forecast", show_header=False, box=None, padding=(0, 2))
    t.add_column("k", style="dim", width=22)
    t.add_column("v")

    state_color = "green" if state == "Charging" else "yellow" if state == "Complete" else "dim"
    t.add_row("Status", f"[{state_color}]{state}[/{state_color}]")
    t.add_row("Battery level", f"{level}%")
    t.add_row("Charge limit", f"{limit}%")
    t.add_row("Charger power", f"{rate_kw:.1f} kW" if rate_kw else "—")
    t.add_row("Time to limit", f"[bold]{dur_str}[/bold]" if dur_str != "—" else "—")
    t.add_row("ETA", f"[bold]{eta_str}[/bold]" if eta_str != "—" else "—")
    if kwh_needed is not None:
        t.add_row("Energy to add", f"{kwh_needed:.2f} kWh")
    t.add_row("Range", f"{range_mi:.1f} mi")

    console.print(t)
    if state not in ("Charging",):
        console.print(
            "\n  [dim]Vehicle is not currently charging — connect to a charger to get a live forecast.[/dim]"
        )


@charge_app.command("history")
def charge_history(
    vin: str | None = VinOption,  # noqa: ARG001
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
) -> None:
    """Show charging history (Fleet API) or redirect to TeslaMate."""
    from rich.table import Table

    from tesla_cli.cli.output import console
    from tesla_cli.core.exceptions import BackendNotSupportedError
    from tesla_cli.core.models.charge import ChargingHistory

    backend = _backend()
    try:
        data = backend.get_charge_history()
    except BackendNotSupportedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        console.print(
            "\n[dim]Tip:[/dim] `tesla teslaMate charging` shows charging history "
            "from your local TeslaMate database — no Fleet API required."
        )
        raise typer.Exit(1)

    if is_json_mode():
        import json

        console.print_json(json.dumps(data))
        return

    history = ChargingHistory.from_api(data)

    if not history.points:
        console.print("[yellow]No charging history available.[/yellow]")
        return

    if oneline:
        total_kwh = sum(pt.kwh for pt in history.points)
        console.print(f"⚡ {len(history.points)} sessions | 🔋 {total_kwh:.1f} kWh total")
        return

    t = Table(title=f"Charging History — {history.total_label}", show_lines=False)
    t.add_column("Date", style="cyan")
    t.add_column("kWh", justify="right", style="green")
    t.add_column("Location", style="dim")

    for pt in history.points:
        t.add_row(pt.timestamp, f"{pt.kwh:.1f}", pt.location)

    console.print(t)

    if history.breakdown:
        console.print()
        for label in history.breakdown.values():
            console.print(f"  [dim]{label}[/dim]")


def _fetch_sessions(limit: int = 20) -> tuple[list, str]:
    """Fetch unified charging sessions, merging TeslaMate + Fleet API when both available.

    Strategy:
    - TeslaMate provides: per-session costs, battery levels, precise timestamps
    - Fleet API provides: aggregated history with location labels
    - When both available: TeslaMate is primary, Fleet API fills gaps
    - Dedup by matching date prefix (YYYY-MM-DD) + similar kWh (±20%)

    Returns (sessions, source_name). Shared by `sessions`, `cost-summary`, and API route.
    """
    from tesla_cli.core.models.charge import ChargingHistory, ChargingSession

    cfg = load_config()
    cost_per_kwh = cfg.general.cost_per_kwh
    tm_sessions: list[ChargingSession] = []
    fleet_sessions: list[ChargingSession] = []
    sources: list[str] = []

    # Try TeslaMate
    try:
        if cfg.teslaMate.database_url:
            from tesla_cli.core.backends.teslaMate import TeslaMateBacked

            tm = TeslaMateBacked(cfg.teslaMate.database_url)
            rows = tm.get_charging_sessions(limit=limit)
            tm_sessions = [ChargingSession.from_teslamate(r, cost_per_kwh) for r in rows]
            if tm_sessions:
                sources.append("TeslaMate")
    except Exception:
        pass

    # Try Fleet API
    try:
        backend = _backend()
        raw = backend.get_charge_history()
        history = ChargingHistory.from_api(raw)
        fleet_sessions = [
            ChargingSession.from_fleet_point(pt, cost_per_kwh)
            for pt in history.points[:limit]
        ]
        if fleet_sessions:
            sources.append("Fleet API")
    except Exception:
        pass

    # Merge: TeslaMate is primary, add Fleet API sessions that don't overlap
    if tm_sessions and fleet_sessions:
        tm_dates = {s.date[:10] for s in tm_sessions if len(s.date) >= 10}
        for fs in fleet_sessions:
            # Fleet API dates are shorter ("Mar 15") — skip dedup if can't parse
            if not any(fs.date in d or d in fs.date for d in tm_dates):
                tm_sessions.append(fs)
        sessions = sorted(tm_sessions, key=lambda s: s.date, reverse=True)[:limit]
        source_used = " + ".join(sources)
    elif tm_sessions:
        sessions = tm_sessions
        source_used = "TeslaMate"
    elif fleet_sessions:
        sessions = fleet_sessions
        source_used = "Fleet API"
    else:
        sessions = []
        source_used = ""

    return sessions, source_used


@charge_app.command("sessions")
def charge_sessions(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of sessions"),
    csv_out: str | None = typer.Option(None, "--csv", help="Export to CSV file"),
    vin: str | None = VinOption,  # noqa: ARG001
) -> None:
    """Unified charging sessions from all available sources.

    Prefers TeslaMate (richer data: per-session costs, battery levels).
    Falls back to Fleet API. Applies cost_per_kwh estimation when actual cost is missing.
    """
    import json

    from rich.table import Table

    from tesla_cli.cli.output import console

    sessions, source_used = _fetch_sessions(limit=limit)
    cfg = load_config()

    if not sessions:
        console.print("[yellow]No charging sessions available.[/yellow]")
        console.print(
            "[dim]Tip: Connect TeslaMate (`tesla teslaMate connect`) "
            "or use Fleet API backend for charging data.[/dim]"
        )
        raise typer.Exit(1)

    if csv_out:
        import csv as _csv

        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            rows = [s.model_dump() for s in sessions]
            writer = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        console.print(f"[green]Exported {len(sessions)} sessions to {csv_out}[/green]")
        return

    if is_json_mode():
        console.print_json(json.dumps([s.model_dump() for s in sessions]))
        return

    cost_per_kwh = cfg.general.cost_per_kwh
    t = Table(
        title=f"Charging Sessions ({source_used})",
        caption=f"{len(sessions)} sessions"
        + (f" | cost_per_kwh: ${cost_per_kwh}" if cost_per_kwh else ""),
    )
    t.add_column("#", style="dim", justify="right")
    t.add_column("Date", style="cyan")
    t.add_column("Location", max_width=30)
    t.add_column("kWh", justify="right", style="green")
    t.add_column("Cost", justify="right")
    t.add_column("Battery", justify="center")

    total_kwh = 0.0
    total_cost = 0.0

    for i, s in enumerate(sessions, 1):
        cost_str = "—"
        if s.cost is not None:
            cost_str = f"${s.cost:.2f}"
            if s.cost_estimated:
                cost_str += " ~"
            total_cost += s.cost

        batt_str = "—"
        if s.battery_start is not None and s.battery_end is not None:
            batt_str = f"{s.battery_start}% → {s.battery_end}%"

        total_kwh += s.kwh
        t.add_row(str(i), s.date, s.location, f"{s.kwh:.1f}", cost_str, batt_str)

    console.print(t)

    summary = f"  [bold]{total_kwh:.1f} kWh[/bold] total"
    if total_cost > 0:
        summary += f" | [bold]${total_cost:.2f}[/bold] total cost"
        if any(s.cost_estimated for s in sessions):
            summary += " [dim](~ = estimated)[/dim]"
    console.print(summary)


@charge_app.command("cost-summary")
def charge_cost_summary(
    csv_out: str | None = typer.Option(None, "--csv", help="Export to CSV file"),
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
    vin: str | None = VinOption,  # noqa: ARG001
) -> None:
    """Show charging cost summary across all sources.

    Aggregates from TeslaMate (actual costs) or Fleet API (estimated via cost_per_kwh).
    Shows total kWh, total cost, average cost per kWh, and source breakdown.
    """
    import json

    from rich.table import Table

    from tesla_cli.cli.output import console

    sessions, source_used = _fetch_sessions(limit=500)
    cfg = load_config()
    cost_per_kwh = cfg.general.cost_per_kwh

    if not sessions:
        console.print("[yellow]No charging data available.[/yellow]")
        raise typer.Exit(1)

    total_kwh = sum(s.kwh for s in sessions)
    sessions_with_cost = [s for s in sessions if s.cost is not None]
    total_cost = sum(s.cost for s in sessions_with_cost)
    actual_cost_sessions = [s for s in sessions_with_cost if not s.cost_estimated]
    estimated_sessions = [s for s in sessions_with_cost if s.cost_estimated]
    avg_cost_per_kwh = total_cost / total_kwh if total_kwh > 0 else 0

    if csv_out:
        import csv as _csv

        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            rows = [s.model_dump() for s in sessions]
            writer = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        console.print(f"[green]Exported {len(sessions)} sessions to {csv_out}[/green]")
        return

    if is_json_mode():
        console.print_json(
            json.dumps(
                {
                    "source": source_used,
                    "total_sessions": len(sessions),
                    "total_kwh": round(total_kwh, 1),
                    "total_cost": round(total_cost, 2),
                    "avg_cost_per_kwh": round(avg_cost_per_kwh, 4),
                    "actual_cost_sessions": len(actual_cost_sessions),
                    "estimated_cost_sessions": len(estimated_sessions),
                    "configured_cost_per_kwh": cost_per_kwh,
                }
            )
        )
        return

    if oneline:
        console.print(
            f"💰 ${total_cost:.2f} total | ⚡ {total_kwh:.0f} kWh | 📊 {len(sessions)} sessions"
        )
        return

    t = Table(title=f"Charging Cost Summary ({source_used})", show_header=False, padding=(0, 2))
    t.add_column("key", style="bold")
    t.add_column("value", justify="right")

    t.add_row("Sessions", str(len(sessions)))
    t.add_row("Total energy", f"{total_kwh:.1f} kWh")
    t.add_row("Total cost", f"${total_cost:.2f}")
    t.add_row("Avg cost/kWh", f"${avg_cost_per_kwh:.4f}")

    if actual_cost_sessions:
        t.add_row("Actual cost data", f"{len(actual_cost_sessions)} sessions")
    if estimated_sessions:
        t.add_row(
            "Estimated (via config)",
            f"{len(estimated_sessions)} sessions @ ${cost_per_kwh}/kWh",
        )

    console.print(t)

    if not cost_per_kwh and not actual_cost_sessions:
        console.print(
            "\n  [dim]Tip: Set cost_per_kwh for estimates:[/dim] "
            "`tesla config set cost-per-kwh 0.22`"
        )


@charge_app.command("last")
def charge_last(
    vin: str | None = VinOption,  # noqa: ARG001
) -> None:
    """Show the most recent charging session with cost details.

    tesla charge last
    tesla -j charge last
    """
    import json as _json

    sessions, source = _fetch_sessions(limit=1)

    if not sessions:
        console.print("[yellow]No charging sessions found.[/yellow]")
        raise typer.Exit(1)

    s = sessions[0]

    if is_json_mode():
        console.print_json(_json.dumps(s.model_dump()))
        return

    console.print()
    console.print(f"  [bold]Last Charge[/bold] [dim]({source})[/dim]")
    console.print()
    console.print(f"  [cyan]Date[/cyan]      {s.date}")
    console.print(f"  [cyan]Location[/cyan]  {s.location or '—'}")
    console.print(f"  [cyan]Energy[/cyan]    [bold green]{s.kwh:.1f} kWh[/bold green]")

    if s.cost is not None:
        est = " [dim](estimated)[/dim]" if s.cost_estimated else ""
        console.print(f"  [cyan]Cost[/cyan]      [bold]${s.cost:.2f}[/bold]{est}")

    if s.battery_start is not None and s.battery_end is not None:
        console.print(f"  [cyan]Battery[/cyan]   {s.battery_start}% → {s.battery_end}%")
    console.print()


@charge_app.command("weekly")
def charge_weekly(
    weeks: int = typer.Option(4, "--weeks", "-w", help="Number of weeks to show"),
    vin: str | None = VinOption,  # noqa: ARG001
) -> None:
    """Weekly charging summary — kWh, cost, sessions per week.

    tesla charge weekly
    tesla charge weekly --weeks 8
    tesla -j charge weekly
    """
    import json as _json
    from collections import defaultdict
    from datetime import datetime

    from rich.table import Table

    sessions, source = _fetch_sessions(limit=500)

    if not sessions:
        console.print("[yellow]No charging data available.[/yellow]")
        raise typer.Exit(1)

    weekly: dict[str, dict] = defaultdict(lambda: {"kwh": 0.0, "cost": 0.0, "sessions": 0})
    for s in sessions:
        try:
            dt = datetime.strptime(s.date[:10], "%Y-%m-%d")
            week_key = dt.strftime("%Y-W%V")
            weekly[week_key]["kwh"] += s.kwh
            if s.cost is not None:
                weekly[week_key]["cost"] += s.cost
            weekly[week_key]["sessions"] += 1
        except (ValueError, TypeError):
            continue

    sorted_weeks = sorted(weekly.items(), reverse=True)[:weeks]
    sorted_weeks.reverse()

    if is_json_mode():
        console.print_json(
            _json.dumps(
                {
                    "source": source,
                    "weeks": [
                        {"week": w, "kwh": round(d["kwh"], 1), "cost": round(d["cost"], 2), "sessions": d["sessions"]}
                        for w, d in sorted_weeks
                    ],
                }
            )
        )
        return

    t = Table(title=f"Weekly Charging Summary ({source})")
    t.add_column("Week", style="cyan")
    t.add_column("kWh", justify="right", style="green")
    t.add_column("Cost", justify="right")
    t.add_column("Sessions", justify="right", style="dim")

    total_kwh = 0.0
    total_cost = 0.0
    for w, d in sorted_weeks:
        cost_str = f"${d['cost']:.2f}" if d["cost"] > 0 else "\u2014"
        t.add_row(w, f"{d['kwh']:.1f}", cost_str, str(d["sessions"]))
        total_kwh += d["kwh"]
        total_cost += d["cost"]

    console.print(t)

    avg_kwh = total_kwh / len(sorted_weeks) if sorted_weeks else 0
    console.print(
        f"\n  [bold]{total_kwh:.1f} kWh[/bold] total"
        f" | [bold]{avg_kwh:.1f} kWh/week[/bold] avg"
        + (f" | [bold]${total_cost:.2f}[/bold] total cost" if total_cost > 0 else "")
    )


@charge_app.command("watch-complete")
def charge_watch_complete(
    interval: int = typer.Option(60, "--interval", "-i", help="Poll interval in seconds"),
    vin: str | None = VinOption,
) -> None:
    """Watch for charging to complete and notify when done.

    Polls every INTERVAL seconds. Exits with notification when charging
    reaches the limit or stops.

    tesla charge watch-complete              # poll every 60s
    tesla charge watch-complete -i 30        # poll every 30s
    """
    import time as _time

    v = _vin(vin)
    cfg = load_config()
    backend = get_vehicle_backend(cfg)

    # Setup notifier
    notifier = None
    if cfg.notifications.enabled and cfg.notifications.apprise_urls:
        try:
            import apprise

            notifier = apprise.Apprise()
            for url in cfg.notifications.apprise_urls:
                notifier.add(url)
        except ImportError:
            pass

    console.print(f"  [dim]Watching for charge completion (every {interval}s, Ctrl+C to stop)...[/dim]")

    try:
        while True:
            try:
                data = backend.get_charge_state(v)
            except Exception:
                _time.sleep(interval)
                continue

            state = data.get("charging_state", "Unknown")
            level = data.get("battery_level", 0)
            limit = data.get("charge_limit_soc", 80)

            if state == "Complete" or (state != "Charging" and level >= limit):
                msg = f"Charging complete! Battery at {level}% (limit: {limit}%)"
                console.print(f"\n  [bold green]\u2713 {msg}[/bold green]")

                if notifier:
                    notifier.notify(
                        title="Tesla — Charge Complete",
                        body=msg,
                    )
                    console.print("  [dim]Notification sent.[/dim]")
                return

            eta = data.get("time_to_full_charge", 0)
            eta_str = f"{int(eta)}h{int((eta % 1) * 60):02d}m" if eta else "?"
            console.print(
                f"  [dim]{_time.strftime('%H:%M')}[/dim]  "
                f"\U0001f50b {level}% → {limit}%  |  "
                f"\u26a1 {data.get('charger_power', 0)} kW  |  "
                f"ETA: {eta_str}"
            )
            _time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching.[/dim]")


@charge_app.command("invoices")
def charge_invoices(
    n: int = typer.Option(20, "-n", help="Number of invoices to show"),
    csv_file: str | None = typer.Option(None, "--csv", help="Export to CSV file"),
    vin: str | None = VinOption,
) -> None:
    """Show Supercharging invoices (requires Tessie backend).

    \b
    tesla charge invoices
    tesla charge invoices -n 50
    tesla charge invoices --csv invoices.csv
    tesla -j charge invoices
    """
    import csv as _csv
    import json as _json

    from rich.table import Table

    from tesla_cli.core.backends.tessie import TessieBackend
    from tesla_cli.core.models.charge import ChargingInvoice

    cfg = load_config()
    v = _vin(vin)
    backend = get_vehicle_backend(cfg)

    if not isinstance(backend, TessieBackend):
        console.print("[yellow]charge invoices requires the Tessie backend.[/yellow]")
        console.print("[dim]Configure Tessie: tesla config set tessie-token <token>[/dim]")
        raise typer.Exit(1)

    raw = backend.get_charging_invoices(v)
    invoices: list[ChargingInvoice] = []
    for item in raw[:n]:
        invoices.append(
            ChargingInvoice(
                invoice_id=str(item.get("invoice_id") or item.get("id") or ""),
                date=str(item.get("date") or item.get("billing_date") or ""),
                location=str(item.get("location") or item.get("charger_name") or ""),
                kwh=float(item.get("kwh") or item.get("energy_kwh") or 0.0),
                amount=float(item.get("amount") or item.get("total") or 0.0),
                currency=str(item.get("currency") or "USD"),
                duration_minutes=int(item.get("duration_minutes") or item.get("duration") or 0),
                vin=str(item.get("vin") or v),
            )
        )

    if not invoices:
        console.print("[yellow]No invoices found.[/yellow]")
        return

    if is_json_mode():
        console.print(_json.dumps([inv.model_dump() for inv in invoices], indent=2))
        return

    if csv_file:
        with open(csv_file, "w", newline="", encoding="utf-8") as fh:
            writer = _csv.DictWriter(fh, fieldnames=list(ChargingInvoice.model_fields.keys()))
            writer.writeheader()
            writer.writerows([inv.model_dump() for inv in invoices])
        console.print(f"[green]Exported {len(invoices)} invoices to {csv_file}[/green]")
        return

    t = Table(title=f"Supercharging Invoices ({len(invoices)})")
    t.add_column("Date", style="cyan")
    t.add_column("Location", max_width=35)
    t.add_column("kWh", justify="right", style="green")
    t.add_column("Amount", justify="right")
    t.add_column("Duration", justify="right", style="dim")

    total_kwh = 0.0
    total_amount = 0.0
    for inv in invoices:
        dur_str = f"{inv.duration_minutes}m" if inv.duration_minutes else "—"
        amount_str = f"{inv.amount:.2f} {inv.currency}" if inv.amount else "—"
        t.add_row(inv.date, inv.location, f"{inv.kwh:.2f}", amount_str, dur_str)
        total_kwh += inv.kwh
        total_amount += inv.amount

    console.print(t)
    console.print(
        f"\n  [bold]{total_kwh:.2f} kWh[/bold] total"
        + (
            f" | [bold]{invoices[0].currency} {total_amount:.2f}[/bold] total"
            if total_amount
            else ""
        )
    )
