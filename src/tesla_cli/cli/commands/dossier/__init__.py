"""Dossier implementation functions.

These functions contain the core logic for vehicle intelligence features.
They are called from their canonical CLI homes: order, vehicle, data.
No CLI commands are registered here — this is an internal module.
"""

# Package layout: shared imports/helpers live here; code is split into _show, _export, _tools.
# Submodules look up names that tests patch on tesla_cli.cli.commands.dossier through this package.
# ruff: noqa: F401, I001

from __future__ import annotations

import json

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tesla_cli.cli.output import console, is_json_mode
from tesla_cli.core.backends.dossier import DossierBackend
from tesla_cli.core.mission_control import build_legacy_mission_control_payload


# Submodules register their commands; names are re-exported for importers.
from tesla_cli.cli.commands.dossier._show import (  # noqa: E402
    _build_cli_mission_control_payload,
    _render_account,
    _render_delivery,
    _render_epa,
    _render_logistics,
    _render_meta,
    _render_monitor,
    _render_nhtsa,
    _render_option_codes,
    _render_order,
    _render_recalls,
    _render_runt,
    _render_simit,
    _render_sources,
    _render_specs,
    _render_status,
    _render_summary_dashboard,
    _render_tesla_tasks,
    _render_vin_decode,
    dossier_build,
    dossier_show,
)
from tesla_cli.cli.commands.dossier._export import (  # noqa: E402
    dossier_export_html,
    dossier_export_pdf,
)
from tesla_cli.cli.commands.dossier._tools import (  # noqa: E402
    _compute_diff,
    _kv_table,
    _section,
    dossier_battery_health,
    dossier_checklist,
    dossier_clean,
    dossier_diff,
    dossier_estimate,
    dossier_gates,
    dossier_history,
    dossier_option_codes,
    dossier_set_delivery,
    dossier_ships,
    dossier_sources,
    dossier_vin,
)
