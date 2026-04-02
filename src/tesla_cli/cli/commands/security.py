"""Security commands: tesla security lock|unlock|sentry|valet|speed-limit|pin-to-drive|guest-mode."""

from __future__ import annotations

import typer

from tesla_cli.cli.commands.vehicle import _with_wake
from tesla_cli.cli.output import render_success
from tesla_cli.core.config import load_config, resolve_vin

security_app = typer.Typer(name="security", help="Security, sentry, and access controls.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@security_app.command("lock")
def security_lock(vin: str | None = VinOption) -> None:
    """Lock the vehicle."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "door_lock"), v)
    render_success("Vehicle locked 🔒")


@security_app.command("unlock")
def security_unlock(vin: str | None = VinOption) -> None:
    """Unlock the vehicle."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "door_unlock"), v)
    render_success("Vehicle unlocked 🔓")


@security_app.command("sentry")
def sentry(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle Sentry Mode."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "set_sentry_mode", on=on), v)
    status = "ON 👁️" if on else "OFF"
    render_success(f"Sentry Mode {status}")


@security_app.command("valet")
def valet(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    password: str | None = typer.Option(None, "--password", "-p", help="4-digit PIN"),
    vin: str | None = VinOption,
) -> None:
    """Toggle Valet Mode."""
    v = _vin(vin)
    params: dict = {"on": on}
    if password:
        params["password"] = password
    _with_wake(lambda b, v: b.command(v, "set_valet_mode", **params), v)
    status = "ON" if on else "OFF"
    render_success(f"Valet Mode {status}")


@security_app.command("speed-limit")
def speed_limit(
    action: str = typer.Argument(..., help="activate | deactivate | set"),
    pin: str | None = typer.Option(None, "--pin", help="4-digit PIN"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Speed limit in mph (for 'set')"),
    vin: str | None = VinOption,
) -> None:
    """Manage speed limit mode."""
    v = _vin(vin)
    if action == "activate":
        if not pin:
            typer.echo("PIN required for speed limit activation", err=True)
            raise typer.Exit(1)
        _with_wake(lambda b, v: b.command(v, "speed_limit_activate", pin=pin), v)
        render_success("Speed limit activated")
    elif action == "deactivate":
        if not pin:
            typer.echo("PIN required for speed limit deactivation", err=True)
            raise typer.Exit(1)
        _with_wake(lambda b, v: b.command(v, "speed_limit_deactivate", pin=pin), v)
        render_success("Speed limit deactivated")
    elif action == "set":
        if not limit:
            typer.echo("--limit required for speed limit set", err=True)
            raise typer.Exit(1)
        _with_wake(lambda b, v: b.command(v, "speed_limit_set_limit", limit_mph=limit), v)
        render_success(f"Speed limit set to {limit} mph")
    else:
        typer.echo(f"Unknown action: {action}. Use activate|deactivate|set", err=True)
        raise typer.Exit(1)


@security_app.command("pin-to-drive")
def pin_to_drive(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    password: str | None = typer.Option(None, "--password", "-p", help="PIN"),
    vin: str | None = VinOption,
) -> None:
    """Toggle PIN to Drive."""
    v = _vin(vin)
    params: dict = {"on": on}
    if password:
        params["password"] = password
    _with_wake(lambda b, v: b.command(v, "set_pin_to_drive", **params), v)
    status = "ON" if on else "OFF"
    render_success(f"PIN to Drive {status}")


@security_app.command("guest-mode")
def guest_mode(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle Guest Mode."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "guest_mode", enable=on), v)
    status = "ON" if on else "OFF"
    render_success(f"Guest Mode {status}")


@security_app.command("remote-start")
def security_remote_start(
    vin: str | None = VinOption,
) -> None:
    """Enable remote start (keyless drive for 2 minutes).

    The driver must enter their Tesla account password on the touchscreen.

    tesla security remote-start
    """
    import json as _json

    from tesla_cli.cli.output import console, is_json_mode, render_success

    v = _vin(vin)
    from tesla_cli.cli.commands.vehicle import _with_wake

    _with_wake(lambda b, v: b.command(v, "remote_start_drive"), v)

    if is_json_mode():
        console.print(_json.dumps({"remote_start": True}, indent=2))
        return
    render_success("Remote start enabled — vehicle can be driven for 2 minutes")
