"""Security commands: tesla security lock|unlock|sentry|valet|speed-limit|pin-to-drive|guest-mode."""

from __future__ import annotations

from typing import Optional

import typer

from tesla_cli.backends import get_vehicle_backend
from tesla_cli.config import load_config, resolve_vin
from tesla_cli.commands.vehicle import _with_wake
from tesla_cli.output import render_success

security_app = typer.Typer(name="security", help="Security, sentry, and access controls.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@security_app.command("lock")
def security_lock(vin: Optional[str] = VinOption) -> None:
    """Lock the vehicle."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "door_lock"), v)
    render_success("Vehicle locked 🔒")


@security_app.command("unlock")
def security_unlock(vin: Optional[str] = VinOption) -> None:
    """Unlock the vehicle."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "door_unlock"), v)
    render_success("Vehicle unlocked 🔓")


@security_app.command("sentry")
def sentry(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: Optional[str] = VinOption,
) -> None:
    """Toggle Sentry Mode."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "set_sentry_mode", on=on), v)
    status = "ON 👁️" if on else "OFF"
    render_success(f"Sentry Mode {status}")


@security_app.command("valet")
def valet(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="4-digit PIN"),
    vin: Optional[str] = VinOption,
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
    pin: Optional[str] = typer.Option(None, "--pin", help="4-digit PIN"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Speed limit in mph (for 'set')"),
    vin: Optional[str] = VinOption,
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
        _with_wake(
            lambda b, v: b.command(v, "speed_limit_set_limit", limit_mph=limit), v
        )
        render_success(f"Speed limit set to {limit} mph")
    else:
        typer.echo(f"Unknown action: {action}. Use activate|deactivate|set", err=True)
        raise typer.Exit(1)


@security_app.command("pin-to-drive")
def pin_to_drive(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="PIN"),
    vin: Optional[str] = VinOption,
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
    vin: Optional[str] = VinOption,
) -> None:
    """Toggle Guest Mode."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "guest_mode", enable=on), v)
    status = "ON" if on else "OFF"
    render_success(f"Guest Mode {status}")
