"""Vehicle commands: tesla vehicle info/location/charge/climate/lock/unlock/...

Package layout: shared helpers live here; commands are in ``_info`` (queries),
``_control`` (actions) and ``_monitor`` (live views). Imports below are also
consumed by those submodules and by callers/tests that patch
``tesla_cli.cli.commands.vehicle.<name>`` — keep them here.
"""

# ruff: noqa: F401

from __future__ import annotations

import logging
import time

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from tesla_cli.cli.output import (
    console,
    is_json_mode,
    render_dict,
    render_model,
    render_success,
    render_table,
)
from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.exceptions import VehicleAsleepError
from tesla_cli.core.models.charge import ChargeState
from tesla_cli.core.models.climate import ClimateState
from tesla_cli.core.models.drive import Location

vehicle_app = typer.Typer(name="vehicle", help="Tesla vehicle data and control.")

# Common VIN option
VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias (uses default if omitted)")


def _backend():
    return get_vehicle_backend(load_config())


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


def _with_wake(fn, vin: str, retries: int = 2):
    """Execute fn, auto-waking the vehicle if asleep."""
    backend = _backend()
    for attempt in range(retries + 1):
        try:
            return fn(backend, vin)
        except VehicleAsleepError:
            if attempt == retries:
                raise
            console.print("[yellow]Vehicle asleep, waking up...[/yellow]")
            backend.wake_up(vin)
            time.sleep(5)


# Commands live in themed submodules; importing them registers them on
# vehicle_app. Everything is re-exported so existing imports keep working.
from tesla_cli.cli.commands.vehicle._control import (  # noqa: E402,F401
    _CABIN_LEVEL_MAP,
    vehicle_bio,
    vehicle_cabin_protection,
    vehicle_charge,
    vehicle_charge_port,
    vehicle_climate,
    vehicle_dashcam,
    vehicle_flash,
    vehicle_homelink,
    vehicle_horn,
    vehicle_invitations,
    vehicle_invite,
    vehicle_lock,
    vehicle_precondition,
    vehicle_rename,
    vehicle_revoke_invite,
    vehicle_schedule_charge,
    vehicle_schedule_update,
    vehicle_screenshot,
    vehicle_sentry,
    vehicle_speed_limit,
    vehicle_sw_update,
    vehicle_tonneau,
    vehicle_trunk,
    vehicle_unlock,
    vehicle_valet,
    vehicle_wake,
    vehicle_windows,
)
from tesla_cli.cli.commands.vehicle._info import (  # noqa: E402,F401
    _fmt_temp,
    fleet_status,
    vehicle_alerts,
    vehicle_battery_health,
    vehicle_consumption,
    vehicle_export,
    vehicle_firmware_alerts,
    vehicle_info,
    vehicle_last_seen,
    vehicle_list,
    vehicle_location,
    vehicle_map,
    vehicle_nearby,
    vehicle_option_codes,
    vehicle_profile,
    vehicle_release_notes,
    vehicle_safety_score,
    vehicle_sentry_events,
    vehicle_software,
    vehicle_status_line,
    vehicle_summary,
    vehicle_tires,
    vehicle_vin,
    vehicle_weather,
)
from tesla_cli.cli.commands.vehicle._monitor import (  # noqa: E402,F401
    _WATCH_KEYS,
    _format_watch_change,
    vehicle_dashboard,
    vehicle_health_check,
    vehicle_ready,
    vehicle_stream,
    vehicle_stream_live,
    vehicle_trips,
    vehicle_watch,
)
