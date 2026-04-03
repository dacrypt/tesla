"""tesla setup — Interactive onboarding wizard.

Guides the user from zero to a fully configured CLI with their first data built:
  1. Tesla account auth (OAuth2 + PKCE)
  2. Auto-discover VIN and reservation number from the API
  3. Optionally configure a vehicle control backend (Tessie / Fleet API)
  4. Build the first data build (cross all data sources)
"""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

from tesla_cli.cli.output import console
from tesla_cli.core.auth import tokens
from tesla_cli.core.config import load_config, save_config
from tesla_cli.core.exceptions import AuthenticationError, TeslaCliError


def setup_wizard(
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-run all steps even if already configured"
    ),
    skip_build: bool = typer.Option(False, "--skip-build", help="Skip the final data build"),
) -> None:
    """Interactive onboarding wizard. Connects your Tesla account and builds your first data build."""
    # ── Welcome ────────────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Tesla CLI — Setup Wizard[/bold cyan]\n\n"
            "This wizard will:\n"
            "  [dim]1.[/dim] Connect your Tesla account (OAuth2)\n"
            "  [dim]2.[/dim] Auto-discover your VIN and order number\n"
            "  [dim]3.[/dim] Optionally configure live vehicle control\n"
            "  [dim]4.[/dim] Build your first data build from all sources\n\n"
            "[dim]Run [bold]tesla setup --force[/bold] to re-run all steps at any time.[/dim]",
            border_style="cyan",
        )
    )
    console.print()

    # ── Check existing state ────────────────────────────────────────────────────
    cfg = load_config()
    already_authed = tokens.has_token(tokens.ORDER_REFRESH_TOKEN)
    has_vin = bool(cfg.general.default_vin)
    has_rn = bool(cfg.order.reservation_number)

    if already_authed and has_vin and has_rn and not force:
        console.print("[green]✓ Already configured:[/green]")
        console.print(f"  VIN: [bold]{cfg.general.default_vin}[/bold]")
        console.print(f"  Order: [bold]{cfg.order.reservation_number}[/bold]")
        console.print()
        answer = Prompt.ask("Re-run setup?", choices=["y", "n"], default="n")
        if answer == "n":
            console.print(
                "[dim]Nothing changed. Run [bold]tesla vehicle profile[/bold] to see your dossier.[/dim]"
            )
            raise typer.Exit()
        console.print()

    # ── Step 1: Auth ────────────────────────────────────────────────────────────
    console.print(
        Panel.fit("[bold]Step 1 / 4[/bold] — Tesla Account Authentication", border_style="blue")
    )
    console.print()

    if already_authed and not force:
        console.print("[green]✓ Already authenticated — skipping.[/green]")
    else:
        try:
            from tesla_cli.cli.commands.config_cmd import _auth_order

            _auth_order()
        except AuthenticationError as e:
            console.print(f"\n[red]Authentication failed:[/red] {e}")
            console.print("[dim]Run [bold]tesla config auth order[/bold] to retry.[/dim]")
            raise typer.Exit(1)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Setup cancelled.[/yellow]")
            raise typer.Exit()

    console.print()

    # ── Step 2: Auto-discover VIN + RN ─────────────────────────────────────────
    console.print(
        Panel.fit("[bold]Step 2 / 4[/bold] — Discovering your order", border_style="blue")
    )
    console.print()

    orders = []
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
    ) as p:
        p.add_task("Fetching orders from Tesla API...", total=None)
        try:
            import httpx

            from tesla_cli.core.backends.order import OrderBackend

            orders = OrderBackend().get_orders()
        except AuthenticationError as e:
            console.print(f"[red]Auth error:[/red] {e}")
            raise typer.Exit(1)
        except httpx.TimeoutException:
            console.print("[yellow]Request timed out.[/yellow]")
        except TeslaCliError as e:
            console.print(f"[yellow]Could not fetch orders:[/yellow] {e}")

    selected_vin = ""
    selected_rn = ""

    if not orders:
        # Fallback to manual entry
        console.print("[yellow]No orders found — enter your details manually:[/yellow]")
        selected_vin = Prompt.ask("VIN (leave blank to skip)", default="")
        selected_rn = Prompt.ask("Reservation number (e.g. RNXXXXXXXXX)", default="")
    elif len(orders) == 1:
        order = orders[0]
        selected_rn = order.get("referenceNumber", order.get("rn", ""))
        selected_vin = order.get("vin", "")
        model = order.get("model", order.get("modelCode", "Tesla"))
        status = order.get("orderStatus", "")
        console.print(
            f"[green]✓ Found order:[/green] [bold]{selected_rn}[/bold]  {model}  [{status}]"
        )
        if not selected_vin:
            console.print(
                "  [yellow]VIN not yet assigned by Tesla — will be auto-updated on next data build.[/yellow]"
            )
    else:
        # Multiple orders — let user pick
        console.print(f"Found [bold]{len(orders)}[/bold] orders on your account:\n")
        for i, order in enumerate(orders, 1):
            rn = order.get("referenceNumber", order.get("rn", "—"))
            model = order.get("model", order.get("modelCode", "Tesla"))
            status = order.get("orderStatus", "—")
            vin = order.get("vin", "(no VIN yet)")
            console.print(f"  [bold]{i}.[/bold]  {rn}  {model}  [{status}]  {vin}")
        console.print()
        choices = [str(i) for i in range(1, len(orders) + 1)]
        pick = Prompt.ask("Select order", choices=choices, default="1")
        order = orders[int(pick) - 1]
        selected_rn = order.get("referenceNumber", order.get("rn", ""))
        selected_vin = order.get("vin", "")
        if not selected_vin:
            console.print(
                "  [yellow]VIN not yet assigned by Tesla — will be auto-updated later.[/yellow]"
            )

    # Save discovered values
    cfg = load_config()
    changed = False
    if selected_vin and (not cfg.general.default_vin or force):
        cfg.general.default_vin = selected_vin
        changed = True
        console.print(f"[green]✓ VIN set:[/green] {selected_vin}")
    if selected_rn and (not cfg.order.reservation_number or force):
        cfg.order.reservation_number = selected_rn
        changed = True
        console.print(f"[green]✓ Reservation number set:[/green] {selected_rn}")
    if changed:
        save_config(cfg)
    elif has_vin and has_rn:
        console.print(
            f"[dim]Keeping existing config — VIN: {cfg.general.default_vin}  Order: {cfg.order.reservation_number}[/dim]"
        )

    console.print()

    # ── Step 3: Vehicle control ─────────────────────────────────────────────────
    console.print(
        Panel.fit(
            "[bold]Step 3 / 4[/bold] — Vehicle Control\n\n"
            "  [bold green]owner[/bold green]   Free — uses your existing Tesla account token (recommended)\n"
            "  [dim]tessie  Paid proxy service (tessie.com, ~$10/month)[/dim]\n"
            "  [dim]fleet   Tesla developer API (requires app registration)[/dim]",
            border_style="blue",
        )
    )
    console.print()

    cfg = load_config()
    already_owner = cfg.general.backend == "owner" and tokens.has_token(tokens.ORDER_REFRESH_TOKEN)
    tessie_ok = tokens.has_token(tokens.TESSIE_TOKEN)
    fleet_ok = tokens.has_token(tokens.FLEET_ACCESS_TOKEN)

    if (already_owner or tessie_ok or fleet_ok) and not force:
        backend_name = (
            cfg.general.backend if already_owner else ("tessie" if tessie_ok else "fleet")
        )
        console.print(
            f"[green]✓ Vehicle backend already configured ({backend_name}) — skipping.[/green]"
        )
    else:
        choice = Prompt.ask(
            "Vehicle backend",
            choices=["owner", "tessie", "fleet", "skip"],
            default="owner",
        )
        if choice == "owner":
            # Owner API uses the order tracking token — already set up in Step 1
            cfg.general.backend = "owner"
            save_config(cfg)
            console.print(
                "[green]✓ Vehicle backend set to 'owner' — no extra setup needed.[/green]"
            )
        elif choice == "tessie":
            try:
                from tesla_cli.cli.commands.config_cmd import _auth_tessie

                _auth_tessie()
            except (TeslaCliError, KeyboardInterrupt, EOFError):
                console.print(
                    "[yellow]Skipping — configure later with[/yellow] [bold]tesla config auth tessie[/bold]"
                )
        elif choice == "fleet":
            try:
                from tesla_cli.cli.commands.config_cmd import _auth_fleet

                _auth_fleet()
            except (TeslaCliError, KeyboardInterrupt, EOFError):
                console.print(
                    "[yellow]Skipping — configure later with[/yellow] [bold]tesla config auth fleet[/bold]"
                )
        else:
            console.print(
                "[dim]Skipped — run [bold]tesla config set backend owner[/bold] when ready.[/dim]"
            )

    console.print()

    # ── Step 4: Build dossier ───────────────────────────────────────────────────
    if skip_build:
        console.print("[dim]Skipping data build (--skip-build).[/dim]")
    else:
        console.print(
            Panel.fit("[bold]Step 4 / 4[/bold] — Building your vehicle data", border_style="blue")
        )
        console.print("[dim]Pulling from Tesla API, NHTSA, RUNT, ship tracking...[/dim]\n")

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as p:
                p.add_task("Querying all data sources...", total=None)
                from tesla_cli.core.backends.dossier import DossierBackend

                DossierBackend().build_dossier()

            console.print("[green]✓ Dossier built successfully.[/green]\n")

            # Show the dossier
            from tesla_cli.cli.commands.dossier import dossier_show

            dossier_show()

        except AuthenticationError as e:
            console.print(f"[red]Auth error during data build:[/red] {e}")
            console.print("[dim]Run [bold]tesla data build[/bold] after fixing auth.[/dim]")
        except TeslaCliError as e:
            console.print(f"[yellow]Dossier partially built:[/yellow] {e}")
            console.print(
                "[dim]Run [bold]tesla vehicle profile[/bold] to see what was collected.[/dim]"
            )
        except Exception as e:
            console.print(f"[yellow]Dossier build encountered an error:[/yellow] {e}")
            console.print("[dim]Run [bold]tesla data build[/bold] to retry.[/dim]")

    # ── Done ────────────────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel.fit(
            "[bold green]✓ Setup complete![/bold green]\n\n"
            "Next steps:\n"
            "  [bold]tesla config doctor[/bold]        — validate all connections\n"
            "  [bold]tesla vehicle ready[/bold]        — check if your car is ready to drive\n"
            "  [bold]tesla vehicle summary[/bold]      — compact vehicle status\n\n"
            "Daily commands:\n"
            "  [bold]tesla charge status[/bold]        — current charge state\n"
            "  [bold]tesla charge last[/bold]          — most recent charging session\n"
            "  [bold]tesla order status[/bold]         — check your order\n"
            "  [bold]tesla order watch -i 5[/bold]     — monitor for changes every 5 min",
            border_style="green",
        )
    )
