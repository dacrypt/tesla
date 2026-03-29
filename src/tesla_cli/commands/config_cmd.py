"""Config commands: tesla config show/set/auth/alias."""

from __future__ import annotations

import typer
from rich.prompt import Prompt

from tesla_cli.auth import tokens
from tesla_cli.config import load_config, save_config
from tesla_cli.output import console, render_dict, render_success

config_app = typer.Typer(name="config", help="Manage tesla-cli configuration.")


@config_app.command("show")
def config_show() -> None:
    """Show current configuration."""
    cfg = load_config()
    data = cfg.model_dump()
    # Mask token presence
    data["tokens"] = {
        "order": "configured" if tokens.has_token(tokens.ORDER_REFRESH_TOKEN) else "not set",
        "tessie": "configured" if tokens.has_token(tokens.TESSIE_TOKEN) else "not set",
        "fleet": "configured" if tokens.has_token(tokens.FLEET_ACCESS_TOKEN) else "not set",
    }

    # Show delivery cache status
    from tesla_cli.backends.order import DELIVERY_CACHE_FILE
    if DELIVERY_CACHE_FILE.exists():
        import json
        cached = json.loads(DELIVERY_CACHE_FILE.read_text())
        data["delivery_cache"] = {
            "status": "cached",
            "fetched_at": cached.get("fetched_at", "unknown"),
            "appointment": cached.get("delivery_details", {}).get("deliveryTiming", {}).get("appointment", ""),
        }
    else:
        data["delivery_cache"] = "not cached (run: tesla order delivery --import)"

    render_dict(data, title="Tesla CLI Configuration")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(help="Config key (e.g. default-vin, backend, reservation-number)"),
    value: str = typer.Argument(help="Value to set"),
) -> None:
    """Set a configuration value."""
    cfg = load_config()
    key_map = {
        "default-vin": ("general", "default_vin"),
        "backend": ("general", "backend"),
        "reservation-number": ("order", "reservation_number"),
        "region": ("fleet", "region"),
        "client-id": ("fleet", "client_id"),
        "notifications-enabled": ("notifications", "enabled"),
    }
    if key not in key_map:
        valid = ", ".join(key_map.keys())
        console.print(f"[red]Unknown key:[/red] {key}\nValid keys: {valid}")
        raise typer.Exit(1)
    section, field = key_map[key]
    section_obj = getattr(cfg, section)
    if field == "enabled":
        value = value.lower() in ("true", "1", "yes")  # type: ignore[assignment]
    setattr(section_obj, field, value)
    save_config(cfg)
    render_success(f"{key} = {value}")


@config_app.command("alias")
def config_alias(
    name: str = typer.Argument(help="Alias name (e.g. modely)"),
    vin: str = typer.Argument(help="VIN to map to"),
) -> None:
    """Create a VIN alias for convenience."""
    cfg = load_config()
    cfg.vehicles.aliases[name] = vin
    save_config(cfg)
    render_success(f"Alias '{name}' -> {vin}")


@config_app.command("auth")
def config_auth(
    backend: str = typer.Argument(help="Backend to authenticate: order, tessie, fleet"),
) -> None:
    """Authenticate with a Tesla backend."""
    if backend == "order":
        _auth_order()
    elif backend == "tessie":
        _auth_tessie()
    elif backend == "fleet":
        _auth_fleet()
    else:
        console.print(f"[red]Unknown backend:[/red] {backend}\nValid: order, tessie, fleet")
        raise typer.Exit(1)


def _auth_order() -> None:
    """Run Tesla OAuth2+PKCE flow for order tracking."""
    from tesla_cli.auth.oauth import run_tesla_oauth_flow

    console.print("[bold]Authenticating with Tesla for order tracking...[/bold]")
    token_data = run_tesla_oauth_flow()
    tokens.set_token(tokens.ORDER_ACCESS_TOKEN, token_data["access_token"])
    tokens.set_token(tokens.ORDER_REFRESH_TOKEN, token_data["refresh_token"])
    render_success("Order tracking authentication complete. Tokens saved to keyring.")


def _auth_tessie() -> None:
    """Prompt for Tessie API token."""
    console.print(
        "[bold]Tessie Authentication[/bold]\n"
        "Get your API token from: [link=https://my.tessie.com/settings/api]my.tessie.com/settings/api[/link]"
    )
    token = Prompt.ask("Tessie API token", password=True)
    if not token.strip():
        console.print("[red]No token provided.[/red]")
        raise typer.Exit(1)
    tokens.set_token(tokens.TESSIE_TOKEN, token.strip())
    cfg = load_config()
    cfg.tessie.configured = True
    cfg.general.backend = "tessie"
    save_config(cfg)
    render_success("Tessie token saved. Backend set to 'tessie'.")


def _auth_fleet() -> None:
    """Configure Fleet API credentials."""
    console.print(
        "[bold]Fleet API Authentication[/bold]\n"
        "Register your app at: [link=https://developer.tesla.com]developer.tesla.com[/link]"
    )
    client_id = Prompt.ask("Client ID")
    if not client_id.strip():
        console.print("[red]No client ID provided.[/red]")
        raise typer.Exit(1)
    cfg = load_config()
    cfg.fleet.client_id = client_id.strip()
    save_config(cfg)

    from tesla_cli.auth.oauth import run_tesla_oauth_flow

    console.print("[bold]Running OAuth2 flow...[/bold]")
    token_data = run_tesla_oauth_flow(client_id=client_id.strip())
    tokens.set_token(tokens.FLEET_ACCESS_TOKEN, token_data["access_token"])
    tokens.set_token(tokens.FLEET_REFRESH_TOKEN, token_data["refresh_token"])
    cfg.general.backend = "fleet"
    save_config(cfg)
    render_success("Fleet API authentication complete. Backend set to 'fleet'.")
