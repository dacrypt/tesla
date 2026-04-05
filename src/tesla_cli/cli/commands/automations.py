"""Automation engine commands: tesla automations list/add/remove/enable/disable/run/test."""

from __future__ import annotations

import time

import typer

from tesla_cli.cli.output import console, is_json_mode, render_success, render_warning
from tesla_cli.core.automation import AUTOMATIONS_FILE, AutomationEngine
from tesla_cli.core.models.automation import (
    AutomationAction,
    AutomationRule,
    AutomationTrigger,
)

automations_app = typer.Typer(
    name="automations",
    help="Config-driven automation rules: watch vehicle state and fire actions.",
)

# ── Helpers ────────────────────────────────────────────────────────────────────

TRIGGER_TYPES = [
    "battery_below",
    "battery_above",
    "charging_complete",
    "charging_started",
    "sentry_event",
    "location_enter",
    "location_exit",
    "state_change",
    "time_of_day",
]

ACTION_TYPES = ["notify", "command"]


def _engine() -> AutomationEngine:
    return AutomationEngine(AUTOMATIONS_FILE)


def _status_icon(enabled: bool) -> str:
    return "[green]●[/green]" if enabled else "[dim]○[/dim]"


def _cooldown_str(rule: AutomationRule) -> str:
    if rule.last_fired is None:
        return "[dim]never[/dim]"
    from datetime import UTC, datetime

    elapsed = (datetime.now(tz=UTC) - rule.last_fired).total_seconds() / 60
    return f"{int(elapsed)}m ago"


# ── Commands ───────────────────────────────────────────────────────────────────


@automations_app.command("list")
def automations_list() -> None:
    """List all automation rules with their status.

    tesla automations list
    tesla -j automations list
    """
    import json

    engine = _engine()
    rules = engine.rules

    if is_json_mode():
        console.print_json(
            json.dumps([r.model_dump(mode="json") for r in rules], indent=2)
        )
        return

    if not rules:
        console.print("\n  [dim]No automation rules configured.[/dim]")
        console.print("  Add one with: [bold]tesla automations add[/bold]\n")
        return

    from rich.table import Table

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("", width=2)
    table.add_column("Name")
    table.add_column("Trigger")
    table.add_column("Action")
    table.add_column("Last fired", width=12)
    table.add_column("Cooldown", width=10)

    for rule in rules:
        t = rule.trigger
        trigger_desc = t.type
        if t.threshold is not None:
            trigger_desc += f" {t.threshold}"
        if t.time:
            trigger_desc += f" @ {t.time}"
        if t.latitude is not None:
            trigger_desc += f" ({t.latitude:.3f},{t.longitude:.3f})"

        action_desc = rule.action.type
        if rule.action.message:
            msg = rule.action.message[:40]
            action_desc += f": {msg}{'…' if len(rule.action.message) > 40 else ''}"
        elif rule.action.command:
            cmd = rule.action.command[:40]
            action_desc += f": {cmd}{'…' if len(rule.action.command) > 40 else ''}"

        table.add_row(
            _status_icon(rule.enabled),
            rule.name,
            trigger_desc,
            action_desc,
            _cooldown_str(rule),
            f"{rule.cooldown_minutes}m",
        )

    console.print()
    console.print(table)
    console.print(
        f"\n  [dim]{len(rules)} rule(s) · "
        f"{sum(1 for r in rules if r.enabled)} enabled[/dim]\n"
    )


@automations_app.command("add")
def automations_add(
    name: str = typer.Option("", "--name", "-n", help="Rule name"),
    trigger_type: str = typer.Option("", "--trigger", "-t", help="Trigger type"),
    action_type: str = typer.Option("", "--action", "-a", help="Action type (notify/command)"),
    cooldown: int = typer.Option(30, "--cooldown", "-c", help="Cooldown in minutes"),
) -> None:
    """Interactively add a new automation rule.

    tesla automations add
    tesla automations add --name "Low battery" --trigger battery_below --action notify
    """
    engine = _engine()

    # Interactive prompts for missing values
    if not name:
        name = typer.prompt("Rule name")

    if not trigger_type:
        console.print(f"  Trigger types: {', '.join(TRIGGER_TYPES)}")
        trigger_type = typer.prompt("Trigger type")

    if trigger_type not in TRIGGER_TYPES:
        console.print(f"[red]Unknown trigger type '{trigger_type}'.[/red]")
        console.print(f"  Valid types: {', '.join(TRIGGER_TYPES)}")
        raise typer.Exit(1)

    # Build trigger
    trigger_kwargs: dict = {"type": trigger_type}

    if trigger_type in ("battery_below", "battery_above"):
        threshold = typer.prompt("Threshold (%)", default="20")
        trigger_kwargs["threshold"] = float(threshold)

    elif trigger_type in ("location_enter", "location_exit"):
        trigger_kwargs["latitude"] = float(typer.prompt("Latitude"))
        trigger_kwargs["longitude"] = float(typer.prompt("Longitude"))
        trigger_kwargs["radius_km"] = float(typer.prompt("Radius (km)", default="0.5"))

    elif trigger_type == "state_change":
        trigger_kwargs["field"] = typer.prompt("Field (e.g. charge_state.charging_state)")
        from_val = typer.prompt("From value (leave blank for any)", default="")
        to_val = typer.prompt("To value (leave blank for any)", default="")
        if from_val:
            trigger_kwargs["from_value"] = from_val
        if to_val:
            trigger_kwargs["to_value"] = to_val

    elif trigger_type == "time_of_day":
        trigger_kwargs["time"] = typer.prompt("Time (HH:MM)")

    trigger = AutomationTrigger(**trigger_kwargs)

    # Build action
    if not action_type:
        console.print(f"  Action types: {', '.join(ACTION_TYPES)}")
        action_type = typer.prompt("Action type", default="notify")

    if action_type not in ("notify", "command", "exec"):
        console.print(f"[red]Unknown action type '{action_type}'.[/red]")
        raise typer.Exit(1)

    action_kwargs: dict = {"type": action_type}
    if action_type == "notify":
        action_kwargs["message"] = typer.prompt(
            "Message (use {battery_level}, {range}, {ts} etc.)",
            default="Tesla alert: {ts}",
        )
    else:
        action_kwargs["command"] = typer.prompt("Shell command to execute")

    action = AutomationAction(**action_kwargs)

    rule = AutomationRule(
        name=name,
        trigger=trigger,
        action=action,
        cooldown_minutes=cooldown,
    )

    # Check for name collision
    if any(r.name == name for r in engine.rules):
        console.print(f"[yellow]Rule '{name}' already exists. Remove it first.[/yellow]")
        raise typer.Exit(1)

    engine.add_rule(rule)
    render_success(f"Automation rule '{name}' added.")


@automations_app.command("remove")
def automations_remove(
    name: str = typer.Argument(..., help="Rule name to remove"),
) -> None:
    """Remove an automation rule by name.

    tesla automations remove "Low battery alert"
    """
    engine = _engine()
    if engine.remove_rule(name):
        render_success(f"Rule '{name}' removed.")
    else:
        console.print(f"[red]Rule '{name}' not found.[/red]")
        raise typer.Exit(1)


@automations_app.command("enable")
def automations_enable(
    name: str = typer.Argument(..., help="Rule name to enable"),
) -> None:
    """Enable an automation rule.

    tesla automations enable "Low battery alert"
    """
    engine = _engine()
    if engine.set_enabled(name, True):
        render_success(f"Rule '{name}' enabled.")
    else:
        console.print(f"[red]Rule '{name}' not found.[/red]")
        raise typer.Exit(1)


@automations_app.command("disable")
def automations_disable(
    name: str = typer.Argument(..., help="Rule name to disable"),
) -> None:
    """Disable an automation rule.

    tesla automations disable "Low battery alert"
    """
    engine = _engine()
    if engine.set_enabled(name, False):
        render_success(f"Rule '{name}' disabled.")
    else:
        console.print(f"[red]Rule '{name}' not found.[/red]")
        raise typer.Exit(1)


@automations_app.command("run")
def automations_run(
    interval: int = typer.Option(60, "--interval", "-i", help="Poll interval in seconds"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log but don't execute actions"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
) -> None:
    """Start the automation daemon (polls vehicle, evaluates rules).

    tesla automations run
    tesla automations run --interval 30
    tesla automations run --dry-run
    """
    from datetime import datetime as _dt

    from tesla_cli.core.backends import get_vehicle_backend
    from tesla_cli.core.config import load_config, resolve_vin

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    backend = get_vehicle_backend(cfg)
    engine = _engine()

    if not engine.rules:
        console.print("[yellow]No automation rules configured.[/yellow]")
        console.print("Add one with: [bold]tesla automations add[/bold]")
        raise typer.Exit(1)

    enabled_count = sum(1 for r in engine.rules if r.enabled)
    mode = "[yellow](dry-run)[/yellow]" if dry_run else ""
    console.print(
        f"\n  [bold]Automation engine[/bold] {mode} [dim]{v}[/dim]\n"
        f"  [dim]{enabled_count} enabled rule(s) · polling every {interval}s[/dim]\n"
        "  [dim]Press Ctrl+C to stop.[/dim]\n"
    )

    try:
        while True:
            ts = _dt.now().strftime("%H:%M:%S")
            try:
                data = backend.get_vehicle_data(v)
                fired = engine.evaluate(data, dry_run=dry_run)

                if fired:
                    for rule, msg in fired:
                        prefix = "[yellow]DRY-RUN[/yellow] " if dry_run else "[green]FIRED[/green] "
                        console.print(
                            f"  [dim]{ts}[/dim]  {prefix}[bold]{rule.name}[/bold]: {msg}"
                        )
                else:
                    console.print(f"  [dim]{ts}[/dim]  [dim]No triggers fired.[/dim]")

            except Exception as exc:  # noqa: BLE001
                console.print(f"  [dim]{ts}[/dim]  [red]Error:[/red] {exc}")

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n  [dim]Automation engine stopped.[/dim]\n")


@automations_app.command("test")
def automations_test(
    name: str = typer.Argument(..., help="Rule name to dry-run"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
) -> None:
    """Dry-run a single rule against current vehicle state.

    tesla automations test "Low battery alert"
    """
    from tesla_cli.core.backends import get_vehicle_backend
    from tesla_cli.core.config import load_config, resolve_vin

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    backend = get_vehicle_backend(cfg)
    engine = _engine()

    rule = next((r for r in engine.rules if r.name == name), None)
    if rule is None:
        console.print(f"[red]Rule '{name}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n  Fetching vehicle data for [bold]{v}[/bold]...")
    try:
        data = backend.get_vehicle_data(v)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to fetch vehicle data:[/red] {exc}")
        raise typer.Exit(1)

    # Evaluate only the target rule (bypass cooldown by temporarily zeroing last_fired)
    saved_last_fired = rule.last_fired
    saved_cooldown = rule.cooldown_minutes
    rule.last_fired = None
    rule.cooldown_minutes = 0

    fired = engine.evaluate(data, dry_run=True)

    rule.last_fired = saved_last_fired
    rule.cooldown_minutes = saved_cooldown

    matched = [(r, msg) for r, msg in fired if r.name == name]

    console.print()
    if matched:
        _, msg = matched[0]
        console.print(f"  [green]WOULD FIRE[/green]  [bold]{name}[/bold]")
        console.print(f"  Action: {rule.action.type}")
        if msg:
            console.print(f"  Message: {msg}")
    else:
        render_warning(f"Rule '{name}' would NOT fire (trigger conditions not met).")

    console.print(
        f"\n  Trigger: [bold]{rule.trigger.type}[/bold]  "
        f"Action: [bold]{rule.action.type}[/bold]\n"
    )
