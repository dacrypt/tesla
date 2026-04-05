"""Energy commands: tesla energy status|info|history|backup|mode|storm|sites."""

from __future__ import annotations

import typer

from tesla_cli.cli.output import (
    console,
    is_json_mode,
    render_dict,
    render_success,
    render_table,
)
from tesla_cli.core.backends.energy import load_energy_backend
from tesla_cli.core.config import load_config

energy_app = typer.Typer(name="energy", help="Tesla Energy (Powerwall/Solar) management.")

VALID_MODES = ("self_consumption", "autonomous", "backup")


def _backend():
    return load_energy_backend()


def _site_id(explicit: int | None = None) -> int:
    """Resolve site_id from argument or config."""
    if explicit and explicit > 0:
        return explicit
    cfg = load_config()
    if cfg.energy.site_id > 0:
        return cfg.energy.site_id
    from tesla_cli.core.exceptions import ConfigurationError

    raise ConfigurationError(
        "No energy site configured.\n"
        "Run: tesla energy sites   to discover your site ID\n"
        "Then: tesla config set energy.site_id <ID>"
    )


# ── Commands ────────────────────────────────────────────────────────────────


@energy_app.command("sites")
def energy_sites() -> None:
    """List all Tesla energy sites (Powerwall/Solar) on your account."""
    backend = _backend()
    sites = backend.list_energy_sites()
    if is_json_mode():
        import json

        typer.echo(json.dumps(sites, indent=2))
        return
    if not sites:
        console.print("[yellow]No energy sites found on this account.[/yellow]")
        return
    rows = []
    for s in sites:
        rows.append(
            {
                "site_id": str(s.get("energy_site_id", "")),
                "name": s.get("site_name", s.get("display_name", "")),
                "type": s.get("resource_type", ""),
                "gateway": s.get("gateway_id", ""),
            }
        )
    render_table(rows, columns=["site_id", "name", "type", "gateway"], title="Energy Sites")


@energy_app.command("status")
def energy_status(
    site: int = typer.Option(0, "--site", "-s", help="Energy site ID (uses config default if 0)"),
    oneline: bool = typer.Option(False, "--oneline", "-1", help="Single-line summary"),
) -> None:
    """Show live power flow, battery %, and grid status.

    tesla energy status             # detailed view
    tesla energy status --oneline   # ☀️ 4.2kW | 🔋 85% | 🏠 1.8kW | ⚡ -2.4kW grid
    """
    backend = _backend()
    sid = _site_id(site)
    data = backend.live_status(sid)

    if is_json_mode():
        import json

        typer.echo(json.dumps(data, indent=2))
        return

    solar_kw = data.get("solar_power", 0) / 1000
    battery_pct = data.get("percentage_charged", data.get("battery_percentage", 0))
    load_kw = data.get("load_power", 0) / 1000
    grid_kw = data.get("grid_power", 0) / 1000
    battery_kw = data.get("battery_power", 0) / 1000
    grid_status = data.get("grid_status", "")
    storm_mode = data.get("storm_mode_active", False)

    if oneline:
        grid_sign = "+" if grid_kw > 0 else ""
        parts = [
            f"\u2600\ufe0f {solar_kw:.1f}kW",
            f"\U0001f50b {battery_pct:.0f}%",
            f"\U0001f3e0 {load_kw:.1f}kW",
            f"\u26a1 {grid_sign}{grid_kw:.1f}kW grid",
        ]
        console.print(" | ".join(parts))
        return

    console.print(f"\n[bold cyan]Energy Status — Site {sid}[/bold cyan]")
    console.print(f"  Solar:         [green]{solar_kw:.2f} kW[/green]")
    console.print(f"  Battery:       [yellow]{battery_pct:.1f}%[/yellow]  ({battery_kw:.2f} kW)")
    console.print(f"  Home load:     {load_kw:.2f} kW")
    grid_color = "red" if grid_kw > 0 else "green"
    grid_dir = "importing" if grid_kw > 0 else "exporting"
    console.print(f"  Grid:          [{grid_color}]{grid_kw:.2f} kW ({grid_dir})[/{grid_color}]")
    console.print(f"  Grid status:   {grid_status}")
    if storm_mode:
        console.print("  [bold yellow]Storm Watch: ACTIVE[/bold yellow]")
    console.print()


@energy_app.command("info")
def energy_info(
    site: int = typer.Option(0, "--site", "-s", help="Energy site ID"),
) -> None:
    """Show site configuration, assets, and features."""
    backend = _backend()
    sid = _site_id(site)
    data = backend.get_site_info(sid)
    if is_json_mode():
        import json

        typer.echo(json.dumps(data, indent=2))
        return
    render_dict(data, title=f"Site Info — {sid}")


@energy_app.command("history")
def energy_history(
    site: int = typer.Option(0, "--site", "-s", help="Energy site ID"),
    period: str = typer.Option("day", "--period", "-p", help="Period: day | week | month | year"),
    start: str = typer.Option("", "--start", help="Start date (ISO 8601, e.g. 2024-01-01T00:00:00Z)"),
    end: str = typer.Option("", "--end", help="End date (ISO 8601)"),
) -> None:
    """Show energy production and consumption history.

    tesla energy history              # today
    tesla energy history --period week
    """
    backend = _backend()
    sid = _site_id(site)
    data = backend.energy_history(sid, period=period, start=start, end=end)
    if is_json_mode():
        import json

        typer.echo(json.dumps(data, indent=2))
        return
    render_dict(data, title=f"Energy History ({period}) — Site {sid}")


@energy_app.command("backup")
def energy_backup(
    reserve: int | None = typer.Argument(None, help="Backup reserve % to set (0-100). Omit to show current."),
    site: int = typer.Option(0, "--site", "-s", help="Energy site ID"),
) -> None:
    """Show or set the battery backup reserve percentage.

    tesla energy backup       # show current reserve
    tesla energy backup 30    # set reserve to 30%
    """
    backend = _backend()
    sid = _site_id(site)

    if reserve is None:
        # Show current backup reserve from live_status
        data = backend.live_status(sid)
        if is_json_mode():
            import json

            typer.echo(json.dumps({"backup_reserve_percent": data.get("backup_reserve_percent")}, indent=2))
            return
        pct = data.get("backup_reserve_percent", "?")
        console.print(f"Backup reserve: [bold]{pct}%[/bold]")
        return

    if not 0 <= reserve <= 100:
        raise typer.BadParameter("Reserve must be between 0 and 100.")
    result = backend.set_backup_reserve(sid, reserve)
    if is_json_mode():
        import json

        typer.echo(json.dumps(result, indent=2))
        return
    render_success(f"Backup reserve set to {reserve}%")


@energy_app.command("mode")
def energy_mode(
    new_mode: str | None = typer.Argument(
        None,
        help="Operation mode to set: self_consumption | autonomous | backup. Omit to show current.",
    ),
    site: int = typer.Option(0, "--site", "-s", help="Energy site ID"),
) -> None:
    """Show or set the operation mode.

    tesla energy mode                       # show current mode
    tesla energy mode self_consumption      # set mode
    """
    backend = _backend()
    sid = _site_id(site)

    if new_mode is None:
        data = backend.live_status(sid)
        if is_json_mode():
            import json

            typer.echo(json.dumps({"operation_mode": data.get("operation_mode")}, indent=2))
            return
        mode = data.get("operation_mode", "?")
        console.print(f"Operation mode: [bold]{mode}[/bold]")
        return

    if new_mode not in VALID_MODES:
        raise typer.BadParameter(f"Invalid mode. Choose from: {', '.join(VALID_MODES)}")
    result = backend.set_operation_mode(sid, new_mode)
    if is_json_mode():
        import json

        typer.echo(json.dumps(result, indent=2))
        return
    render_success(f"Operation mode set to '{new_mode}'")


@energy_app.command("storm")
def energy_storm(
    site: int = typer.Option(0, "--site", "-s", help="Energy site ID"),
    on: bool = typer.Option(False, "--on", help="Enable storm watch"),
    off: bool = typer.Option(False, "--off", help="Disable storm watch"),
) -> None:
    """Show or toggle Storm Watch mode.

    tesla energy storm          # show current storm watch state
    tesla energy storm --on     # enable storm watch
    tesla energy storm --off    # disable storm watch
    """
    backend = _backend()
    sid = _site_id(site)

    if not on and not off:
        # Show current state
        data = backend.live_status(sid)
        if is_json_mode():
            import json

            typer.echo(json.dumps({"storm_mode_active": data.get("storm_mode_active")}, indent=2))
            return
        active = data.get("storm_mode_active", False)
        state = "[bold green]ACTIVE[/bold green]" if active else "[dim]inactive[/dim]"
        console.print(f"Storm Watch: {state}")
        return

    if on and off:
        raise typer.BadParameter("Cannot use --on and --off together.")

    enabled = on
    result = backend.set_storm_mode(sid, enabled)
    if is_json_mode():
        import json

        typer.echo(json.dumps(result, indent=2))
        return
    label = "enabled" if enabled else "disabled"
    render_success(f"Storm Watch {label}")


@energy_app.command("backup-history")
def energy_backup_history(
    site: int = typer.Option(0, "--site", "-s", help="Energy site ID"),
    period: str = typer.Option("day", "--period", "-p", help="Period: day | week | month | year"),
) -> None:
    """Show backup event history."""
    backend = _backend()
    sid = _site_id(site)
    data = backend.backup_history(sid, period=period)
    if is_json_mode():
        import json

        typer.echo(json.dumps(data, indent=2))
        return
    render_dict(data, title=f"Backup History ({period}) — Site {sid}")
