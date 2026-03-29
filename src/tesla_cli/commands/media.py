"""Media commands: tesla media play|pause|next|prev|volume|fav."""

from __future__ import annotations

from typing import Optional

import typer

from tesla_cli.config import load_config, resolve_vin
from tesla_cli.commands.vehicle import _with_wake
from tesla_cli.output import render_success

media_app = typer.Typer(name="media", help="Media playback controls.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@media_app.command("play")
def media_play(vin: Optional[str] = VinOption) -> None:
    """Toggle play/pause."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "media_toggle_playback"), v)
    render_success("Media toggled ▶️")


@media_app.command("pause")
def media_pause(vin: Optional[str] = VinOption) -> None:
    """Pause playback (same as play toggle)."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "media_toggle_playback"), v)
    render_success("Media toggled ⏸️")


@media_app.command("next")
def media_next(vin: Optional[str] = VinOption) -> None:
    """Next track."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "media_next_track"), v)
    render_success("Next track ⏭️")


@media_app.command("prev")
def media_prev(vin: Optional[str] = VinOption) -> None:
    """Previous track."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "media_prev_track"), v)
    render_success("Previous track ⏮️")


@media_app.command("volume")
def media_volume(
    level: Optional[float] = typer.Argument(None, help="Volume level 0.0-11.0 (omit to step up)"),
    down: bool = typer.Option(False, "--down", "-d", help="Step volume down instead of up"),
    vin: Optional[str] = VinOption,
) -> None:
    """Set volume or step up/down."""
    v = _vin(vin)
    if level is not None:
        _with_wake(lambda b, v: b.command(v, "adjust_volume", volume=level), v)
        render_success(f"Volume set to {level}")
    elif down:
        _with_wake(lambda b, v: b.command(v, "media_volume_down"), v)
        render_success("Volume down 🔉")
    else:
        _with_wake(lambda b, v: b.command(v, "media_volume_up"), v)
        render_success("Volume up 🔊")


@media_app.command("fav")
def media_fav(
    direction: str = typer.Argument("next", help="next | prev"),
    vin: Optional[str] = VinOption,
) -> None:
    """Switch to next/previous favorite."""
    v = _vin(vin)
    cmd = "media_next_fav" if direction == "next" else "media_prev_fav"
    _with_wake(lambda b, v: b.command(v, cmd), v)
    render_success(f"Favorite {direction} ⭐")
