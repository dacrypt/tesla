"""Tesla CLI - main application entry point."""

from __future__ import annotations

import difflib
import sys

import typer

from tesla_cli import __version__
from tesla_cli.cli.commands.config_cmd import config_app
from tesla_cli.cli.output import render_error, set_json_mode
from tesla_cli.core.exceptions import TeslaCliError

app = typer.Typer(
    name="tesla",
    help="Tesla CLI — track orders, control your vehicle, and analyze charging from the terminal.",
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
    lang: str = typer.Option("", "--lang", help="Language: en (default), es, pt, fr, de, it"),
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    """Tesla CLI - Order tracking and vehicle control."""
    set_json_mode(json_output)
    if lang:
        from tesla_cli.cli.i18n import set_lang

        set_lang(lang)
    if anon:
        from tesla_cli.cli.output import set_anon_mode
        from tesla_cli.core.config import load_config

        cfg = load_config()
        set_anon_mode(
            True,
            vin=cfg.general.default_vin,
            rn=cfg.order.reservation_number,
        )


def _all_command_names() -> list[str]:
    """Return all top-level command and group names registered on the app."""
    names: list[str] = []
    for cmd in app.registered_commands:
        if cmd.name:
            names.append(cmd.name)
    for grp in app.registered_groups:
        if grp.name:
            names.append(grp.name)
    return names


def main() -> None:
    """Entry point for the CLI."""
    try:
        app()
    except TeslaCliError as e:
        render_error(str(e), error_type=type(e).__name__)
        raise typer.Exit(1)
    except SystemExit as e:
        # Typer/Click exits with code 2 on UsageError (unknown command).
        # Intercept to offer "Did you mean?" suggestions.
        if e.code == 2 and len(sys.argv) > 1:
            typed = sys.argv[1]
            known = _all_command_names()
            matches = difflib.get_close_matches(typed, known, n=3, cutoff=0.6)
            if matches:
                from tesla_cli.cli.output import error_console

                suggestions = "  ".join(f"[bold cyan]{m}[/bold cyan]" for m in matches)
                error_console.print(f"\n[yellow]Did you mean?[/yellow]  {suggestions}\n")
        raise


# Lazy-register command groups to avoid import cost at startup
def _register_commands() -> None:
    # Core vehicle commands
    from tesla_cli.cli.commands.charge import charge_app
    from tesla_cli.cli.commands.climate import climate_app
    from tesla_cli.cli.commands.event_stream_cmd import alerts_command, events_command
    from tesla_cli.cli.commands.media import media_app
    from tesla_cli.cli.commands.notify import notify_app
    from tesla_cli.cli.commands.order import order_app
    from tesla_cli.cli.commands.runt import runt_app
    from tesla_cli.cli.commands.security import security_app
    from tesla_cli.cli.commands.simit import simit_app
    from tesla_cli.cli.commands.vehicle import vehicle_app

    app.add_typer(order_app, name="order")
    app.add_typer(vehicle_app, name="vehicle")
    app.add_typer(charge_app, name="charge")
    app.add_typer(climate_app, name="climate")
    app.add_typer(security_app, name="security")
    app.add_typer(simit_app, name="simit")
    app.add_typer(media_app, name="media")
    app.add_typer(notify_app, name="notify")
    app.add_typer(runt_app, name="runt")
    app.command("alerts")(alerts_command)
    app.command("events")(events_command)

    # Service center management
    from tesla_cli.cli.commands.service import service_app

    app.add_typer(service_app, name="service")

    # Energy (Powerwall/Solar)
    from tesla_cli.cli.commands.energy import energy_app

    app.add_typer(energy_app, name="energy")

    # Data sources & exports
    from tesla_cli.cli.commands.data_cmd import data_app
    from tesla_cli.cli.commands.domain_cmd import domain_app

    app.add_typer(data_app, name="data")
    app.add_typer(domain_app, name="domain")

    # Automations
    from tesla_cli.cli.commands.automations import automations_app

    app.add_typer(automations_app, name="automations")

    # Integrations
    from tesla_cli.cli.commands.abrp import abrp_app
    from tesla_cli.cli.commands.ble import ble_app
    from tesla_cli.cli.commands.geofence import geofence_app
    from tesla_cli.cli.commands.ha import ha_app
    from tesla_cli.cli.commands.mqtt_cmd import mqtt_app
    from tesla_cli.cli.commands.providers_cmd import providers_app
    from tesla_cli.cli.commands.serve import serve_app
    from tesla_cli.cli.commands.setup import setup_wizard
    from tesla_cli.cli.commands.telemetry import telemetry_app
    from tesla_cli.cli.commands.teslaMate import teslaMate_app

    app.command("setup")(setup_wizard)
    app.add_typer(teslaMate_app, name="teslaMate")
    app.add_typer(telemetry_app, name="telemetry")
    app.add_typer(abrp_app, name="abrp")
    app.add_typer(ble_app, name="ble")
    app.add_typer(geofence_app, name="geofence")
    app.add_typer(ha_app, name="ha")
    app.add_typer(mqtt_app, name="mqtt")
    app.add_typer(serve_app, name="serve")
    app.add_typer(providers_app, name="providers")

    # Dashcam clip management
    from tesla_cli.cli.commands.dashcam import dashcam_app

    app.add_typer(dashcam_app, name="dashcam")

    # Smart scene commands
    from tesla_cli.cli.commands.scenes import scenes_app

    app.add_typer(scenes_app, name="scene")

    # Short aliases (hidden — do not appear in --help)
    @app.command("cs", hidden=True)
    def _alias_cs(
        watch: bool = typer.Option(False, "--watch", "-w", help="Live monitor"),
        oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
        interval: int = typer.Option(30, "--interval", "-i", help="Refresh interval in seconds"),
        vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
    ):
        """Alias: tesla charge status"""
        from tesla_cli.cli.commands.charge import charge_status

        charge_status(watch=watch, oneline=oneline, interval=interval, vin=vin)

    @app.command("vs", hidden=True)
    def _alias_vs(
        oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
        vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
    ):
        """Alias: tesla vehicle summary"""
        from tesla_cli.cli.commands.vehicle import vehicle_summary

        vehicle_summary(oneline=oneline, vin=vin)

    @app.command("os", hidden=True)
    def _alias_os(
        oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
    ):
        """Alias: tesla order status"""
        from tesla_cli.cli.commands.order import order_status

        order_status(oneline=oneline)

    @app.command("vr", hidden=True)
    def _alias_vr(
        oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line output"),
        vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
    ):
        """Alias: tesla vehicle ready"""
        from tesla_cli.cli.commands.vehicle import vehicle_ready

        vehicle_ready(oneline=oneline, vin=vin)

    @app.command("sm", hidden=True)
    def _alias_sm(
        vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
    ):
        """Alias: tesla scene morning"""
        from tesla_cli.cli.commands.scenes import scene_morning

        scene_morning(vin=vin)

    @app.command("sg", hidden=True)
    def _alias_sg(
        vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
    ):
        """Alias: tesla scene goodnight"""
        from tesla_cli.cli.commands.scenes import scene_goodnight

        scene_goodnight(vin=vin)


@app.command("quickstart")
def quickstart() -> None:
    """Show a quick-start guide with the most useful daily commands."""
    from tesla_cli.cli.output import console

    console.print("""
[bold cyan]Tesla CLI — Quick Start Guide[/bold cyan]

[bold]Morning routine:[/bold]
  [green]tesla vehicle ready[/green]              Am I ready to drive?
  [green]tesla vehicle ready --oneline[/green]    ✅ Ready | 🔋 82% | 🌡 22°C
  [green]tesla vehicle status-line[/green]        🔋72% 🔒 🛡 🌡22° (for tmux)

[bold]Charging:[/bold]
  [green]tesla charge status --oneline[/green]    🔋 65% | ⚡ 11kW | 1h30m to 80%
  [green]tesla charge last[/green]                Most recent session + cost
  [green]tesla charge weekly[/green]              Weekly kWh + cost summary
  [green]tesla charge watch-complete[/green]      Notify when charge finishes

[bold]Vehicle control:[/bold]
  [green]tesla security lock[/green]              Lock doors
  [green]tesla security unlock[/green]            Unlock doors
  [green]tesla vehicle sentry --on[/green]        Enable Sentry Mode
  [green]tesla climate on[/green]                 Start climate/AC
  [green]tesla media send-destination "..."[/green]  Navigate somewhere

[bold]Analytics:[/bold]
  [green]tesla teslaMate battery-degradation[/green]  Battery health trend
  [green]tesla teslaMate monthly-cost[/green]     Cost trend by month
  [green]tesla teslaMate trips[/green]            Recent trip history

[bold]Server & API:[/bold]
  [green]tesla serve[/green]                      Start REST API + web dashboard
  [green]tesla config doctor[/green]              Validate all connections

[dim]Run [bold]tesla <group> --help[/bold] for full command list in any group.[/dim]
""")


_register_commands()
