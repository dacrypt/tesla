"""Streaming telemetry commands (future)."""

from __future__ import annotations

import typer

from tesla_cli.output import console

stream_app = typer.Typer(name="stream", help="Real-time vehicle telemetry streaming (coming soon).")


@stream_app.command("live")
def stream_live() -> None:
    """Stream live vehicle data via WebSocket."""
    console.print(
        "[yellow]Streaming telemetry is not yet implemented.[/yellow]\n"
        "This will support:\n"
        "  - Tessie WebSocket: wss://streaming.tessie.com/<vin>\n"
        "  - Fleet Telemetry: Server-Sent Events\n"
    )
    raise typer.Exit(0)
