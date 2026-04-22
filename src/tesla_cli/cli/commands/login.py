"""tesla login — One-command onboarding.

Authenticates with Tesla via OAuth, then auto-discovers everything:
VIN, reservation number, cédula, placa — all from your Tesla account.
No manual configuration needed.
"""

from __future__ import annotations

import logging
import threading

import typer
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from tesla_cli.cli.output import console
from tesla_cli.core.auth import tokens
from tesla_cli.core.config import load_config, save_config
from tesla_cli.core.exceptions import AuthenticationError

log = logging.getLogger("tesla-cli.login")


def login(
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-authenticate even if already logged in"
    ),
) -> None:
    """Log in to your Tesla account. Auto-discovers VIN, order, and vehicle data."""
    cfg = load_config()
    already_authed = tokens.has_token(tokens.ORDER_REFRESH_TOKEN)

    if already_authed and not force:
        console.print(
            Panel.fit(
                f"[green]Already logged in.[/green]\n"
                f"  VIN: [bold]{cfg.general.default_vin or '(not yet assigned)'}[/bold]\n"
                f"  Order: [bold]{cfg.order.reservation_number or '(none)'}[/bold]\n\n"
                "[dim]Run [bold]tesla login --force[/bold] to re-authenticate.[/dim]",
                border_style="green",
            )
        )
        return

    # ── Step 1: OAuth ────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Tesla CLI — Login[/bold cyan]\n\n"
            "Your browser will open to authenticate with Tesla.\n"
            "After logging in, Tesla redirects you to a blank page.\n"
            "[bold yellow]Copy the full URL[/bold yellow] from that page and paste it here.",
            border_style="cyan",
        )
    )
    console.print()

    try:
        from tesla_cli.core.auth.oauth import run_tesla_oauth_flow

        token_data = run_tesla_oauth_flow()
        tokens.set_token(tokens.ORDER_ACCESS_TOKEN, token_data["access_token"])
        tokens.set_token(tokens.ORDER_REFRESH_TOKEN, token_data["refresh_token"])
        console.print("[green]✓ Authenticated with Tesla.[/green]\n")
    except AuthenticationError as e:
        console.print(f"[red]Authentication error:[/red] {e}")
        raise typer.Exit(1)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    # ── Step 2: Auto-discover orders → VIN + RN ─────────────────────────────
    discovered: dict[str, str] = {}

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
    ) as p:
        p.add_task("Looking up your Tesla orders...", total=None)
        discovered.update(_discover_orders())

    cfg = load_config()
    if discovered.get("vin"):
        cfg.general.default_vin = discovered["vin"]
        console.print(f"[green]✓ VIN:[/green] [bold]{discovered['vin']}[/bold]")
    if discovered.get("rn"):
        cfg.order.reservation_number = discovered["rn"]
        console.print(f"[green]✓ Order:[/green] [bold]{discovered['rn']}[/bold]")
    if discovered.get("model"):
        console.print(f"[green]✓ Model:[/green] [bold]{discovered['model']}[/bold]")

    # ── Step 3: RUNT → cédula + placa ────────────────────────────────────────
    if discovered.get("vin"):
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
        ) as p:
            p.add_task("Querying RUNT with your VIN...", total=None)
            runt = _discover_runt(discovered["vin"])

        if runt.get("cedula"):
            cfg.general.cedula = runt["cedula"]
            discovered["cedula"] = runt["cedula"]
            console.print(f"[green]✓ Owner ID (cédula):[/green] [bold]{runt['cedula']}[/bold]")
        if runt.get("placa"):
            discovered["placa"] = runt["placa"]
            console.print(f"[green]✓ License plate:[/green] [bold]{runt['placa']}[/bold]")
        if runt.get("estado"):
            console.print(f"[green]✓ RUNT status:[/green] [bold]{runt['estado']}[/bold]")
        if not runt:
            console.print("[dim]  RUNT: vehicle not yet registered in Colombia.[/dim]")

    save_config(cfg)

    # ── Step 4: Refresh available sources ─────────────────────────────────────
    console.print()
    refreshed = []
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
    ) as p:
        p.add_task("Refreshing data sources...", total=None)
        refreshed = _refresh_available_sources()

    if refreshed:
        console.print(
            f"[green]✓ {len(refreshed)} source(s) refreshed:[/green] {', '.join(refreshed)}"
        )

    # ── Summary ──────────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel.fit(
            "[bold green]Login complete.[/bold green]\n\n"
            + (
                f"  VIN:    [bold]{discovered.get('vin', '—')}[/bold]\n"
                if discovered.get("vin")
                else ""
            )
            + (
                f"  Plate:  [bold]{discovered.get('placa', '—')}[/bold]\n"
                if discovered.get("placa")
                else ""
            )
            + (
                f"  Cédula: [bold]{discovered.get('cedula', '—')}[/bold]\n"
                if discovered.get("cedula")
                else ""
            )
            + (
                f"  Order:  [bold]{discovered.get('rn', '—')}[/bold]\n"
                if discovered.get("rn")
                else ""
            )
            + "\nTry:\n"
            "  [bold]tesla order status[/bold]    — your order status\n"
            "  [bold]tesla vehicle status[/bold]  — vehicle status\n"
            "  [bold]tesla data sources[/bold]    — all data sources",
            border_style="green",
        )
    )


# ── Discovery helpers ────────────────────────────────────────────────────────


def _discover_orders() -> dict[str, str]:
    """Fetch orders from Tesla API and extract VIN + RN."""
    result: dict[str, str] = {}
    try:
        from tesla_cli.core.backends.order import OrderBackend

        _orders: list = []
        _error: list[Exception] = []

        def _fetch():
            try:
                _orders.extend(OrderBackend().get_orders())
            except Exception as exc:
                _error.append(exc)

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()
        t.join(timeout=30)

        if _error:
            log.debug("Order discovery failed: %s", _error[0])
            return result

        orders = _orders
        if not orders:
            return result

        # Pick first order (or the one with a VIN)
        order = next((o for o in orders if o.get("vin")), orders[0])
        result["rn"] = order.get("referenceNumber", order.get("rn", ""))
        result["vin"] = order.get("vin", "")
        result["model"] = order.get("model", order.get("modelCode", ""))
        result["status"] = order.get("orderStatus", "")
    except Exception as exc:
        log.debug("Order discovery error: %s", exc)
    return result


def _discover_runt(vin: str) -> dict[str, str]:
    """Query RUNT with VIN to discover cédula and placa."""
    result: dict[str, str] = {}
    try:
        from tesla_cli.core.backends.runt import RuntBackend

        backend = RuntBackend(timeout=45)
        data = backend.query_by_vin(vin)
        d = data.model_dump() if hasattr(data, "model_dump") else {}

        if d.get("no_identificacion"):
            result["cedula"] = str(d["no_identificacion"])
        if d.get("placa"):
            result["placa"] = str(d["placa"])
        if d.get("estado"):
            result["estado"] = str(d["estado"])
    except Exception as exc:
        log.debug("RUNT discovery failed: %s", exc)
    return result


def _refresh_available_sources() -> list[str]:
    """Refresh stale sources that have their requirements met."""
    refreshed: list[str] = []
    try:
        from tesla_cli.core.sources import _SOURCES, _is_stale, refresh_source

        for sid in _SOURCES:
            if _is_stale(sid):
                r = refresh_source(sid)
                if not r.get("error"):
                    refreshed.append(sid)
    except Exception as exc:
        log.debug("Source refresh failed: %s", exc)
    return refreshed
