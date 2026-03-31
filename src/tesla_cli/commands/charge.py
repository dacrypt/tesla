"""Charge commands: tesla charge status|start|stop|limit|amps|port-open|port-close|schedule|history."""

from __future__ import annotations

import typer

from tesla_cli.backends import get_vehicle_backend
from tesla_cli.commands.vehicle import _with_wake
from tesla_cli.config import load_config, resolve_vin
from tesla_cli.models.charge import ChargeState
from tesla_cli.output import (
    console,
    is_json_mode,
    render_dict,
    render_model,
    render_success,
    render_table,
)

charge_app = typer.Typer(name="charge", help="Battery and charging management.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _backend():
    return get_vehicle_backend(load_config())


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@charge_app.command("status")
def charge_status(vin: str | None = VinOption) -> None:
    """Show current charge state."""
    from tesla_cli.output import console
    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_charge_state(v), v)
    state = ChargeState.model_validate(data)
    render_model(state, title="Charge State")

    cfg = load_config()
    cost_per_kwh = cfg.general.cost_per_kwh
    energy_added = data.get("charge_energy_added")
    if cost_per_kwh and cost_per_kwh > 0 and energy_added:
        estimated_cost = float(energy_added) * float(cost_per_kwh)
        console.print(
            f"  [dim]Estimated session cost:[/dim] [bold]${estimated_cost:.2f}[/bold] "
            f"[dim]({energy_added} kWh \xd7 ${cost_per_kwh:.4f}/kWh)[/dim]"
        )


@charge_app.command("start")
def charge_start(vin: str | None = VinOption) -> None:
    """Start charging."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "charge_start"), v)
    render_success("Charging started")


@charge_app.command("stop")
def charge_stop(vin: str | None = VinOption) -> None:
    """Stop charging."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "charge_stop"), v)
    render_success("Charging stopped")


@charge_app.command("limit")
def charge_limit(
    percent: int | None = typer.Argument(None, help="Charge limit percentage (50-100). Omit to show current."),
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
    _with_wake(
        lambda b, v: b.command(v, "set_scheduled_charging", enable=enable, time=time), v
    )
    status = "enabled" if enable else "disabled"
    render_success(f"Scheduled charging {status}")


@charge_app.command("departure")
def charge_departure(
    time: str = typer.Argument(..., help="Departure time (HH:MM, 24h)"),
    precondition: bool = typer.Option(False, "--precondition/--no-precondition", help="Enable cabin preconditioning"),
    off_peak: bool = typer.Option(False, "--off-peak/--no-off-peak", help="Enable off-peak charging window"),
    off_peak_end: str = typer.Option("07:00", "--off-peak-end", help="Off-peak charging end time (HH:MM)"),
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
            from tesla_cli.output import console
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
        from tesla_cli.output import console
        console.print(_json.dumps({
            "scheduled_departure": True,
            "time": time,
            "time_minutes": dep_minutes,
            "precondition": precondition,
            "off_peak": off_peak,
        }, indent=2))
        return

    msg = f"Scheduled departure set to {time}"
    if precondition:
        msg += " with preconditioning"
    if off_peak:
        msg += f" (off-peak until {off_peak_end})"
    render_success(msg)


@charge_app.command("schedule-preview")
def charge_schedule_preview(vin: str | None = VinOption) -> None:
    """Show current scheduled charge and departure settings in one consolidated view.

    tesla charge schedule-preview
    """
    import json as _json

    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_charge_state(v), v)

    # Extract scheduling fields
    sched_mode  = data.get("scheduled_charging_mode", "Off")
    sched_start = data.get("scheduled_charging_start_time_app")  # minutes after midnight
    sched_start_utc = data.get("scheduled_charging_start_time")
    dep_mode    = data.get("scheduled_departure_time_minutes")    # minutes after midnight
    dep_time    = data.get("scheduled_departure_time")            # epoch
    precond     = data.get("preconditioning_enabled", False)
    precond_wkd = data.get("preconditioning_weekdays_only", False)
    off_peak    = data.get("off_peak_charging_enabled", False)
    off_peak_end = data.get("off_peak_hours_end_time")            # minutes after midnight

    def _minutes_to_hhmm(mins: int | None) -> str:
        if mins is None:
            return "—"
        return f"{int(mins) // 60:02d}:{int(mins) % 60:02d}"

    if is_json_mode():
        from tesla_cli.output import console as _con
        _con.print(_json.dumps({
            "scheduled_charging_mode": sched_mode,
            "scheduled_charging_start": _minutes_to_hhmm(sched_start),
            "scheduled_charging_start_utc": sched_start_utc,
            "scheduled_departure_time": _minutes_to_hhmm(dep_mode),
            "scheduled_departure_epoch": dep_time,
            "preconditioning_enabled": precond,
            "preconditioning_weekdays_only": precond_wkd,
            "off_peak_charging_enabled": off_peak,
            "off_peak_hours_end_time": _minutes_to_hhmm(off_peak_end),
        }, indent=2))
        return

    from rich.panel import Panel
    from rich.table import Table

    from tesla_cli.output import console as _con

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
    limit: int | None = typer.Option(None, "--limit", "-l", min=50, max=100, help="Charge limit percent (50–100)"),
    amps:  int | None = typer.Option(None, "--amps",  "-a", min=1,  max=48,  help="Charge current amps (1–48)"),
    schedule: str | None = typer.Option(None, "--schedule", "-s", help="Scheduled charge ON time HH:MM (empty string to disable)"),
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

    from tesla_cli.exceptions import VehicleAsleepError

    cfg = load_config()
    v   = resolve_vin(cfg, vin)
    b   = get_vehicle_backend(cfg)

    # ── No args → show current profile ──────────────────────────────────────
    if limit is None and amps is None and schedule is None:
        try:
            cs = b.get_charge_state(v)
        except VehicleAsleepError:
            console.print("[yellow]Vehicle is asleep. Wake it first.[/yellow]")
            raise typer.Exit(1)

        if is_json_mode():
            console.print(_json.dumps({
                "charge_limit_soc":           cs.get("charge_limit_soc"),
                "charge_amps":                cs.get("charge_amps"),
                "scheduled_charging_pending": cs.get("scheduled_charging_pending"),
                "scheduled_charging_start_time": str(cs.get("scheduled_charging_start_time") or ""),
            }))
            return

        from rich.table import Table
        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_column("k", style="dim", width=26)
        t.add_column("v")
        t.add_row("Charge limit",      f"{cs.get('charge_limit_soc', '?')}%")
        t.add_row("Charge amps",       f"{cs.get('charge_amps', '?')} A")
        t.add_row("Scheduled pending", str(cs.get("scheduled_charging_pending", "?")))
        t.add_row("Scheduled time",    str(cs.get("scheduled_charging_start_time") or "—"))
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
        if limit is not None:  parts.append(f"limit=[bold]{limit}%[/bold]")
        if amps  is not None:  parts.append(f"amps=[bold]{amps}A[/bold]")
        if schedule is not None:
            parts.append(f"schedule=[bold]{'off' if schedule == '' else schedule}[/bold]")
        render_success("Charge profile updated: " + "  ".join(parts))
    else:
        console.print(f"[red]Some updates failed:[/red] {results}")
        raise typer.Exit(1)


@charge_app.command("schedule-amps")
def charge_schedule_amps(
    schedule_time: str = typer.Argument(..., metavar="HH:MM", help="Scheduled charge start time (24-hour)"),
    amps: int         = typer.Argument(..., help="Charge current in amps (1–48)"),
    vin: str | None   = VinOption,
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


@charge_app.command("history")
def charge_history(vin: str | None = VinOption) -> None:  # noqa: ARG001
    """Show charging history (Fleet API) or redirect to TeslaMate."""
    from tesla_cli.exceptions import BackendNotSupportedError
    from tesla_cli.output import console

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

    if isinstance(data, list):
        render_table(
            data,
            columns=["date", "location", "kwh", "cost", "duration"],
            title="Charging History",
        )
    else:
        render_dict(data, title="Charging History")
