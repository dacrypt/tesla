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
    anon: bool = typer.Option(False, "--anon", help="Anonymize PII (VIN, email, name) in output"),
    lang: str = typer.Option("", "--lang", help="Language: en (default) or es"),
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    """Tesla CLI - Order tracking and vehicle control."""
    set_json_mode(json_output)
    if lang:
        from tesla_cli.i18n import set_lang
        set_lang(lang)
    if anon:
        from tesla_cli.config import load_config
        from tesla_cli.output import set_anon_mode
        cfg = load_config()
        set_anon_mode(
            True,
            vin=cfg.general.default_vin,
            rn=cfg.order.reservation_number,
        )


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
    from tesla_cli.commands.notify import notify_app
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
    app.add_typer(notify_app, name="notify")
    app.add_typer(runt_app, name="runt")
    app.add_typer(simit_app, name="simit")

    from tesla_cli.commands.abrp import abrp_app
    from tesla_cli.commands.ble import ble_app
    from tesla_cli.commands.geofence import geofence_app
    from tesla_cli.commands.ha import ha_app
    from tesla_cli.commands.setup import setup_wizard
    from tesla_cli.commands.teslaMate import teslaMate_app
    app.command("setup")(setup_wizard)
    app.add_typer(teslaMate_app, name="teslaMate")
    app.add_typer(abrp_app, name="abrp")
    app.add_typer(ble_app, name="ble")
    app.add_typer(geofence_app, name="geofence")
    app.add_typer(ha_app, name="ha")


_register_commands()
