"""`tesla doctor` — per-feature health report.

Prints a Rich table (default) or JSON (`--json`) describing the status of
every feature in `core/health/features.py`. Also performs a one-time v4.9.1
migration hook: on first invocation, purge stale fixture events produced
by pre-release test runs.

Exit code is always 0; CI consumers should parse the JSON status field.
"""

from __future__ import annotations

import json as _json

import typer

from tesla_cli.cli.output import console, error_console
from tesla_cli.core.config import load_config, save_config
from tesla_cli.core.health.features import probe_all

doctor_app = typer.Typer(
    help="Feature health report — show which features are live on this install.",
    invoke_without_command=True,
)


_STATUS_STYLES = {
    "ok": ("green", "ok"),
    "missing-scope": ("yellow", "missing-scope"),
    "external-blocker": ("red", "external-blocker"),
    "not-configured": ("yellow", "not-configured"),
}


def _run_migration_if_needed(*, quiet_stdout: bool = False) -> None:
    """v4.9.1 one-time events-purge migration (see plan §3.1 / §3.1 T1.2).

    Silently noop if Lane C hasn't landed `run_v491_purge_migration` yet.
    When `quiet_stdout` is set (e.g. `--json` mode), status lines are routed to
    stderr so stdout stays a valid JSON document.
    """
    cfg = load_config()
    if getattr(cfg.general, "v491_events_purge_done", False):
        return
    try:
        from tesla_cli.cli.commands.events import (  # type: ignore[attr-defined]
            run_v491_purge_migration,
        )
    except (ImportError, AttributeError):
        return  # Lane C may not have landed yet
    out = error_console if quiet_stdout else console
    try:
        count = run_v491_purge_migration()
        out.print(f"[dim]Deleted {count} events.[/dim]")
        cfg.general.v491_events_purge_done = True
        save_config(cfg)
    except Exception as exc:  # noqa: BLE001 — migration must never crash doctor
        out.print(f"[yellow]Migration warning:[/yellow] {exc}")


def doctor(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
) -> None:
    """Show per-feature health status (offline-safe, never wakes the car)."""
    rows = probe_all()

    if json_output:
        typer.echo(_json.dumps(rows))
        _run_migration_if_needed(quiet_stdout=True)
        raise typer.Exit(code=0)

    from rich.table import Table

    table = Table(title="Feature Health", show_lines=False)
    table.add_column("Feature", style="cyan", no_wrap=True)
    table.add_column("Tier", style="magenta", no_wrap=True)
    table.add_column("Status")
    table.add_column("Remediation", overflow="fold")

    for row in rows:
        color, label = _STATUS_STYLES.get(row["status"], ("white", row["status"]))
        table.add_row(
            row["name"],
            row["tier"],
            f"[{color}]{label}[/{color}]",
            row.get("remediation", ""),
        )

    console.print(table)
    _run_migration_if_needed()
    raise typer.Exit(code=0)


@doctor_app.callback(invoke_without_command=True)
def _doctor_callback(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
) -> None:
    if ctx.invoked_subcommand is None:
        doctor(json_output=json_output)
