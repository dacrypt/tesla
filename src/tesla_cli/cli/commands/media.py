"""Media commands: tesla media play|pause|next|prev|volume|fav."""

from __future__ import annotations

import typer

from tesla_cli.cli.commands.vehicle import _with_wake
from tesla_cli.cli.output import render_success
from tesla_cli.core.config import load_config, resolve_vin

media_app = typer.Typer(name="media", help="Media playback controls.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


@media_app.command("play")
def media_play(vin: str | None = VinOption) -> None:
    """Toggle play/pause."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "media_toggle_playback"), v)
    render_success("Media toggled ▶️")


@media_app.command("pause")
def media_pause(vin: str | None = VinOption) -> None:
    """Pause playback (same as play toggle)."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "media_toggle_playback"), v)
    render_success("Media toggled ⏸️")


@media_app.command("next")
def media_next(vin: str | None = VinOption) -> None:
    """Next track."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "media_next_track"), v)
    render_success("Next track ⏭️")


@media_app.command("prev")
def media_prev(vin: str | None = VinOption) -> None:
    """Previous track."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "media_prev_track"), v)
    render_success("Previous track ⏮️")


@media_app.command("volume")
def media_volume(
    level: float | None = typer.Argument(None, help="Volume level 0.0-11.0 (omit to step up)"),
    down: bool = typer.Option(False, "--down", "-d", help="Step volume down instead of up"),
    vin: str | None = VinOption,
) -> None:
    """Set volume or step up/down."""
    v = _vin(vin)
    if level is not None:
        if not 0.0 <= level <= 11.0:
            raise typer.BadParameter("Volume must be between 0.0 and 11.0.")
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
    vin: str | None = VinOption,
) -> None:
    """Switch to next/previous favorite."""
    v = _vin(vin)
    cmd = "media_next_fav" if direction == "next" else "media_prev_fav"
    _with_wake(lambda b, v: b.command(v, cmd), v)
    render_success(f"Favorite {direction} ⭐")


# ═══════════════════════════════════════════════════════════════════════════════
# Navigation commands (absorbed from nav.py)
# ═══════════════════════════════════════════════════════════════════════════════


@media_app.command("send-destination")
def media_send_destination(
    destination: str = typer.Argument(..., help="Address or place name"),
    vin: str | None = VinOption,
) -> None:
    """Send a destination to the vehicle navigation."""
    import time as _time

    v = _vin(vin)
    ts = str(int(_time.time() * 1000))
    _with_wake(
        lambda b, v: b.command(
            v, "share",
            type="share_ext_content_raw",
            value={"android.intent.extra.TEXT": destination},
            locale="en-US", timestamp_ms=ts,
        ), v,
    )
    render_success(f"Destination sent: {destination}")


@media_app.command("supercharger")
def media_supercharger(vin: str | None = VinOption) -> None:
    """Navigate to nearest Supercharger."""
    v = _vin(vin)
    _with_wake(lambda b, v: b.command(v, "navigation_sc_request", id=0, order=0, offset=0), v)
    render_success("Navigating to nearest Supercharger")


@media_app.command("home")
def media_home(vin: str | None = VinOption) -> None:
    """Navigate home."""
    import time as _time

    v = _vin(vin)
    ts = str(int(_time.time() * 1000))
    _with_wake(
        lambda b, v: b.command(
            v, "share",
            type="share_ext_content_raw",
            value={"android.intent.extra.TEXT": "Home"},
            locale="en-US", timestamp_ms=ts,
        ), v,
    )
    render_success("Navigating home")


@media_app.command("work")
def media_work(vin: str | None = VinOption) -> None:
    """Navigate to work."""
    import time as _time

    v = _vin(vin)
    ts = str(int(_time.time() * 1000))
    _with_wake(
        lambda b, v: b.command(
            v, "share",
            type="share_ext_content_raw",
            value={"android.intent.extra.TEXT": "Work"},
            locale="en-US", timestamp_ms=ts,
        ), v,
    )
    render_success("Navigating to work")
