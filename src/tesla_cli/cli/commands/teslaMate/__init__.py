"""TeslaMate integration commands: tesla teslaMate trips/charging/updates/status.

Package layout: shared imports/helpers live here; commands are split into
_stack, _trips, _analytics. Names tests patch on ``tesla_cli.cli.commands.teslaMate`` are
looked up by the submodules through this package — keep them here.
"""

# ruff: noqa: F401, I001

from __future__ import annotations

import json

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.cli.i18n import t as i18n_t
from tesla_cli.cli.output import console, is_json_mode, render_success, render_table
from tesla_cli.core.config import load_config, save_config

teslaMate_app = typer.Typer(
    name="teslaMate",
    help="TeslaMate database integration — trips, charging, OTA history.",
)


def _backend():
    from tesla_cli.core.backends.teslaMate import TeslaMateBacked

    cfg = load_config()
    url = cfg.teslaMate.database_url
    if not url:
        console.print(f"[red]{i18n_t('teslaMate.not_configured')}[/red]")
        console.print("  [dim]Managed stack: tesla teslaMate install[/dim]")
        raise typer.Exit(1)
    # Warn if managed stack is installed but not running
    if cfg.teslaMate.managed:
        from pathlib import Path

        from tesla_cli.infra.teslamate_stack import TeslaMateStack

        stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
        if stack.is_installed() and not stack.is_running():
            console.print(
                "[yellow]TeslaMate stack is installed but not running.[/yellow]\n"
                "Start it with: [bold]tesla teslaMate start[/bold]\n"
            )
    return TeslaMateBacked(url, car_id=cfg.teslaMate.car_id)


# Submodules register their commands; names are re-exported for importers.
from tesla_cli.cli.commands.teslaMate._analytics import (  # noqa: E402
    _build_geojson,
    _build_gpx,
    _kv,
    teslaMate_battery_degradation,
    teslaMate_charging,
    teslaMate_charging_locations,
    teslaMate_cost_report,
    teslaMate_daily_chart,
    teslaMate_energy_report,
    teslaMate_graph,
    teslaMate_monthly_cost,
    teslaMate_report,
    teslaMate_stats,
    teslaMate_updates,
)
from tesla_cli.cli.commands.teslaMate._stack import (  # noqa: E402
    _GRAFANA_DASHBOARDS,
    _GRAFANA_NAMES,
    _TESLAFI_COL_MAP,
    _TESLAFI_REQUIRED_COLS,
    _detect_format,
    _insert_teslafi_rows,
    _parse_generic_csv,
    _parse_teslafi_csv,
    _parse_teslamate_json,
    _preview_rows,
    teslaMate_connect,
    teslaMate_doctor,
    teslaMate_grafana,
    teslamate_import,
    teslaMate_install,
    teslaMate_logs,
    teslaMate_restart,
    teslaMate_start,
    teslaMate_status,
    teslaMate_stop,
    teslaMate_sync_tokens,
    teslaMate_uninstall,
    teslaMate_update,
)
from tesla_cli.cli.commands.teslaMate._trips import (  # noqa: E402
    teslaMate_drive_path,
    teslaMate_efficiency,
    teslaMate_geo,
    teslaMate_heatmap,
    teslaMate_timeline,
    teslaMate_trip_stats,
    teslaMate_trips,
    teslaMate_vampire,
)
