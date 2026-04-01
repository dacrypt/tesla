"""Navigation commands: tesla nav send|supercharger|home|work."""

from __future__ import annotations

import time

import typer

from tesla_cli.commands.vehicle import _with_wake
from tesla_cli.config import load_config, resolve_vin
from tesla_cli.output import render_success

nav_app = typer.Typer(name="nav", help="Navigation and destination controls.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@nav_app.command("send")
def nav_send(
    destination: str = typer.Argument(..., help="Address or place name"),
    vin: str | None = VinOption,
) -> None:
    """Send a destination to the vehicle."""
    v = _vin(vin)
    ts = str(int(time.time() * 1000))
    _with_wake(
        lambda b, v: b.command(
            v,
            "share",
            type="share_ext_content_raw",
            value={"android.intent.extra.TEXT": destination},
            locale="en-US",
            timestamp_ms=ts,
        ),
        v,
    )
    render_success(f"Destination sent: {destination}")


@nav_app.command("supercharger")
def nav_supercharger(vin: str | None = VinOption) -> None:
    """Navigate to nearest Supercharger."""
    v = _vin(vin)
    _with_wake(
        lambda b, v: b.command(v, "navigation_sc_request", id=0, order=0, offset=0), v
    )
    render_success("Navigating to nearest Supercharger ⚡")


@nav_app.command("home")
def nav_home(vin: str | None = VinOption) -> None:
    """Navigate home."""
    v = _vin(vin)
    ts = str(int(time.time() * 1000))
    _with_wake(
        lambda b, v: b.command(
            v,
            "share",
            type="share_ext_content_raw",
            value={"android.intent.extra.TEXT": "Home"},
            locale="en-US",
            timestamp_ms=ts,
        ),
        v,
    )
    render_success("Navigating home 🏠")


@nav_app.command("work")
def nav_work(vin: str | None = VinOption) -> None:
    """Navigate to work."""
    v = _vin(vin)
    ts = str(int(time.time() * 1000))
    _with_wake(
        lambda b, v: b.command(
            v,
            "share",
            type="share_ext_content_raw",
            value={"android.intent.extra.TEXT": "Work"},
            locale="en-US",
            timestamp_ms=ts,
        ),
        v,
    )
    render_success("Navigating to work 🏢")
