"""Charge commands: tesla charge status|start|stop|limit|amps|port-open|port-close|schedule|history."""

from __future__ import annotations

import typer

from tesla_cli.backends import get_vehicle_backend
from tesla_cli.commands.vehicle import _with_wake
from tesla_cli.config import load_config, resolve_vin
from tesla_cli.models.charge import ChargeState
from tesla_cli.output import render_dict, render_model, render_success, render_table

charge_app = typer.Typer(name="charge", help="Battery and charging management.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _backend():
    return get_vehicle_backend(load_config())


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@charge_app.command("status")
def charge_status(vin: str | None = VinOption) -> None:
    """Show current charge state."""
    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_charge_state(v), v)
    state = ChargeState.model_validate(data)
    render_model(state, title="Charge State")


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
    percent: int = typer.Argument(..., help="Charge limit percentage (50-100)"),
    vin: str | None = VinOption,
) -> None:
    """Set charge limit percentage."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "set_charge_limit", percent=percent), v)
    render_success(f"Charge limit set to {percent}%")


@charge_app.command("amps")
def charge_amps(
    amps: int = typer.Argument(..., help="Charging amps"),
    vin: str | None = VinOption,
) -> None:
    """Set charging amperage."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "set_charging_amps", charging_amps=amps), v)
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
