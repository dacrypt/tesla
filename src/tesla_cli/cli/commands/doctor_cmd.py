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

    Skipped entirely under pytest — otherwise running `tesla doctor` inside
    a test would wipe the shared events store and leak a stderr line into
    click.testing.CliRunner's combined output (breaks JSON-decoding tests
    and `test_source_refresh_emits_events_and_alerts`).
    """
    import sys

    if "pytest" in sys.modules:
        return
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


def _check_vin_reachable() -> tuple[bool, str]:
    """Verify that `general.default_vin` matches a VIN on the current Fleet
    account. Returns (ok, human_readable_detail).

    Catches a real class of bug: test pollution / fat-finger editing of the
    config file that leaves `default_vin` pointing at a sample VIN Tesla
    doesn't recognise (e.g. `5YJ3E1EA1PF000001`). Every signed command
    then 404s silently and the user spends hours wondering why pairing
    "broke" when in fact the VIN is wrong.

    One cheap Fleet API call (`list_vehicles`); never wakes the car.
    """
    try:
        cfg = load_config()
    except Exception as exc:
        return False, f"cannot load config: {exc}"
    vin = (cfg.general.default_vin or "").strip()
    if not vin:
        return False, "default_vin is empty — set with: tesla config set default-vin <VIN>"
    try:
        from tesla_cli.core.backends import get_vehicle_backend

        vehicles = get_vehicle_backend(cfg).list_vehicles()
    except Exception as exc:
        return False, f"could not list vehicles: {exc}"
    account_vins = [v.get("vin") for v in vehicles]
    if vin in account_vins:
        return True, f"{vin} (present on account)"
    return False, (
        f"{vin} is NOT on this account. Known VINs: {account_vins}. "
        f"Fix: tesla config set default-vin <one-of-those>"
    )


def doctor(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
    check_vin: bool = typer.Option(
        False,
        "--check-vin",
        help="Also verify `default_vin` matches a VIN on the Fleet account (1 API call).",
    ),
) -> None:
    """Show per-feature health status (offline-safe, never wakes the car)."""
    rows = probe_all()

    if check_vin:
        ok, detail = _check_vin_reachable()
        rows.append(
            {
                "name": "default_vin_reachable",
                "tier": "T0",
                "status": "ok" if ok else "external-blocker",
                **({"remediation": detail} if not ok else {}),
            }
        )

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
    check_vin: bool = typer.Option(
        False,
        "--check-vin",
        help="Also verify `default_vin` matches a VIN on the Fleet account (1 API call).",
    ),
) -> None:
    if ctx.invoked_subcommand is None:
        doctor(json_output=json_output, check_vin=check_vin)
