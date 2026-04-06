"""Automation engine commands: tesla automations list/add/remove/enable/disable/run/test."""

from __future__ import annotations

import time
from pathlib import Path

import typer

from tesla_cli.cli.output import console, is_json_mode, render_success, render_warning
from tesla_cli.core.automation import AUTOMATIONS_FILE, AutomationEngine
from tesla_cli.core.models.automation import (
    AutomationAction,
    AutomationCondition,
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


def _parse_trigger_params(trigger_type: str) -> dict:
    """Prompt for trigger-specific parameters and return kwargs dict."""
    kwargs: dict = {"type": trigger_type}

    if trigger_type in ("battery_below", "battery_above"):
        threshold = typer.prompt("Threshold (%)", default="20")
        kwargs["threshold"] = float(threshold)

    elif trigger_type in ("location_enter", "location_exit"):
        kwargs["latitude"] = float(typer.prompt("Latitude"))
        kwargs["longitude"] = float(typer.prompt("Longitude"))
        kwargs["radius_km"] = float(typer.prompt("Radius (km)", default="0.5"))

    elif trigger_type == "state_change":
        kwargs["field"] = typer.prompt("Field (e.g. charge_state.charging_state)")
        from_val = typer.prompt("From value (leave blank for any)", default="")
        to_val = typer.prompt("To value (leave blank for any)", default="")
        if from_val:
            kwargs["from_value"] = from_val
        if to_val:
            kwargs["to_value"] = to_val

    elif trigger_type == "time_of_day":
        kwargs["time"] = typer.prompt("Time (HH:MM)")

    return kwargs


def _parse_conditions(condition: list[str]) -> list[AutomationCondition]:
    """Parse condition strings in 'field:op:value' format into AutomationCondition list."""
    parsed: list[AutomationCondition] = []
    for cond_str in condition:
        parts = cond_str.split(":", 2)
        if len(parts) != 3:  # noqa: PLR2004
            console.print(f"[red]Invalid condition format '{cond_str}'. Use field:op:value.[/red]")
            raise typer.Exit(1)
        parsed.append(AutomationCondition(field=parts[0], operator=parts[1], value=parts[2]))
    return parsed


def _cooldown_str(rule: AutomationRule) -> str:
    if rule.last_fired is None:
        return "[dim]never[/dim]"
    from datetime import UTC, datetime

    elapsed = (datetime.now(tz=UTC) - rule.last_fired).total_seconds() / 60
    return f"{int(elapsed)}m ago"


# ── Commands ───────────────────────────────────────────────────────────────────


@automations_app.command("list")
def automations_list(
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
) -> None:
    """List all automation rules with their status.

    tesla automations list
    tesla -j automations list
    """
    import json

    engine = _engine()
    rules = engine.rules

    if is_json_mode():
        console.print_json(json.dumps([r.model_dump(mode="json") for r in rules], indent=2))
        return

    if not rules:
        console.print("\n  [dim]No automation rules configured.[/dim]")
        console.print("  Add one with: [bold]tesla automations add[/bold]\n")
        return

    if oneline:
        enabled = sum(1 for r in rules if r.enabled)
        disabled = len(rules) - enabled
        last = next(
            (
                r.name
                for r in sorted(
                    rules,
                    key=lambda r: (
                        r.last_fired
                        or __import__("datetime").datetime.min.replace(
                            tzinfo=__import__("datetime").timezone.utc
                        )
                    ),
                    reverse=True,
                )
                if r.last_fired
            ),
            "none",
        )
        console.print(
            f"📋 {len(rules)} rules | ✅ {enabled} enabled | ⏸ {disabled} disabled | 🔥 last: {last}"
        )
        return

    from rich.table import Table

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("", width=2)
    table.add_column("Name")
    table.add_column("Trigger")
    table.add_column("Action")
    table.add_column("Cond", width=5)
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

        cond_count = str(len(rule.conditions)) if rule.conditions else "[dim]—[/dim]"

        table.add_row(
            _status_icon(rule.enabled),
            rule.name,
            trigger_desc,
            action_desc,
            cond_count,
            _cooldown_str(rule),
            f"{rule.cooldown_minutes}m",
        )

    console.print()
    console.print(table)
    console.print(
        f"\n  [dim]{len(rules)} rule(s) · {sum(1 for r in rules if r.enabled)} enabled[/dim]\n"
    )


@automations_app.command("add")
def automations_add(
    name: str = typer.Option("", "--name", "-n", help="Rule name"),
    trigger_type: str = typer.Option("", "--trigger", "-t", help="Trigger type"),
    action_type: str = typer.Option("", "--action", "-a", help="Action type (notify/command)"),
    cooldown: int = typer.Option(30, "--cooldown", help="Cooldown in minutes"),
    condition: list[str] = typer.Option(  # noqa: B008
        [],
        "--condition",
        "-c",
        help="Condition: field:op:value (e.g. charge_state.battery_level:lt:90)",
    ),
    delay: int = typer.Option(0, "--delay", help="Delay in seconds before action"),
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

    trigger = AutomationTrigger(**_parse_trigger_params(trigger_type))

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

    parsed_conditions = _parse_conditions(condition)

    rule = AutomationRule(
        name=name,
        trigger=trigger,
        action=action,
        conditions=parsed_conditions,
        cooldown_minutes=cooldown,
        delay_seconds=delay,
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
    source: str = typer.Option(
        "auto",
        "--source",
        help="Data source: auto (try MQTT first, fall back to poll), poll, mqtt",
    ),
) -> None:
    """Start the automation daemon (polls vehicle, evaluates rules).

    \b
    tesla automations run
    tesla automations run --interval 30
    tesla automations run --dry-run
    tesla automations run --source mqtt
    tesla automations run --source poll
    """
    from datetime import datetime as _dt

    from tesla_cli.core.backends import get_vehicle_backend
    from tesla_cli.core.config import load_config, resolve_vin

    if source not in ("auto", "poll", "mqtt"):
        console.print(f"[red]Unknown source '{source}'. Use: auto, poll, mqtt[/red]")
        raise typer.Exit(1)

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    engine = _engine()

    if not engine.rules:
        console.print("[yellow]No automation rules configured.[/yellow]")
        console.print("Add one with: [bold]tesla automations add[/bold]")
        raise typer.Exit(1)

    enabled_count = sum(1 for r in engine.rules if r.enabled)
    mode = "[yellow](dry-run)[/yellow]" if dry_run else ""

    # ── MQTT mode ──────────────────────────────────────────────────────────────
    use_mqtt = source in ("mqtt", "auto")
    if use_mqtt:
        broker = cfg.mqtt.broker or "localhost"
        mqtt_port = cfg.mqtt.port
        topic_prefix = (cfg.mqtt.topic_prefix or "tesla").rstrip("/")
        topic = f"{topic_prefix}/telemetry/{{vin}}"

        def _on_fired(rule, msg):  # noqa: ANN001
            ts = _dt.now().strftime("%H:%M:%S")
            prefix = "[yellow]DRY-RUN[/yellow] " if dry_run else "[green]FIRED[/green] "
            console.print(f"  [dim]{ts}[/dim]  {prefix}[bold]{rule.name}[/bold]: {msg}")

        console.print(
            f"\n  [bold]Automation engine[/bold] {mode} [dim]{v}[/dim]\n"
            f"  [dim]{enabled_count} enabled rule(s) · source=mqtt "
            f"broker={broker}:{mqtt_port}[/dim]\n"
            "  [dim]Press Ctrl+C to stop.[/dim]\n"
        )
        try:
            engine.run_mqtt(
                broker=broker,
                port=mqtt_port,
                topic=topic,
                vin=v,
                dry_run=dry_run,
                on_fired=_on_fired,
            )
            return
        except ImportError:
            if source == "mqtt":
                console.print(
                    "[red]paho-mqtt not installed.[/red]\n"
                    "Install with: [bold]pip install 'tesla-cli[mqtt]'[/bold]"
                )
                raise typer.Exit(1)
            # source == "auto": fall through to polling
            render_warning("paho-mqtt not installed — falling back to poll mode.")
        except KeyboardInterrupt:
            console.print("\n  [dim]Automation engine stopped.[/dim]\n")
            return

    # ── Poll mode ──────────────────────────────────────────────────────────────
    backend = get_vehicle_backend(cfg)

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
                        console.print(f"  [dim]{ts}[/dim]  {prefix}[bold]{rule.name}[/bold]: {msg}")
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
        f"\n  Trigger: [bold]{rule.trigger.type}[/bold]  Action: [bold]{rule.action.type}[/bold]\n"
    )


# ── Daemon management ──────────────────────────────────────────────────────────

_LAUNCHD_LABEL = "com.tesla-cli.automations"
_LAUNCHD_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCHD_LABEL}.plist"
_SYSTEMD_UNIT = Path.home() / ".config" / "systemd" / "user" / "tesla-automations.service"


def _service_installed() -> bool:
    """True if the background service unit/plist exists on disk."""
    import sys

    if sys.platform == "darwin":
        return _LAUNCHD_PLIST.exists()
    return _SYSTEMD_UNIT.exists()


def _service_running() -> bool:
    """True if the background service is currently active."""
    import subprocess
    import sys

    try:
        if sys.platform == "darwin":
            r = subprocess.run(
                ["launchctl", "list", _LAUNCHD_LABEL],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return r.returncode == 0
        else:
            r = subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", "tesla-automations"],
                capture_output=True,
                timeout=5,
            )
            return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _service_pid() -> int | None:
    """Return the PID of the running service, or None."""
    import subprocess
    import sys

    try:
        if sys.platform == "darwin":
            r = subprocess.run(
                ["launchctl", "list", _LAUNCHD_LABEL],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith('"PID"') or line.startswith("PID"):
                    parts = line.split()
                    for part in parts:
                        part = part.strip('",;')
                        if part.isdigit():
                            return int(part)
        else:
            r = subprocess.run(
                ["systemctl", "--user", "show", "-p", "MainPID", "tesla-automations"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in r.stdout.splitlines():
                if line.startswith("MainPID="):
                    pid = line.split("=", 1)[1].strip()
                    if pid.isdigit() and int(pid) > 0:
                        return int(pid)
    except Exception:  # noqa: BLE001
        pass
    return None


def _tesla_executable() -> str:
    """Return the path of the 'tesla' CLI executable."""
    import shutil
    import sys

    exe = shutil.which("tesla")
    if exe:
        return exe
    # Fall back to running via the current Python interpreter
    return f"{sys.executable} -m tesla_cli"


@automations_app.command("install")
def automations_install(
    source: str = typer.Option(
        "auto",
        "--source",
        help="Data source for the daemon: auto, poll, mqtt",
    ),
    interval: int = typer.Option(60, "--interval", "-i", help="Poll interval in seconds"),
) -> None:
    """Install automations as a background service (launchd on macOS, systemd on Linux).

    \b
    tesla automations install
    tesla automations install --source mqtt
    tesla automations install --source poll --interval 30
    """
    import subprocess
    import sys

    tesla_exe = _tesla_executable()
    run_args = f"{tesla_exe} automations run --source {source} --interval {interval}"

    if sys.platform == "darwin":
        _LAUNCHD_PLIST.parent.mkdir(parents=True, exist_ok=True)
        plist_content = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_LAUNCHD_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        {"".join(f"<string>{arg}</string>" + chr(10) + "        " for arg in run_args.split())}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{Path.home()}/.tesla-cli/automations.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/.tesla-cli/automations-error.log</string>
</dict>
</plist>
"""
        _LAUNCHD_PLIST.write_text(plist_content)
        try:
            subprocess.run(
                ["launchctl", "load", "-w", str(_LAUNCHD_PLIST)],
                check=True,
                capture_output=True,
                timeout=10,
            )
        except subprocess.CalledProcessError as exc:
            console.print(f"[red]launchctl load failed:[/red] {exc.stderr.decode()}")
            raise typer.Exit(1)
        render_success(
            f"Automations service installed and started.\n"
            f"  Plist: [dim]{_LAUNCHD_PLIST}[/dim]\n"
            f"  Logs:  [dim]~/.tesla-cli/automations.log[/dim]"
        )
    else:
        _SYSTEMD_UNIT.parent.mkdir(parents=True, exist_ok=True)
        unit_content = f"""\
[Unit]
Description=Tesla CLI Automations Daemon
After=network.target

[Service]
ExecStart={run_args}
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
        _SYSTEMD_UNIT.write_text(unit_content)
        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                check=True,
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", "tesla-automations"],
                check=True,
                capture_output=True,
                timeout=10,
            )
        except subprocess.CalledProcessError as exc:
            console.print(f"[red]systemctl failed:[/red] {exc.stderr.decode()}")
            raise typer.Exit(1)
        render_success(
            f"Automations service installed and started.\n"
            f"  Unit: [dim]{_SYSTEMD_UNIT}[/dim]\n"
            f"  Logs: [bold]journalctl --user -u tesla-automations -f[/bold]"
        )


@automations_app.command("uninstall")
def automations_uninstall() -> None:
    """Remove the automations background service.

    \b
    tesla automations uninstall
    """
    import subprocess
    import sys

    if not _service_installed():
        console.print("[yellow]Automations service is not installed.[/yellow]")
        raise typer.Exit(1)

    if sys.platform == "darwin":
        try:
            subprocess.run(
                ["launchctl", "unload", "-w", str(_LAUNCHD_PLIST)],
                capture_output=True,
                timeout=10,
            )
        except Exception:  # noqa: BLE001
            pass
        _LAUNCHD_PLIST.unlink(missing_ok=True)
        render_success("Automations service uninstalled.")
    else:
        try:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", "tesla-automations"],
                capture_output=True,
                timeout=10,
            )
        except Exception:  # noqa: BLE001
            pass
        _SYSTEMD_UNIT.unlink(missing_ok=True)
        render_success("Automations service uninstalled.")


@automations_app.command("status")
def automations_status() -> None:
    """Show automation service status: installed, running, PID, last rule fired.

    \b
    tesla automations status
    tesla -j automations status
    """
    import json as _json
    import sys

    engine = _engine()
    rules = engine.rules
    installed = _service_installed()
    running = _service_running() if installed else False
    pid = _service_pid() if running else None

    # Last fired: find the most recently fired rule across all rules
    last_fired_rule = None
    last_fired_at = None
    for rule in rules:
        if rule.last_fired is not None and (
            last_fired_at is None or rule.last_fired > last_fired_at
        ):
            last_fired_at = rule.last_fired
            last_fired_rule = rule.name

    platform = "launchd" if sys.platform == "darwin" else "systemd"
    unit_path = str(_LAUNCHD_PLIST) if sys.platform == "darwin" else str(_SYSTEMD_UNIT)

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "installed": installed,
                    "running": running,
                    "pid": pid,
                    "platform": platform,
                    "unit_path": unit_path,
                    "rules_total": len(rules),
                    "rules_enabled": sum(1 for r in rules if r.enabled),
                    "last_fired_rule": last_fired_rule,
                    "last_fired_at": last_fired_at.isoformat() if last_fired_at else None,
                }
            )
        )
        return

    from rich.table import Table

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("k", style="dim", width=18)
    t.add_column("v")

    installed_str = "[green]yes[/green]" if installed else "[dim]no[/dim]"
    running_str = (
        "[green]running[/green]"
        if running
        else ("[red]stopped[/red]" if installed else "[dim]—[/dim]")
    )
    pid_str = str(pid) if pid else "[dim]—[/dim]"
    last_str = (
        f"[bold]{last_fired_rule}[/bold] at {last_fired_at.strftime('%Y-%m-%d %H:%M:%S')}"
        if last_fired_rule
        else "[dim]never[/dim]"
    )

    t.add_row("Service manager", platform)
    t.add_row("Installed", installed_str)
    t.add_row("Status", running_str)
    t.add_row("PID", pid_str)
    t.add_row("Unit/Plist", f"[dim]{unit_path}[/dim]")
    t.add_row("Rules total", str(len(rules)))
    t.add_row("Rules enabled", str(sum(1 for r in rules if r.enabled)))
    t.add_row("Last rule fired", last_str)

    console.print()
    console.print(t)
    console.print()
