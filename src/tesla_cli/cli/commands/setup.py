"""tesla setup — Interactive onboarding wizard.

Guides the user from zero to a fully configured CLI with their first data built:
  1. Tesla account auth (OAuth2 + PKCE)
  2. Auto-discover VIN and reservation number from the API
  3. Vehicle control tier (basic / advanced / tessie)
  4. Fleet Telemetry (real-time streaming, optional — Advanced tier only, requires Docker)
  5. TeslaMate Analytics (deep logging, optional — requires Docker)
  6. Notifications (Apprise URLs, optional)
  7. Default automations (optional)
  8. Build the first data dossier (cross all data sources)
"""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt

from tesla_cli.cli.output import console
from tesla_cli.core.auth import tokens
from tesla_cli.core.config import load_config, save_config
from tesla_cli.core.exceptions import AuthenticationError, EndpointDeprecatedError, TeslaCliError


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
            "  [dim]3.[/dim] Choose your tier (Basic works immediately — no registration needed)\n"
            "  [dim]4.[/dim] Optionally install fleet-telemetry for real-time streaming (Advanced only)\n"
            "  [dim]5.[/dim] Optionally install TeslaMate for deep analytics\n"
            "  [dim]6.[/dim] Optionally set up push notifications\n"
            "  [dim]7.[/dim] Optionally configure smart automation rules\n"
            "  [dim]8.[/dim] Build your first data dossier from all sources\n\n"
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
        Panel.fit("[bold]Step 1 / 8[/bold] — Tesla Account Authentication", border_style="blue")
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
        Panel.fit("[bold]Step 2 / 8[/bold] — Discovering your order", border_style="blue")
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

    # ── Step 3: Vehicle control tier ────────────────────────────────────────────
    # Tier explanation:
    #   basic    → Owner API, uses the token from Step 1, no extra registration
    #   advanced → Fleet API (free, requires developer.tesla.com app)
    #   tessie   → Paid third-party proxy (~$12/month)
    console.print(
        Panel.fit(
            "[bold]Step 3 / 8[/bold] — Vehicle Control\n\n"
            "Tesla CLI works in three tiers. Start with Basic — upgrade later if needed.\n\n"
            "  [bold green]basic[/bold green]     Email + password only. Order tracking, vehicle data & commands.\n"
            "            No registration needed. Works immediately.\n"
            "            (Some newer VINs may need the Advanced tier)\n\n"
            "  [dim]advanced  Tesla Developer API. Required for newer vehicles (2024+),\n"
            "            signed commands, real-time telemetry, Powerwall/Solar.\n"
            "            Free — requires registering an app at developer.tesla.com[/dim]\n\n"
            "  [dim]tessie    Third-party proxy service (~$12/month).\n"
            "            Alternative if you prefer a managed service.[/dim]",
            border_style="blue",
        )
    )
    console.print()

    cfg = load_config()
    already_owner = cfg.general.backend == "owner" and tokens.has_token(tokens.ORDER_REFRESH_TOKEN)
    tessie_ok = tokens.has_token(tokens.TESSIE_TOKEN)
    fleet_ok = tokens.has_token(tokens.FLEET_ACCESS_TOKEN)

    # Track which tier was chosen — used to gate Step 4 (Fleet Telemetry)
    tier_selected = "basic"  # default

    if (already_owner or tessie_ok or fleet_ok) and not force:
        # Derive a display name for the existing configuration
        if tessie_ok:
            backend_name = "tessie"
            tier_selected = "tessie"
        elif fleet_ok:
            backend_name = cfg.general.backend  # fleet or fleet-signed
            tier_selected = "advanced"
        else:
            backend_name = "owner"
            tier_selected = "basic"
        console.print(
            f"[green]✓ Vehicle backend already configured ({backend_name}) — skipping.[/green]"
        )
    else:
        choice = Prompt.ask(
            "Choose tier",
            choices=["basic", "advanced", "tessie"],
            default="basic",
        )

        if choice == "basic":
            # Owner API token already obtained in Step 1 — nothing more to do
            cfg = load_config()
            cfg.general.backend = "owner"
            save_config(cfg)
            tier_selected = "basic"
            console.print(
                "[green]✓ Using your existing Tesla account token — no extra setup needed.[/green]"
            )

        elif choice == "advanced":
            tier_selected = "advanced"
            _show_fleet_api_guide()
            try:
                from tesla_cli.cli.commands.config_cmd import _auth_fleet

                _auth_fleet()
                # Default to fleet-signed for full signed-command support
                cfg = load_config()
                cfg.general.backend = "fleet-signed"
                save_config(cfg)
                console.print(
                    "[green]✓ Backend set to 'fleet-signed' — end-to-end encrypted commands enabled.[/green]"
                )
            except (TeslaCliError, KeyboardInterrupt, EOFError):
                console.print(
                    "[yellow]Skipping — configure later with[/yellow] [bold]tesla config auth fleet[/bold]"
                )
                # Fall back to basic so Step 4 is correctly gated
                tier_selected = "basic"

        else:  # tessie
            tier_selected = "tessie"
            try:
                from tesla_cli.cli.commands.config_cmd import _auth_tessie

                _auth_tessie()
            except (TeslaCliError, KeyboardInterrupt, EOFError):
                console.print(
                    "[yellow]Skipping — configure later with[/yellow] [bold]tesla config auth tessie[/bold]"
                )
                tier_selected = "basic"

    console.print()

    # ── Auto-detect 412 / Owner API blocked ────────────────────────────────────
    # If the user chose basic (Owner API), do a quick probe to see if their VIN
    # is blocked and offer to upgrade to Advanced right now.
    cfg = load_config()
    if tier_selected == "basic" and cfg.general.default_vin:
        tier_selected = _check_owner_api_and_maybe_upgrade(cfg, tier_selected, force)
        console.print()

    # ── Step 4: Fleet Telemetry ─────────────────────────────────────────────────
    # Fleet Telemetry is only meaningful with the Advanced tier (Fleet API).
    # Skip it with an informative message for Basic/Tessie users.
    console.print(
        Panel.fit(
            "[bold]Step 4 / 8[/bold] — Fleet Telemetry [dim](real-time streaming)[/dim]\n\n"
            "Fleet Telemetry streams live data directly from your vehicle — speed,\n"
            "location, battery state — without polling the Tesla API.\n\n"
            "[dim]Requires: Advanced tier + Docker + a publicly reachable hostname[/dim]",
            border_style="blue",
        )
    )
    console.print()

    if tier_selected != "advanced":
        # Not on Fleet API — telemetry is unavailable
        console.print(
            "[dim]Fleet Telemetry requires the Advanced tier — skipping.[/dim]\n"
            "[dim]Upgrade anytime with: tesla config auth fleet[/dim]"
        )
    else:
        # Check Docker availability first
        docker_available = _check_docker_available()

        if not docker_available:
            console.print(
                "[yellow]Docker not found — skipping fleet-telemetry.[/yellow]\n"
                "[dim]Install Docker (https://docs.docker.com/get-docker/) then run:[/dim]\n"
                "[dim]  tesla telemetry install[/dim]"
            )
        else:
            # Check if already installed
            try:
                from tesla_cli.infra.fleet_telemetry_stack import FleetTelemetryStack

                ft_stack = FleetTelemetryStack()
                if ft_stack.is_installed() and not force:
                    running = ft_stack.is_running()
                    status_str = "[green]running[/green]" if running else "[yellow]stopped[/yellow]"
                    console.print(
                        f"[green]✓ Fleet-telemetry already installed[/green] — {status_str}"
                    )
                    if not running:
                        console.print("[dim]Start it with: tesla telemetry start[/dim]")
                else:
                    install_ft = Confirm.ask(
                        "Install fleet-telemetry for real-time vehicle streaming?", default=False
                    )
                    if install_ft:
                        _run_fleet_telemetry_install(ft_stack)
                    else:
                        console.print(
                            "[dim]Skipped — install later with: tesla telemetry install[/dim]"
                        )
            except Exception as e:
                console.print(f"[yellow]Fleet-telemetry setup skipped:[/yellow] {e}")

    console.print()

    # ── Step 5: TeslaMate ───────────────────────────────────────────────────────
    # TeslaMate works with any tier — always offered.
    console.print(
        Panel.fit(
            "[bold]Step 5 / 8[/bold] — TeslaMate Analytics [dim](optional)[/dim]\n\n"
            "TeslaMate logs every drive, charge, and sleep — giving you beautiful\n"
            "Grafana dashboards with historical efficiency, range, and cost data.\n\n"
            "[dim]Requires: Docker[/dim]",
            border_style="blue",
        )
    )
    console.print()

    docker_available = _check_docker_available()

    if not docker_available:
        console.print(
            "[yellow]Docker not found — skipping TeslaMate.[/yellow]\n"
            "[dim]Install Docker then run: tesla teslaMate install[/dim]"
        )
    else:
        try:
            from tesla_cli.infra.teslamate_stack import TeslaMateStack

            tm_stack = TeslaMateStack()
            if tm_stack.is_installed() and not force:
                running = tm_stack.is_running()
                status_str = "[green]running[/green]" if running else "[yellow]stopped[/yellow]"
                console.print(
                    f"[green]✓ TeslaMate already installed[/green] — {status_str}"
                )
                if not running:
                    console.print("[dim]Start it with: tesla teslaMate start[/dim]")
            else:
                install_tm = Confirm.ask(
                    "Install TeslaMate for deep analytics and Grafana dashboards?", default=False
                )
                if install_tm:
                    _run_teslamate_install(tm_stack)
                else:
                    console.print(
                        "[dim]Skipped — install later with: tesla teslaMate install[/dim]"
                    )
        except Exception as e:
            console.print(f"[yellow]TeslaMate setup skipped:[/yellow] {e}")

    console.print()

    # ── Step 6: Notifications ───────────────────────────────────────────────────
    console.print(
        Panel.fit(
            "[bold]Step 6 / 8[/bold] — Notifications [dim](optional)[/dim]\n\n"
            "Get push notifications when your vehicle finishes charging,\n"
            "a software update is ready, or automations fire.\n\n"
            "Supported: Telegram, Discord, Slack, email, Pushover, and 80+ more\n"
            "[dim]Powered by Apprise — format: tgram://bot_token/chat_id[/dim]",
            border_style="blue",
        )
    )
    console.print()

    cfg = load_config()
    already_has_notifications = bool(cfg.notifications.apprise_urls)

    if already_has_notifications and not force:
        urls_preview = ", ".join(
            u.split("://")[0] + "://***" for u in cfg.notifications.apprise_urls
        )
        console.print(
            f"[green]✓ Notifications already configured:[/green] {urls_preview}"
        )
    else:
        setup_notif = Confirm.ask("Set up push notifications?", default=False)
        if setup_notif:
            _run_notifications_setup(cfg)
        else:
            console.print(
                "[dim]Skipped — configure later with: tesla config set notifications-enabled true[/dim]"
            )

    console.print()

    # ── Step 7: Automations ─────────────────────────────────────────────────────
    setup_automations = Confirm.ask(
        "Set up smart automation rules? These fire automatically when conditions are met.",
        default=False,
    )
    if setup_automations:
        _run_automations_setup()
    else:
        console.print(
            "[dim]Skipped — configure later with: tesla automations add[/dim]"
        )

    console.print()

    # ── Step 8: Build dossier ───────────────────────────────────────────────────
    if skip_build:
        console.print("[dim]Skipping data build (--skip-build).[/dim]")
    else:
        console.print(
            Panel.fit(
                "[bold]Step 8 / 8[/bold] — Building your vehicle data", border_style="blue"
            )
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
    _print_done_panel(tier_selected)


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _show_fleet_api_guide() -> None:
    """Print step-by-step instructions for registering a Fleet API app."""
    console.print()
    console.print(
        Panel.fit(
            "[bold]To set up Fleet API (free, ~5 minutes):[/bold]\n\n"
            "  1. Go to [cyan]https://developer.tesla.com[/cyan]\n"
            "  2. Sign in with your Tesla account\n"
            "  3. Click [bold]Create Application[/bold]\n"
            "  4. Fill in:\n"
            "       - Name: anything (e.g. [italic]my-tesla-cli[/italic])\n"
            "       - Redirect URI: [cyan]https://auth.tesla.com/void/callback[/cyan]\n"
            "       - Scopes: [dim]vehicle_device_data, vehicle_cmds, vehicle_charging_cmds[/dim]\n"
            "  5. Copy the [bold]Client ID[/bold] and [bold]Client Secret[/bold] shown",
            border_style="dim",
        )
    )
    console.print()


def _check_owner_api_and_maybe_upgrade(cfg: object, tier_selected: str, force: bool) -> str:
    """Probe the Owner API for the configured VIN.

    If the VIN receives a 412 EndpointDeprecated response, offer the user an
    in-place upgrade to the Advanced (Fleet API) tier.  Returns the final tier.
    """
    from tesla_cli.core.config import Config

    assert isinstance(cfg, Config)

    try:
        from tesla_cli.core.backends.owner import OwnerApiVehicleBackend

        backend = OwnerApiVehicleBackend()
        backend.list_vehicles()
        console.print("[green]✓ Owner API working for your vehicle.[/green]")
    except EndpointDeprecatedError:
        # Check if vehicle is pre-delivery (412 is expected before delivery)
        is_pre_delivery = False
        try:
            from tesla_cli.core.backends.order import OrderBackend

            rn = cfg.order.reservation_number
            if rn:
                status = OrderBackend().get_order_status(rn)
                order_st = (status.order_status or "").upper()
                if order_st in ("BOOKED", "PENDING", "CONFIRMED", "IN_TRANSIT"):
                    is_pre_delivery = True
        except Exception:
            pass

        if is_pre_delivery:
            console.print(
                "[cyan]Your vehicle hasn't been delivered yet — this is normal.[/cyan]\n"
                "  The Owner API cannot access vehicles before delivery.\n"
                "  Live vehicle data (battery, location, climate) will be\n"
                "  available after you take delivery.\n\n"
                "  [dim]Order tracking and dossier data work perfectly in the meantime.[/dim]\n"
                "  [dim]After delivery, run [bold]tesla setup --force[/bold] to re-check.[/dim]"
            )
        else:
            console.print(
                "[yellow]Your VIN requires the Advanced tier (Fleet API).[/yellow]\n"
                "  The Owner API is blocked for newer Tesla vehicles.\n"
            )
            upgrade = Prompt.ask(
                "Upgrade to Advanced (Fleet API) now?", choices=["y", "n"], default="y"
            )
            if upgrade == "y":
                _show_fleet_api_guide()
                try:
                    from tesla_cli.cli.commands.config_cmd import _auth_fleet

                    _auth_fleet()
                    cfg = load_config()
                    cfg.general.backend = "fleet-signed"
                    save_config(cfg)
                    console.print(
                        "[green]✓ Upgraded to Advanced tier — "
                        "fleet-signed backend active.[/green]"
                    )
                    return "advanced"
                except (TeslaCliError, KeyboardInterrupt, EOFError):
                    console.print(
                        "[yellow]Upgrade skipped — configure later with[/yellow] "
                        "[bold]tesla config auth fleet[/bold]"
                    )
    except Exception:
        # Network error or other transient issue — silently skip the probe
        pass

    return tier_selected


def _print_done_panel(tier_selected: str) -> None:
    """Print the final summary panel, tailored to the chosen tier."""
    if tier_selected == "advanced":
        tier_line = "Tier: [bold green]Advanced[/bold green] (Fleet API)"
        features_line = (
            "Available: everything — telemetry, Powerwall, signed commands, analytics"
        )
        upgrade_line = ""
    elif tier_selected == "tessie":
        tier_line = "Tier: [bold cyan]Tessie[/bold cyan] (managed proxy)"
        features_line = "Available: vehicle data, commands, order tracking, TeslaMate analytics"
        upgrade_line = (
            "\n  Upgrade to Fleet: [bold]tesla config auth fleet[/bold]"
            " (for telemetry, Powerwall, signed commands)"
        )
    else:
        # basic / owner
        tier_line = "Tier: [bold]Basic[/bold] (email + password)"
        features_line = (
            "Available: order tracking, vehicle data, commands, TeslaMate analytics"
        )
        upgrade_line = (
            "\n  Upgrade: [bold]tesla config auth fleet[/bold]"
            " (for telemetry, Powerwall, signed commands)"
        )

    body = (
        f"[bold green]✓ Setup complete![/bold green]\n\n"
        f"  {tier_line}\n"
        f"  {features_line}"
        f"{upgrade_line}\n\n"
        "Next steps:\n"
        "  [bold]tesla config doctor[/bold]        — validate all connections\n"
        "  [bold]tesla vehicle ready[/bold]        — check if your car is ready to drive\n"
        "  [bold]tesla vehicle summary[/bold]      — compact vehicle status\n\n"
        "Daily commands:\n"
        "  [bold]tesla charge status[/bold]        — current charge state\n"
        "  [bold]tesla charge last[/bold]          — most recent charging session\n"
        "  [bold]tesla order status[/bold]         — check your order\n"
        "  [bold]tesla order watch -i 5[/bold]     — monitor for changes every 5 min\n\n"
        "Infrastructure:\n"
        "  [bold]tesla telemetry status[/bold]     — fleet-telemetry streaming status\n"
        "  [bold]tesla teslaMate status[/bold]     — TeslaMate analytics status\n"
        "  [bold]tesla config doctor[/bold]        — full system health check"
    )
    console.print(Panel.fit(body, border_style="green"))


def _check_docker_available() -> bool:
    """Return True if Docker daemon is reachable, False otherwise (no exception raised)."""
    import subprocess

    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _run_fleet_telemetry_install(ft_stack: object) -> None:
    """Interactively install and start the fleet-telemetry stack."""
    from tesla_cli.core.exceptions import DockerNotFoundError
    from tesla_cli.infra.fleet_telemetry_stack import FleetTelemetryStack, FleetTelemetryStackError

    assert isinstance(ft_stack, FleetTelemetryStack)

    console.print()
    console.print(
        "[dim]Fleet-telemetry needs a hostname or IP that your vehicle can reach over TLS.[/dim]"
    )
    hostname = Prompt.ask(
        "Hostname or IP for fleet-telemetry",
        default="localhost",
    )

    console.print("[dim]Generating TLS certificates and pulling Docker image...[/dim]")
    try:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
        ) as p:
            p.add_task("Installing fleet-telemetry...", total=None)
            result = ft_stack.install(hostname=hostname)

        if result.get("healthy"):
            console.print("[green]✓ Fleet-telemetry installed and running.[/green]")
            console.print(
                f"  Listening on [bold]{hostname}:{result.get('port', 4443)}[/bold]"
            )
        else:
            console.print(
                "[yellow]Fleet-telemetry installed but may not be healthy yet.[/yellow]\n"
                "[dim]Check: tesla telemetry status[/dim]"
            )
        # ── Persist config ──────────────────────────────────────────────────
        cfg = load_config()
        cfg.telemetry.enabled = True
        cfg.telemetry.hostname = hostname
        cfg.telemetry.managed = True
        save_config(cfg)
        console.print("[green]✓ Fleet-telemetry config saved.[/green]")

        # ── Auto-configure streaming fields via Fleet API ───────────────────
        vin = cfg.general.default_vin
        if not vin:
            console.print(
                "[yellow]No VIN configured — skipping streaming field setup.[/yellow]\n"
                "[dim]Run: tesla telemetry configure[/dim]"
            )
            return

        default_fields = {
            "BatteryLevel": {"interval_seconds": 60},
            "ChargeState": {"interval_seconds": 60},
            "VehicleSpeed": {"interval_seconds": 30},
            "Location": {"interval_seconds": 120},
            "InsideTemp": {"interval_seconds": 300},
            "OutsideTemp": {"interval_seconds": 300},
            "Odometer": {"interval_seconds": 3600},
            "SentryMode": {"interval_seconds": 60},
        }
        try:
            from tesla_cli.core.backends.fleet_telemetry import (
                load_fleet_telemetry_backend,
                read_ca_cert,
            )

            ft_backend = load_fleet_telemetry_backend()
            ca_cert = read_ca_cert(cfg.telemetry.ca_cert_path)
            ft_backend.configure_streaming(
                vin=vin,
                hostname=hostname,
                port=cfg.telemetry.port,
                ca_cert=ca_cert,
                fields=default_fields,
            )
            console.print("[green]✓ Streaming fields configured on vehicle.[/green]")
        except Exception as e:
            console.print(
                f"[yellow]Warning: could not configure streaming fields:[/yellow] {e}\n"
                "[dim]Run: tesla telemetry configure[/dim]"
            )
    except DockerNotFoundError as e:
        console.print(f"[red]Docker error:[/red] {e}")
        console.print("[dim]Skipping — install Docker first, then run: tesla telemetry install[/dim]")
    except FleetTelemetryStackError as e:
        console.print(f"[yellow]Fleet-telemetry install failed:[/yellow] {e}")
        console.print("[dim]Retry manually: tesla telemetry install[/dim]")
    except Exception as e:
        console.print(f"[yellow]Unexpected error during fleet-telemetry install:[/yellow] {e}")


def _run_teslamate_install(tm_stack: object) -> None:
    """Interactively install and start the TeslaMate stack."""
    from tesla_cli.core.exceptions import DockerNotFoundError
    from tesla_cli.infra.teslamate_stack import TeslaMateStack, TeslaMateStackError

    assert isinstance(tm_stack, TeslaMateStack)

    console.print("[dim]Pulling TeslaMate images (PostgreSQL, Grafana, Mosquitto)...[/dim]")
    try:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
        ) as p:
            p.add_task("Installing TeslaMate...", total=None)
            result = tm_stack.install()

        if result.get("healthy"):
            console.print("[green]✓ TeslaMate installed and running.[/green]")
            grafana_port = result.get("grafana_port", 3000)
            teslamate_port = result.get("teslamate_port", 4000)
            console.print(
                f"  TeslaMate: [bold]http://localhost:{teslamate_port}[/bold]\n"
                f"  Grafana:   [bold]http://localhost:{grafana_port}[/bold]  "
                f"(admin / {result.get('grafana_password', '***')})"
            )
            # Update managed flag in config
            cfg = load_config()
            cfg.teslaMate.managed = True
            save_config(cfg)
        else:
            console.print(
                "[yellow]TeslaMate installed but services may still be starting.[/yellow]\n"
                "[dim]Check: tesla teslaMate status[/dim]"
            )
    except DockerNotFoundError as e:
        console.print(f"[red]Docker error:[/red] {e}")
        console.print("[dim]Skipping — install Docker first, then run: tesla teslaMate install[/dim]")
    except TeslaMateStackError as e:
        console.print(f"[yellow]TeslaMate install failed:[/yellow] {e}")
        console.print("[dim]Retry manually: tesla teslaMate install[/dim]")
    except Exception as e:
        console.print(f"[yellow]Unexpected error during TeslaMate install:[/yellow] {e}")


def _run_notifications_setup(cfg: object) -> None:
    """Interactively configure Apprise notification URLs."""
    from tesla_cli.core.config import Config

    assert isinstance(cfg, Config)

    console.print()
    console.print(
        "  [bold]Common formats:[/bold]\n"
        "  [cyan]tgram://BOT_TOKEN/CHAT_ID[/cyan]           — Telegram\n"
        "  [cyan]discord://WEBHOOK_ID/WEBHOOK_TOKEN[/cyan]  — Discord\n"
        "  [cyan]slack://TOKEN/CHANNEL[/cyan]               — Slack\n"
        "  [cyan]mailto://user:pass@gmail.com[/cyan]        — Email\n"
        "  [dim]Full list: https://github.com/caronc/apprise/wiki[/dim]\n"
    )

    urls: list[str] = list(cfg.notifications.apprise_urls)
    while True:
        url = Prompt.ask(
            "Apprise URL (leave blank to finish)",
            default="",
        )
        if not url.strip():
            break
        urls.append(url.strip())
        console.print(f"  [green]✓[/green] Added: {url.strip()}")

    if not urls:
        console.print("[dim]No URLs entered — notifications not configured.[/dim]")
        return

    cfg.notifications.apprise_urls = urls
    cfg.notifications.enabled = True
    save_config(cfg)
    console.print(f"[green]✓ {len(urls)} notification URL(s) saved.[/green]")

    # Send a test notification
    send_test = Confirm.ask("Send a test notification now?", default=True)
    if send_test:
        _send_test_notification(urls)


def _run_automations_setup() -> None:
    """Create 3 default automation rules: low battery, charge complete, sentry event."""
    from tesla_cli.core.automation import AutomationEngine
    from tesla_cli.core.models.automation import AutomationAction, AutomationRule, AutomationTrigger

    engine = AutomationEngine()

    default_rules: list[AutomationRule] = [
        AutomationRule(
            name="Low battery alert",
            trigger=AutomationTrigger(type="battery_below", threshold=20),
            action=AutomationAction(
                type="notify",
                message="Battery low: {battery_level}% — plug in soon.",
            ),
        ),
        AutomationRule(
            name="Charge complete",
            trigger=AutomationTrigger(type="charging_complete"),
            action=AutomationAction(
                type="notify",
                message="Charging complete — battery at {battery_level}%.",
            ),
        ),
        AutomationRule(
            name="Sentry event",
            trigger=AutomationTrigger(type="sentry_event"),
            action=AutomationAction(
                type="notify",
                message="Sentry Mode triggered — check your vehicle.",
            ),
        ),
    ]

    existing_names = {r.name for r in engine.rules}
    added = 0
    for rule in default_rules:
        if rule.name not in existing_names:
            engine.add_rule(rule)
            added += 1
            console.print(f"  [green]✓[/green] Rule added: [bold]{rule.name}[/bold]")
        else:
            console.print(f"  [dim]Skipped (already exists):[/dim] {rule.name}")

    if added:
        console.print(f"[green]✓ {added} automation rule(s) saved.[/green]")
    else:
        console.print("[dim]All default rules already configured.[/dim]")


def _send_test_notification(urls: list[str]) -> None:
    """Attempt to send a test notification via Apprise."""
    try:
        import apprise  # type: ignore[import]

        ap = apprise.Apprise()
        for url in urls:
            ap.add(url)
        ok = ap.notify(
            title="Tesla CLI",
            body="Test notification from tesla setup wizard. All systems go!",
        )
        if ok:
            console.print("[green]✓ Test notification sent.[/green]")
        else:
            console.print(
                "[yellow]Notification may not have delivered — check your URL format.[/yellow]"
            )
    except ImportError:
        console.print(
            "[yellow]Apprise not installed — install with:[/yellow] [bold]uv add apprise[/bold]"
        )
    except Exception as e:
        console.print(f"[yellow]Test notification failed:[/yellow] {e}")
