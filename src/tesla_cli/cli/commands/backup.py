"""tesla backup — full backup / restore of the tesla-cli data directory."""

from __future__ import annotations

import json

import typer

from tesla_cli.cli.output import console, is_json_mode, render_success
from tesla_cli.core.exceptions import ConfigurationError

backup_app = typer.Typer(name="backup", help="Back up and restore all tesla-cli data.")


@backup_app.command("create")
def backup_create(
    output: str | None = typer.Option(
        None, "--output", "-o", help="Archive path (default: ~/.tesla-cli/backups/…tar.gz)"
    ),
    no_secrets: bool = typer.Option(
        False,
        "--no-secrets",
        help="Drop tokens, keys and the master key; redact config.toml (shareable)",
    ),
) -> None:
    """Archive config, encrypted tokens, events, dossier and caches (mode 0600).

    \b
    tesla backup create
    tesla backup create -o /mnt/nas/tesla-cli.tar.gz
    tesla backup create --no-secrets      # for sharing with support

    Backups contain personal data (VIN, reservation) and, by default,
    credentials. They are never written inside a git repository.
    """
    from tesla_cli.core.backup import create_backup

    try:
        path, manifest = create_backup(output, include_secrets=not no_secrets)
    except ConfigurationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    if is_json_mode():
        console.print(json.dumps({"path": str(path), **manifest}), soft_wrap=True, markup=False)
        return
    note = "secrets included — store it like a password" if not no_secrets else "no secrets"
    render_success(f"Backup written to {path} ({len(manifest['files'])} files, {note})")


@backup_app.command("restore")
def backup_restore(
    archive: str = typer.Argument(..., help="Backup archive (.tar.gz) to restore"),
    force: bool = typer.Option(False, "--force", help="Do not ask for confirmation"),
) -> None:
    """Restore a backup into ~/.tesla-cli (current data is saved first).

    \b
    tesla backup restore ~/.tesla-cli/backups/tesla-cli-backup-20261104-120000.tar.gz
    """
    from tesla_cli.core.backup import read_manifest, restore_backup

    try:
        manifest = read_manifest(archive)
    except (ConfigurationError, OSError, ValueError) as exc:
        console.print(f"[red]Cannot restore: {exc}[/red]")
        raise typer.Exit(1) from exc
    if not force and not typer.confirm(
        f"Restore {len(manifest.get('files', []))} files from a backup made on "
        f"{manifest.get('created', '?')[:19]} (tesla-cli {manifest.get('tesla_cli_version')})? "
        "Existing files are overwritten (a safety backup is taken first)."
    ):
        console.print("[dim]Restore cancelled.[/dim]")
        raise typer.Exit(0)
    restored, safety = restore_backup(archive)
    if safety:
        console.print(f"[dim]Previous data saved to {safety}[/dim]")
    render_success(f"Restored {len(restored)} files")
    if not manifest.get("include_secrets", True):
        console.print(
            "[yellow]This backup had no secrets: re-authenticate with "
            "`tesla config auth` and recreate API keys with `tesla serve api-key --rotate`.[/yellow]"
        )


@backup_app.command("list")
def backup_list() -> None:
    """List backups in ~/.tesla-cli/backups/."""
    from tesla_cli.core.backup import list_backups

    items = list_backups()
    if is_json_mode():
        console.print(
            json.dumps([{"path": str(p), "bytes": p.stat().st_size} for p in items]),
            soft_wrap=True,
            markup=False,
        )
        return
    if not items:
        console.print("[dim]No backups yet. Create one with: tesla backup create[/dim]")
        return
    for p in items:
        console.print(f"  {p.name}  [dim]{p.stat().st_size / 1024:.0f} KB[/dim]")
