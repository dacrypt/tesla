"""Config commands: tesla config show/set/auth/alias."""

from __future__ import annotations

import typer
from rich.prompt import Prompt

from tesla_cli.auth import tokens
from tesla_cli.config import load_config, save_config
from tesla_cli.output import console, is_json_mode, render_dict, render_success

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
        "cost-per-kwh": ("general", "cost_per_kwh"),
    }
    if key not in key_map:
        valid = ", ".join(key_map.keys())
        console.print(f"[red]Unknown key:[/red] {key}\nValid keys: {valid}")
        raise typer.Exit(1)
    section, field = key_map[key]
    section_obj = getattr(cfg, section)
    if field == "enabled":
        value = value.lower() in ("true", "1", "yes")  # type: ignore[assignment]
    elif field == "cost_per_kwh":
        value = float(value)  # type: ignore[assignment]
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


@config_app.command("export")
def config_export(
    output: str = typer.Option(None, "--output", "-o", help="Write to file instead of stdout"),
) -> None:
    """Export current configuration to TOML (safe to share — tokens not included).

    tesla config export                    → print to stdout
    tesla config export -o backup.toml    → write to file
    """

    from tesla_cli.config import CONFIG_FILE

    if not CONFIG_FILE.exists():
        console.print("[yellow]No config file found. Run[/yellow] [bold]tesla setup[/bold] [yellow]first.[/yellow]")
        raise typer.Exit(1)

    content = CONFIG_FILE.read_text()

    if output:
        from pathlib import Path
        Path(output).write_text(content)
        render_success(f"Config exported to {output}  (tokens NOT included — those live in keyring)")
    else:
        console.print(content)


@config_app.command("import")
def config_import(
    source: str = typer.Argument(..., help="TOML config file to import"),
    merge: bool = typer.Option(True, "--merge/--replace", help="Merge with existing config (default) or replace"),
) -> None:
    """Import configuration from a TOML file.

    tesla config import backup.toml           → merge into existing config
    tesla config import backup.toml --replace → replace entire config
    """
    from pathlib import Path

    from tesla_cli.config import CONFIG_FILE, Config

    src = Path(source)
    if not src.exists():
        console.print(f"[red]File not found:[/red] {source}")
        raise typer.Exit(1)

    try:
        import tomllib
        imported = tomllib.loads(src.read_text())
        imported_cfg = Config.model_validate(imported)
    except Exception as e:
        console.print(f"[red]Failed to parse config:[/red] {e}")
        raise typer.Exit(1)

    if merge and CONFIG_FILE.exists():
        existing = load_config()
        # Merge: imported values overwrite existing non-default values
        merged = existing.model_dump()
        for section, values in imported_cfg.model_dump().items():
            if isinstance(values, dict):
                merged[section].update({k: v for k, v in values.items() if v})
            else:
                if values:
                    merged[section] = values
        final = Config.model_validate(merged)
    else:
        final = imported_cfg

    save_config(final)
    render_success(f"Config imported from {source}" + (" (merged)" if merge else " (replaced)"))


@config_app.command("encrypt-token")
def config_encrypt_token(
    key_name: str = typer.Argument(..., help="Token key name (e.g. order_refresh_token)"),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, help="Encryption password"),
) -> None:
    """Encrypt a stored token with AES-256-GCM (for headless/server deployments).

    tesla config encrypt-token order_refresh_token --password mypass
    tesla config encrypt-token fleet_access_token -p mypass
    """
    from tesla_cli.auth.encryption import encrypt_token, is_encrypted

    raw = tokens.get_token(key_name)
    if not raw:
        console.print(f"[red]Token not found:[/red] {key_name}")
        raise typer.Exit(1)
    if is_encrypted(raw):
        console.print(f"[yellow]Token '{key_name}' is already encrypted.[/yellow]")
        return
    encrypted = encrypt_token(raw, password)
    tokens.set_token(key_name, encrypted)
    render_success(f"Token '{key_name}' encrypted with AES-256-GCM")


@config_app.command("decrypt-token")
def config_decrypt_token(
    key_name: str = typer.Argument(..., help="Token key name to decrypt"),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, help="Decryption password"),
) -> None:
    """Decrypt an AES-256-GCM encrypted token back to plaintext in the keyring.

    tesla config decrypt-token order_refresh_token --password mypass
    """
    from tesla_cli.auth.encryption import decrypt_token, is_encrypted

    raw = tokens.get_token(key_name)
    if not raw:
        console.print(f"[red]Token not found:[/red] {key_name}")
        raise typer.Exit(1)
    if not is_encrypted(raw):
        console.print(f"[yellow]Token '{key_name}' is not encrypted.[/yellow]")
        return
    try:
        plaintext = decrypt_token(raw, password)
    except ValueError as exc:
        console.print(f"[red]Decryption failed:[/red] {exc}")
        raise typer.Exit(1)
    tokens.set_token(key_name, plaintext)
    render_success(f"Token '{key_name}' decrypted and restored to keyring")


@config_app.command("backup")
def config_backup(
    output: str = typer.Option("tesla-config-backup.json", "--output", "-o", help="Output JSON file"),
) -> None:
    """Export current configuration to a JSON backup file (tokens omitted for security).

    tesla config backup
    tesla config backup --output ~/tesla-backup.json
    """
    import json as _json
    from pathlib import Path

    cfg = load_config()
    data = cfg.model_dump()

    # Redact any token-like values in config (security)
    def _redact(obj: object) -> object:
        if isinstance(obj, dict):
            return {
                k: "[REDACTED]" if any(t in k.lower() for t in ("token", "secret", "key", "password")) else _redact(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [_redact(i) for i in obj]
        return obj

    safe = _redact(data)
    safe["_meta"] = {
        "backup_version": "1",
        "tesla_cli_version": "1.9.0",
    }

    out = Path(output).expanduser()
    out.write_text(_json.dumps(safe, indent=2, default=str))
    console.print(f"  [green]\u2713[/green] Config backed up to [bold]{out}[/bold] (tokens redacted)")


@config_app.command("restore")
def config_restore(
    input_file: str = typer.Argument(..., help="JSON backup file to restore from"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config without prompting"),
) -> None:
    """Restore configuration from a JSON backup file.

    tesla config restore tesla-config-backup.json
    tesla config restore backup.json --force
    """
    import json as _json
    from pathlib import Path

    src = Path(input_file).expanduser()
    if not src.exists():
        console.print(f"[red]File not found:[/red] {src}")
        raise typer.Exit(1)

    try:
        data = _json.loads(src.read_text())
    except Exception as exc:
        console.print(f"[red]Failed to read backup:[/red] {exc}")
        raise typer.Exit(1)

    data.pop("_meta", None)

    if not force:
        confirm = typer.confirm(f"Restore config from {src.name}? This will overwrite current settings.")
        if not confirm:
            console.print("[dim]Restore cancelled.[/dim]")
            return

    cfg = load_config()

    # Apply non-redacted, non-token fields from backup
    def _apply(target: object, source: dict) -> None:
        for k, v in source.items():
            if isinstance(v, dict) and hasattr(target, k):
                _apply(getattr(target, k), v)
            elif v != "[REDACTED]" and hasattr(target, k):
                try:
                    setattr(target, k, v)
                except Exception:
                    pass

    _apply(cfg, data)
    save_config(cfg)
    console.print(f"  [green]\u2713[/green] Config restored from [bold]{src}[/bold]")
    console.print("  [dim]Note: tokens were not restored (they must be re-authenticated)[/dim]")


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


@config_app.command("doctor")
def config_doctor() -> None:
    """Diagnose the CLI configuration — check tokens, API connectivity, and settings.

    tesla config doctor
    tesla -j config doctor
    """
    import json as _json

    checks: list[dict] = []
    ok_count = 0
    warn_count = 0
    fail_count = 0

    def _check(name: str, status: str, detail: str, fix: str = "") -> None:
        """Record a check result. status: ok | warn | fail"""
        nonlocal ok_count, warn_count, fail_count
        checks.append({"name": name, "status": status, "detail": detail, "fix": fix})
        if status == "ok":
            ok_count += 1
        elif status == "warn":
            warn_count += 1
        else:
            fail_count += 1

    cfg = load_config()

    # ── 1. Order auth token ──────────────────────────────────────────────────
    if tokens.has_token(tokens.ORDER_ACCESS_TOKEN):
        _check("Order auth token", "ok", "Token present in keyring")
    else:
        _check(
            "Order auth token", "fail",
            "No order access token found",
            "Run: tesla config auth order",
        )

    # ── 2. VIN configured ────────────────────────────────────────────────────
    vin = cfg.general.default_vin or ""
    if vin:
        _check("Default VIN", "ok", f"VIN: {vin}")
    else:
        _check(
            "Default VIN", "warn",
            "No default VIN configured",
            "Run: tesla config set default-vin <YOUR_VIN>",
        )

    # ── 3. Reservation number ────────────────────────────────────────────────
    rn = cfg.order.reservation_number or ""
    if rn:
        _check("Reservation number", "ok", f"RN: {rn}")
    else:
        _check(
            "Reservation number", "warn",
            "No reservation number configured",
            "Run: tesla config set reservation-number RNXXXXXXXXX",
        )

    # ── 4. Vehicle backend ───────────────────────────────────────────────────
    backend_name = cfg.general.backend or "owner"
    if backend_name in ("fleet", "tessie", "owner"):
        _check("Vehicle backend", "ok", f"Backend: {backend_name}")
    else:
        _check(
            "Vehicle backend", "warn",
            f"Unrecognised backend: '{backend_name}'",
            "Run: tesla config set backend fleet|tessie|owner",
        )

    # ── 5. Backend-specific token ────────────────────────────────────────────
    if backend_name == "tessie":
        if tokens.has_token(tokens.TESSIE_TOKEN):
            _check("Tessie API token", "ok", "Token present in keyring")
        else:
            _check(
                "Tessie API token", "fail",
                "No Tessie token found",
                "Run: tesla config auth tessie",
            )
    elif backend_name == "fleet":
        if tokens.has_token(tokens.FLEET_ACCESS_TOKEN):
            _check("Fleet API token", "ok", "Token present in keyring")
        else:
            _check(
                "Fleet API token", "fail",
                "No Fleet API token found",
                "Run: tesla config auth fleet",
            )
    else:
        if tokens.has_token(tokens.ORDER_ACCESS_TOKEN):
            _check("Owner API token", "ok", "Reusing order token for Owner API")
        else:
            _check("Owner API token", "warn", "No owner API token (use tessie or fleet for vehicle control)", "")

    # ── 6. TeslaMate ─────────────────────────────────────────────────────────
    tm_url = cfg.teslaMate.database_url or ""
    if not tm_url:
        _check("TeslaMate DB", "warn", "Not configured (optional)", "Run: tesla teslaMate connect <url>")
    else:
        try:
            from tesla_cli.backends.teslaMate import TeslaMateBacked
            tm = TeslaMateBacked(tm_url, car_id=cfg.teslaMate.car_id)
            if tm.ping():
                _check("TeslaMate DB", "ok", f"Connected: {tm_url[:40]}...")
            else:
                _check("TeslaMate DB", "fail", "DB unreachable", "Check DB URL and connectivity")
        except ImportError:
            _check("TeslaMate DB", "warn", "psycopg2 not installed (optional)", "uv pip install psycopg2-binary")
        except Exception as exc:
            _check("TeslaMate DB", "fail", f"Connection error: {str(exc)[:60]}", "Check DB URL")

    # ── 7. Config file ───────────────────────────────────────────────────────
    try:
        from tesla_cli.config import CONFIG_PATH
        if CONFIG_PATH.exists():
            _check("Config file", "ok", f"Found: {CONFIG_PATH}")
        else:
            _check("Config file", "warn", "Config file not yet written (using defaults)", "Run any config set command")
    except Exception:
        _check("Config file", "ok", "Config loaded successfully")

    # ── Output ───────────────────────────────────────────────────────────────
    if is_json_mode():
        console.print_json(_json.dumps({
            "ok": ok_count, "warn": warn_count, "fail": fail_count,
            "checks": checks,
        }, indent=2))
        return

    console.print()
    for c in checks:
        icon, color = {
            "ok":   ("✅", "green"),
            "warn": ("⚠️ ", "yellow"),
            "fail": ("❌", "red"),
        }.get(c["status"], ("?", "white"))
        console.print(f"  {icon}  [{color}]{c['name']}[/{color}]  [dim]{c['detail']}[/dim]")
        if c["fix"]:
            console.print(f"      [dim]→ {c['fix']}[/dim]")

    console.print()
    summary_color = "green" if fail_count == 0 else "red"
    console.print(
        f"  [{summary_color}]Result:[/{summary_color}] "
        f"[green]{ok_count} ok[/green]  "
        f"[yellow]{warn_count} warnings[/yellow]  "
        f"[red]{fail_count} errors[/red]"
    )
    console.print()
    if fail_count > 0:
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
