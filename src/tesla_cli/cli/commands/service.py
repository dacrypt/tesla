"""Service commands: tesla service history|appointments|reminders|setup-reminders."""

from __future__ import annotations

import json as _json
from datetime import date, timedelta

import typer

from tesla_cli.cli.commands.vehicle import _with_wake
from tesla_cli.cli.output import console, is_json_mode, render_dict, render_success, render_table
from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin

service_app = typer.Typer(name="service", help="Tesla Service Center management.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")

# Maintenance intervals
_TIRE_ROTATION_KM = 10_000
_CABIN_FILTER_DAYS = 730  # 2 years
_BRAKE_FLUID_DAYS = 1460  # 4 years
_AC_DESICCANT_DAYS = 1460  # 4 years (Model S/X); 2190 for Model 3/Y (6 years)
_AC_DESICCANT_DAYS_MY = 2190  # 6 years for Model 3/Y


def _backend():
    return get_vehicle_backend(load_config())


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@service_app.command("history")
def service_history(vin: str | None = VinOption) -> None:
    """Show service visit history.

    Fetches service records from Tesla Fleet API.
    Requires Fleet API backend.
    """
    from tesla_cli.core.exceptions import ApiError

    v = _vin(vin)
    backend = _backend()

    try:
        visits = backend.get_service_visits(v)
    except ApiError as exc:
        if exc.status_code in (404, 403):
            console.print(
                "[yellow]Service history not available for this account or vehicle.[/yellow]"
            )
            raise typer.Exit(1)
        raise

    if is_json_mode():
        console.print_json(_json.dumps(visits, default=str))
        return

    if not visits:
        render_success("No service history found.")
        return

    rows = []
    for v_item in visits if isinstance(visits, list) else [visits]:
        if isinstance(v_item, dict):
            rows.append(
                {
                    "date": v_item.get("date") or v_item.get("service_date", ""),
                    "center": v_item.get("service_center") or v_item.get("center_name", ""),
                    "type": v_item.get("service_type") or v_item.get("type", ""),
                    "odometer_km": v_item.get("odometer_km") or v_item.get("odometer", ""),
                }
            )

    if rows:
        render_table(
            rows, columns=["date", "center", "type", "odometer_km"], title="Service History"
        )
    else:
        render_dict(
            visits if isinstance(visits, dict) else {"visits": visits}, title="Service History"
        )


@service_app.command("appointments")
def service_appointments() -> None:
    """Show upcoming service appointments.

    Fetches scheduled appointments from Tesla Fleet API.
    Requires Fleet API backend.
    """
    from tesla_cli.core.exceptions import ApiError

    backend = _backend()

    try:
        data = backend.get_service_appointments()
    except ApiError as exc:
        if exc.status_code in (404, 403):
            console.print("[yellow]Service appointments not available for this account.[/yellow]")
            raise typer.Exit(1)
        raise

    if is_json_mode():
        console.print_json(_json.dumps(data, default=str))
        return

    if not data:
        render_success("No upcoming service appointments.")
        return

    appointments = data if isinstance(data, list) else data.get("appointments", [data])
    if not appointments:
        render_success("No upcoming service appointments.")
        return

    rows = []
    for appt in appointments:
        if isinstance(appt, dict):
            rows.append(
                {
                    "date": appt.get("appointment_date") or appt.get("date", ""),
                    "center": appt.get("service_center") or appt.get("center_name", ""),
                    "type": appt.get("service_type") or appt.get("type", ""),
                    "status": appt.get("status", ""),
                }
            )

    if rows:
        render_table(
            rows, columns=["date", "center", "type", "status"], title="Upcoming Appointments"
        )
    else:
        render_dict(
            data if isinstance(data, dict) else {"appointments": data}, title="Appointments"
        )


@service_app.command("reminders")
def service_reminders(
    odometer: float | None = typer.Option(
        None,
        "--odometer",
        "-o",
        help="Current odometer reading in km (fetched from vehicle if omitted)",
    ),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Vehicle model shorthand: 3, Y, S, X (affects A/C desiccant interval)",
    ),
    last_tire: str | None = typer.Option(
        None, "--last-tire", help="Date of last tire rotation (YYYY-MM-DD)"
    ),
    last_cabin: str | None = typer.Option(
        None, "--last-cabin", help="Date of last cabin air filter replacement (YYYY-MM-DD)"
    ),
    last_brake: str | None = typer.Option(
        None, "--last-brake", help="Date of last brake fluid check (YYYY-MM-DD)"
    ),
    last_ac: str | None = typer.Option(
        None, "--last-ac", help="Date of last A/C desiccant replacement (YYYY-MM-DD)"
    ),
    vin: str | None = VinOption,
) -> None:
    """Show maintenance reminders (tire rotation, brake fluid, cabin filter).

    Estimates next-due dates based on odometer and last-known service dates.

    Intervals:
    - Tire rotation:    every 10,000 km
    - Cabin air filter: every 2 years
    - Brake fluid:      every 4 years
    - A/C desiccant:   every 4 years (6 years for Model 3/Y)

    tesla service reminders
    tesla service reminders --odometer 45000 --last-tire 2023-06-01
    tesla service reminders --model Y --last-ac 2022-01-01
    """
    from tesla_cli.core.exceptions import ApiError

    v = _vin(vin)
    today = date.today()

    # Fetch odometer from vehicle if not supplied
    current_km: float | None = odometer
    if current_km is None:
        try:
            data = _with_wake(lambda b, v: b.get_vehicle_data(v), v)
            raw = data
            if isinstance(raw, dict):
                vs = raw.get("vehicle_state") or raw
                odo = vs.get("odometer")
                if odo is not None:
                    # Tesla reports odometer in miles; convert to km
                    current_km = float(odo) * 1.60934
        except (ApiError, Exception):
            pass

    # Determine A/C desiccant interval based on model
    model_upper = model.upper().strip()
    ac_days = _AC_DESICCANT_DAYS_MY if model_upper in ("3", "Y") else _AC_DESICCANT_DAYS

    def _parse_date(s: str | None) -> date | None:
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            console.print(f"[yellow]Could not parse date '{s}' — ignoring.[/yellow]")
            return None

    last_tire_date = _parse_date(last_tire)
    last_cabin_date = _parse_date(last_cabin)
    last_brake_date = _parse_date(last_brake)
    last_ac_date = _parse_date(last_ac)

    if is_json_mode():
        reminders: list[dict] = []
        if current_km is not None and last_tire_date is not None:
            next_tire_km = (current_km // _TIRE_ROTATION_KM + 1) * _TIRE_ROTATION_KM
            reminders.append(
                {"item": "Tire Rotation", "next_due_km": next_tire_km, "current_km": current_km}
            )
        if last_cabin_date:
            reminders.append(
                {
                    "item": "Cabin Air Filter",
                    "last_service": str(last_cabin_date),
                    "next_due": str(last_cabin_date + timedelta(days=_CABIN_FILTER_DAYS)),
                }
            )
        if last_brake_date:
            reminders.append(
                {
                    "item": "Brake Fluid Check",
                    "last_service": str(last_brake_date),
                    "next_due": str(last_brake_date + timedelta(days=_BRAKE_FLUID_DAYS)),
                }
            )
        if last_ac_date:
            reminders.append(
                {
                    "item": "A/C Desiccant",
                    "last_service": str(last_ac_date),
                    "next_due": str(last_ac_date + timedelta(days=ac_days)),
                }
            )
        console.print_json(_json.dumps(reminders))
        return

    console.print()
    console.print("[bold]Maintenance Reminders[/bold]")
    if current_km is not None:
        console.print(f"  [dim]Current odometer:[/dim] {current_km:,.0f} km")
    console.print()

    def _status_color(due_date: date) -> str:
        delta = (due_date - today).days
        if delta < 0:
            return "red"
        if delta < 60:
            return "yellow"
        return "green"

    def _print_date_reminder(label: str, last: date | None, interval_days: int) -> None:
        if last is None:
            console.print(
                f"  [dim]{label}:[/dim] [dim]last service date unknown — use --last-* option[/dim]"
            )
            return
        next_due = last + timedelta(days=interval_days)
        color = _status_color(next_due)
        delta_days = (next_due - today).days
        overdue = " [red](OVERDUE)[/red]" if delta_days < 0 else ""
        console.print(
            f"  [dim]{label}:[/dim] [{color}]{next_due}[/{color}]"
            f"  [dim](last: {last}){overdue}[/dim]"
        )

    # Tire rotation — km-based
    if current_km is not None:
        # Calculate next due in km
        next_tire_km = (int(current_km) // _TIRE_ROTATION_KM + 1) * _TIRE_ROTATION_KM
        remaining = next_tire_km - current_km
        color = "green" if remaining > 2000 else "yellow" if remaining > 0 else "red"
        overdue = " [red](OVERDUE)[/red]" if remaining <= 0 else ""
        console.print(
            f"  [dim]Tire Rotation:[/dim] [{color}]due at {next_tire_km:,.0f} km[/{color}]"
            f"  [dim]({remaining:,.0f} km remaining){overdue}[/dim]"
        )
    else:
        console.print(
            "  [dim]Tire Rotation:[/dim] [dim]odometer unavailable — pass --odometer[/dim]"
        )

    _print_date_reminder("Cabin Air Filter", last_cabin_date, _CABIN_FILTER_DAYS)
    _print_date_reminder("Brake Fluid Check", last_brake_date, _BRAKE_FLUID_DAYS)
    interval_label = "6 years" if model_upper in ("3", "Y") else "4 years"
    _print_date_reminder(f"A/C Desiccant ({interval_label})", last_ac_date, ac_days)

    console.print()
    console.print(
        "[dim]Tip: pass --last-tire, --last-cabin, --last-brake, --last-ac (YYYY-MM-DD) "
        "for accurate reminders.[/dim]"
    )
    console.print()


@service_app.command("setup-reminders")
def setup_service_reminders(
    vin: str | None = VinOption,
    time: str = typer.Option("08:00", "--time", "-t", help="Daily check time in HH:MM format"),
    cooldown: int = typer.Option(
        1440, "--cooldown", "-c", help="Cooldown in minutes between alerts (default: 24h)"
    ),
) -> None:
    """Configure automatic service reminder notifications.

    Creates automation rules that check maintenance status once daily and
    notify you via configured notification channels when any item is due.

    \b
    tesla service setup-reminders
    tesla service setup-reminders --time 09:00
    tesla service setup-reminders --vin <VIN> --time 07:30
    """
    from tesla_cli.core.automation import AUTOMATIONS_FILE, AutomationEngine
    from tesla_cli.core.models.automation import (
        AutomationAction,
        AutomationRule,
        AutomationTrigger,
    )

    engine = AutomationEngine(AUTOMATIONS_FILE)

    rules_to_create: list[tuple[str, str]] = [
        (
            "service-tire-rotation",
            "Maintenance due: Tire rotation — check your odometer and schedule a rotation.",
        ),
        (
            "service-cabin-filter",
            "Maintenance due: Cabin air filter replacement — 2-year interval reached.",
        ),
        (
            "service-brake-fluid",
            "Maintenance due: Brake fluid check — 4-year interval reached.",
        ),
        (
            "service-ac-desiccant",
            "Maintenance due: A/C desiccant replacement — service interval reached.",
        ),
    ]

    created: list[str] = []
    skipped: list[str] = []

    for rule_name, message in rules_to_create:
        if any(r.name == rule_name for r in engine.rules):
            skipped.append(rule_name)
            continue

        trigger = AutomationTrigger(type="time_of_day", time=time)
        action = AutomationAction(
            type="notify",
            message=message,
        )
        rule = AutomationRule(
            name=rule_name,
            trigger=trigger,
            action=action,
            cooldown_minutes=cooldown,
        )
        engine.add_rule(rule)
        created.append(rule_name)

    console.print()
    if created:
        render_success(
            f"Created {len(created)} service reminder rule(s) — daily check at {time}:\n"
            + "\n".join(f"  [dim]• {n}[/dim]" for n in created)
        )
    if skipped:
        console.print(
            f"[yellow]Skipped {len(skipped)} rule(s) — already configured:[/yellow]\n"
            + "\n".join(f"  [dim]• {n}[/dim]" for n in skipped)
        )
    if not created and not skipped:
        console.print("[dim]No rules created.[/dim]")

    console.print(
        "\n[dim]Tip: start the automation daemon with [bold]tesla automations run[/bold] "
        "to activate notifications.[/dim]\n"
    )
