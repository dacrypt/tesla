"""Tesla CLI - main application entry point."""

from __future__ import annotations

import typer

from tesla_cli import __version__
from tesla_cli.commands.config_cmd import config_app
from tesla_cli.exceptions import TeslaCliError
from tesla_cli.output import render_error, set_json_mode

app = typer.Typer(
    name="tesla",
    help="Tesla CLI - Order tracking and vehicle control.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Register sub-command groups
app.add_typer(config_app, name="config")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tesla-cli v{__version__}")
        raise typer.Exit()


@app.callback()
def global_options(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    """Tesla CLI - Order tracking and vehicle control."""
    set_json_mode(json_output)


def main() -> None:
    """Entry point for the CLI."""
    try:
        app()
    except TeslaCliError as e:
        render_error(str(e), error_type=type(e).__name__)
        raise typer.Exit(1)


# Lazy-register order and vehicle commands to avoid import cost at startup
def _register_commands() -> None:
    from tesla_cli.commands.charge import charge_app
    from tesla_cli.commands.climate import climate_app
    from tesla_cli.commands.dashboard import dashboard_app
    from tesla_cli.commands.dossier import dossier_app
    from tesla_cli.commands.media import media_app
    from tesla_cli.commands.nav import nav_app
    from tesla_cli.commands.order import order_app
    from tesla_cli.commands.runt_cmd import runt_app
    from tesla_cli.commands.security import security_app
    from tesla_cli.commands.sharing import sharing_app
    from tesla_cli.commands.simit_cmd import simit_app
    from tesla_cli.commands.stream import stream_app
    from tesla_cli.commands.vehicle import vehicle_app

    app.add_typer(order_app, name="order")
    app.add_typer(vehicle_app, name="vehicle")
    app.add_typer(stream_app, name="stream")
    app.add_typer(dossier_app, name="dossier")
    app.add_typer(charge_app, name="charge")
    app.add_typer(climate_app, name="climate")
    app.add_typer(security_app, name="security")
    app.add_typer(media_app, name="media")
    app.add_typer(nav_app, name="nav")
    app.add_typer(sharing_app, name="sharing")
    app.add_typer(dashboard_app, name="dashboard")
    app.add_typer(runt_app, name="runt")
    app.add_typer(simit_app, name="simit")

    from tesla_cli.commands.setup import setup_wizard
    app.command("setup")(setup_wizard)


_register_commands()
