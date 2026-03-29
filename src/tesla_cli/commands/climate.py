"""Climate commands: tesla climate on|off|temp|seat-heater|steering-heater|dog-mode|camp-mode|bioweapon|defrost."""

from __future__ import annotations

import typer

from tesla_cli.commands.vehicle import _with_wake
from tesla_cli.config import load_config, resolve_vin
from tesla_cli.models.climate import ClimateState
from tesla_cli.output import render_model, render_success

climate_app = typer.Typer(name="climate", help="Climate and HVAC controls.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@climate_app.command("status")
def climate_status(vin: str | None = VinOption) -> None:
    """Show climate state."""
    v = _vin(vin)
    data = _with_wake(lambda b, v: b.get_climate_state(v), v)
    state = ClimateState.model_validate(data)
    render_model(state, title="Climate State")


@climate_app.command("on")
def climate_on(vin: str | None = VinOption) -> None:
    """Turn climate/AC on."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "auto_conditioning_start"), v)
    render_success("Climate ON")


@climate_app.command("off")
def climate_off(vin: str | None = VinOption) -> None:
    """Turn climate/AC off."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "auto_conditioning_stop"), v)
    render_success("Climate OFF")


@climate_app.command("temp")
def climate_temp(
    driver: float = typer.Argument(..., help="Driver temp in °C"),
    passenger: float | None = typer.Argument(None, help="Passenger temp (defaults to driver)"),
    vin: str | None = VinOption,
) -> None:
    """Set temperature."""
    v = _vin(vin)
    pass_temp = passenger if passenger is not None else driver
    _with_wake(
        lambda b, v: b.command(v, "set_temps", driver_temp=driver, passenger_temp=pass_temp),
        v,
    )
    render_success(f"Temperature set to {driver}°C / {pass_temp}°C")


@climate_app.command("seat-heater")
def seat_heater(
    seat: int = typer.Argument(..., help="Seat (0=driver, 1=passenger, 2=rear-left, 4=rear-center, 5=rear-right)"),
    level: int = typer.Argument(..., help="Level (0=off, 1=low, 2=med, 3=high)"),
    vin: str | None = VinOption,
) -> None:
    """Set seat heater level."""
    v = _vin(vin)
    _with_wake(
        lambda b, v: b.command(v, "remote_seat_heater_request", heater=seat, level=level),
        v,
    )
    render_success(f"Seat {seat} heater set to level {level}")


@climate_app.command("steering-heater")
def steering_heater(
    on: bool = typer.Argument(..., help="Turn on (true) or off (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle steering wheel heater."""
    v = _vin(vin)
    _with_wake(
        lambda b, v: b.command(v, "remote_steering_wheel_heater_request", on=on), v
    )
    status = "ON" if on else "OFF"
    render_success(f"Steering wheel heater {status}")


@climate_app.command("dog-mode")
def dog_mode(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle Dog Mode."""
    v = _vin(vin)
    mode = 2 if on else 0  # 0=off, 2=dog
    _with_wake(
        lambda b, v: b.command(v, "set_climate_keeper_mode", climate_keeper_mode=mode),
        v,
    )
    status = "ON" if on else "OFF"
    render_success(f"Dog Mode {status}")


@climate_app.command("camp-mode")
def camp_mode(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle Camp Mode."""
    v = _vin(vin)
    mode = 3 if on else 0  # 0=off, 3=camp
    _with_wake(
        lambda b, v: b.command(v, "set_climate_keeper_mode", climate_keeper_mode=mode),
        v,
    )
    status = "ON" if on else "OFF"
    render_success(f"Camp Mode {status}")


@climate_app.command("bioweapon")
def bioweapon(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle Bioweapon Defense Mode."""
    v = _vin(vin)
    _with_wake(
        lambda b, v: b.command(v, "set_bioweapon_mode", on=on, manual_override=True),
        v,
    )
    status = "ON" if on else "OFF"
    render_success(f"Bioweapon Defense Mode {status}")


@climate_app.command("defrost")
def defrost(
    on: bool = typer.Argument(True, help="Enable (true) or disable (false)"),
    vin: str | None = VinOption,
) -> None:
    """Toggle max defrost (preconditioning max)."""
    v = _vin(vin)
    _with_wake(
        lambda b, v: b.command(v, "set_preconditioning_max", on=on), v
    )
    status = "ON" if on else "OFF"
    render_success(f"Max Defrost {status}")
