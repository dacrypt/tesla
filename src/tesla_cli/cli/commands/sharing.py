"""Sharing commands: tesla sharing invite|list|revoke."""

from __future__ import annotations

import typer

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.exceptions import BackendNotSupportedError
from tesla_cli.cli.output import console, render_dict, render_success, render_table

sharing_app = typer.Typer(name="sharing", help="Vehicle sharing and driver invitations.")

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")


def _backend():
    return get_vehicle_backend(load_config())


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


def _backend_check(exc: BackendNotSupportedError) -> None:
    console.print(f"[yellow]{exc}[/yellow]")
    raise typer.Exit(1)


@sharing_app.command("invite")
def sharing_invite(vin: str | None = VinOption) -> None:
    """Create a new driver invitation link."""
    v = _vin(vin)
    backend = _backend()
    try:
        data = backend.create_invitation(v)
    except BackendNotSupportedError as exc:
        _backend_check(exc)
        return
    render_dict(data, title="New Invitation")


@sharing_app.command("list")
def sharing_list(vin: str | None = VinOption) -> None:
    """List current driver invitations."""
    v = _vin(vin)
    backend = _backend()
    try:
        invitations = backend.get_invitations(v)
    except BackendNotSupportedError as exc:
        _backend_check(exc)
        return
    if not invitations:
        render_success("No active invitations")
        return
    render_table(
        invitations,
        columns=["id", "owner", "state", "created_at"],
        title="Driver Invitations",
    )


@sharing_app.command("revoke")
def sharing_revoke(
    invitation_id: str = typer.Argument(..., help="Invitation ID to revoke"),
    vin: str | None = VinOption,
) -> None:
    """Revoke a driver invitation."""
    v = _vin(vin)
    backend = _backend()
    try:
        backend.revoke_invitation(v, invitation_id)
    except BackendNotSupportedError as exc:
        _backend_check(exc)
        return
    render_success(f"Invitation {invitation_id} revoked")
