"""Config commands: tesla config show/set/auth/alias."""

from __future__ import annotations

import typer
from rich.prompt import Prompt

from tesla_cli.cli.output import console, is_json_mode, render_dict, render_success
from tesla_cli.core.auth import tokens
from tesla_cli.core.config import load_config, save_config

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
    from tesla_cli.core.backends.order import DELIVERY_CACHE_FILE

    if DELIVERY_CACHE_FILE.exists():
        import json

        cached = json.loads(DELIVERY_CACHE_FILE.read_text())
        data["delivery_cache"] = {
            "status": "cached",
            "fetched_at": cached.get("fetched_at", "unknown"),
            "appointment": cached.get("delivery_details", {})
            .get("deliveryTiming", {})
            .get("appointment", ""),
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
    # Keyring-stored keys (never written to config.toml)
    keyring_map = {
        "planner-openroute-key": tokens.PLANNER_OPENROUTE_KEY,
        "planner-openchargemap-key": tokens.PLANNER_OPENCHARGEMAP_KEY,
    }
    if key in keyring_map:
        tokens.set_token(keyring_map[key], value)
        render_success(f"{key} saved to keyring")
        return

    cfg = load_config()
    key_map = {
        "default-vin": ("general", "default_vin"),
        "backend": ("general", "backend"),
        "reservation-number": ("order", "reservation_number"),
        "region": ("fleet", "region"),
        "client-id": ("fleet", "client_id"),
        "fleet-domain": ("fleet", "domain"),
        "notifications-enabled": ("notifications", "enabled"),
        "cost-per-kwh": ("general", "cost_per_kwh"),
        "cedula": ("general", "cedula"),
        "telemetry-enabled": ("telemetry", "enabled"),
        "telemetry-hostname": ("telemetry", "hostname"),
        "telemetry-port": ("telemetry", "port"),
        "planner-router": ("planner", "router"),
        "planner-osrm-url": ("planner", "osrm_base_url"),
        "planner-stops-every-km": ("planner", "default_stops_every_km"),
        "planner-car-model": ("planner", "default_car_model"),
    }
    if key not in key_map:
        valid = ", ".join(list(key_map.keys()) + list(keyring_map.keys()))
        console.print(f"[red]Unknown key:[/red] {key}\nValid keys: {valid}")
        raise typer.Exit(1)
    section, field = key_map[key]
    section_obj = getattr(cfg, section)
    if field == "enabled":
        value = value.lower() in ("true", "1", "yes")  # type: ignore[assignment]
    elif field in ("cost_per_kwh", "default_stops_every_km"):
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

    from tesla_cli.core.config import CONFIG_FILE

    if not CONFIG_FILE.exists():
        console.print(
            "[yellow]No config file found. Run[/yellow] [bold]tesla setup[/bold] [yellow]first.[/yellow]"
        )
        raise typer.Exit(1)

    content = CONFIG_FILE.read_text()

    if output:
        from pathlib import Path

        Path(output).write_text(content)
        render_success(
            f"Config exported to {output}  (tokens NOT included — those live in keyring)"
        )
    else:
        console.print(content)


@config_app.command("import")
def config_import(
    source: str = typer.Argument(..., help="TOML config file to import"),
    merge: bool = typer.Option(
        True, "--merge/--replace", help="Merge with existing config (default) or replace"
    ),
) -> None:
    """Import configuration from a TOML file.

    tesla config import backup.toml           → merge into existing config
    tesla config import backup.toml --replace → replace entire config
    """
    from pathlib import Path

    from tesla_cli.core.config import CONFIG_FILE, Config

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
    password: str = typer.Option(
        ..., "--password", "-p", prompt=True, hide_input=True, help="Encryption password"
    ),
) -> None:
    """Encrypt a stored token with AES-256-GCM (for headless/server deployments).

    tesla config encrypt-token order_refresh_token --password mypass
    tesla config encrypt-token fleet_access_token -p mypass
    """
    from tesla_cli.core.auth.encryption import encrypt_token, is_encrypted

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
    password: str = typer.Option(
        ..., "--password", "-p", prompt=True, hide_input=True, help="Decryption password"
    ),
) -> None:
    """Decrypt an AES-256-GCM encrypted token back to plaintext in the keyring.

    tesla config decrypt-token order_refresh_token --password mypass
    """
    from tesla_cli.core.auth.encryption import decrypt_token, is_encrypted

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
    output: str = typer.Option(
        "tesla-config-backup.json", "--output", "-o", help="Output JSON file"
    ),
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
                k: "[REDACTED]"
                if any(t in k.lower() for t in ("token", "secret", "key", "password"))
                else _redact(v)
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
    console.print(
        f"  [green]\u2713[/green] Config backed up to [bold]{out}[/bold] (tokens redacted)"
    )


@config_app.command("restore")
def config_restore(
    input_file: str = typer.Argument(..., help="JSON backup file to restore from"),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing config without prompting"
    ),
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
        confirm = typer.confirm(
            f"Restore config from {src.name}? This will overwrite current settings."
        )
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


@config_app.command("register")
def config_register(
    region: str = typer.Option("na", "--region", "-r", help="Fleet API region: na, eu, cn"),
) -> None:
    """Register this app as a Fleet API partner in a region (one-time setup).

    Required after first `tesla config auth fleet` — Tesla needs this before
    the user token can call vehicle endpoints.

    \b
    tesla config register           → register in NA (default)
    tesla config register --region eu
    """
    from tesla_cli.core.auth.oauth import register_fleet_partner

    cfg = load_config()
    client_id = cfg.fleet.client_id or ""
    if not client_id:
        console.print("[red]No client_id configured.[/red] Run: tesla config auth fleet")
        raise typer.Exit(1)

    client_secret = tokens.get_token(tokens.FLEET_CLIENT_SECRET)
    if not client_secret:
        client_secret = Prompt.ask("Client Secret", password=True)
        if not client_secret.strip():
            console.print("[red]No client secret provided.[/red]")
            raise typer.Exit(1)
        tokens.set_token(tokens.FLEET_CLIENT_SECRET, client_secret.strip())

    console.print(f"[dim]Registering partner account in Fleet API region '{region}'...[/dim]")
    try:
        result = register_fleet_partner(client_id, client_secret, region=region)
        console.print(f"  [green]✓[/green] Partner registered: {result}")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    render_success(f"Partner account registered in region '{region}'. Run: tesla vehicle info")


@config_app.command("auth")
def config_auth(
    backend: str = typer.Argument(
        help="Backend to authenticate: order, tessie, fleet, fleet-signed"
    ),
) -> None:
    """Authenticate with a Tesla backend."""
    if backend == "order":
        _auth_order()
    elif backend == "tessie":
        _auth_tessie()
    elif backend == "fleet":
        _auth_fleet()
    elif backend == "fleet-signed":
        _auth_fleet_signed()
    else:
        console.print(
            f"[red]Unknown backend:[/red] {backend}\nValid: order, tessie, fleet, fleet-signed"
        )
        raise typer.Exit(1)


def _doctor_check_tokens(cfg, _check) -> None:
    """Check 1–5: auth tokens and vehicle backend."""
    if tokens.has_token(tokens.ORDER_ACCESS_TOKEN):
        _check("Order auth token", "ok", "Token present in keyring")
    else:
        _check(
            "Order auth token",
            "fail",
            "No order access token found",
            "Run: tesla config auth order",
        )

    vin = cfg.general.default_vin or ""
    if vin:
        _check("Default VIN", "ok", f"VIN: {vin}")
    else:
        _check(
            "Default VIN",
            "warn",
            "No default VIN configured",
            "Run: tesla config set default-vin <YOUR_VIN>",
        )

    rn = cfg.order.reservation_number or ""
    if rn:
        _check("Reservation number", "ok", f"RN: {rn}")
    else:
        _check(
            "Reservation number",
            "warn",
            "No reservation number configured",
            "Run: tesla config set reservation-number RNXXXXXXXXX",
        )

    backend_name = cfg.general.backend or "owner"
    if backend_name in ("fleet", "fleet-signed", "tessie", "owner"):
        _check("Vehicle backend", "ok", f"Backend: {backend_name}")
    else:
        _check(
            "Vehicle backend",
            "warn",
            f"Unrecognised backend: '{backend_name}'",
            "Run: tesla config set backend fleet|fleet-signed|tessie|owner",
        )

    if backend_name == "tessie":
        if tokens.has_token(tokens.TESSIE_TOKEN):
            _check("Tessie API token", "ok", "Token present in keyring")
        else:
            _check(
                "Tessie API token",
                "fail",
                "No Tessie token found",
                "Run: tesla config auth tessie",
            )
    elif backend_name == "fleet":
        if tokens.has_token(tokens.FLEET_ACCESS_TOKEN):
            _check("Fleet API token", "ok", "Token present in keyring")
        else:
            _check(
                "Fleet API token",
                "fail",
                "No Fleet API token found",
                "Run: tesla config auth fleet",
            )
    else:
        if tokens.has_token(tokens.ORDER_ACCESS_TOKEN):
            _check("Owner API token", "ok", "Reusing order token for Owner API")
        else:
            _check(
                "Owner API token",
                "warn",
                "No owner API token (use tessie or fleet for vehicle control)",
                "",
            )


def _doctor_check_teslaMate(cfg, _check) -> None:
    """Check 6: TeslaMate database connectivity."""
    tm_url = cfg.teslaMate.database_url or ""
    if not tm_url:
        _check(
            "TeslaMate DB",
            "warn",
            "Not configured (optional)",
            "Run: tesla teslaMate connect <url>",
        )
        return
    try:
        from tesla_cli.core.backends.teslaMate import TeslaMateBacked

        tm = TeslaMateBacked(tm_url, car_id=cfg.teslaMate.car_id)
        if tm.ping():
            _check("TeslaMate DB", "ok", f"Connected: {tm_url[:40]}...")
        else:
            _check("TeslaMate DB", "fail", "DB unreachable", "Check DB URL and connectivity")
    except ImportError:
        _check(
            "TeslaMate DB",
            "warn",
            "psycopg2 not installed (optional)",
            "uv pip install psycopg2-binary",
        )
    except Exception as exc:
        _check("TeslaMate DB", "fail", f"Connection error: {str(exc)[:60]}", "Check DB URL")


def _doctor_check_config_file(_check) -> None:
    """Check 7: config file on disk."""
    try:
        from tesla_cli.core.config import CONFIG_PATH

        if CONFIG_PATH.exists():
            _check("Config file", "ok", f"Found: {CONFIG_PATH}")
        else:
            _check(
                "Config file",
                "warn",
                "Config file not yet written (using defaults)",
                "Run any config set command",
            )
    except Exception:
        _check("Config file", "ok", "Config loaded successfully")


def _doctor_check_mqtt(cfg, _check) -> None:
    """Check 8: MQTT broker reachability."""
    mqtt_broker = cfg.mqtt.broker or ""
    if not mqtt_broker:
        _check("MQTT broker", "warn", "Not configured (optional)", "Run: tesla mqtt setup")
        return
    try:
        import socket

        sock = socket.create_connection((mqtt_broker, cfg.mqtt.port), timeout=5)
        sock.close()
        _check("MQTT broker", "ok", f"Reachable: {mqtt_broker}:{cfg.mqtt.port}")
    except Exception as exc:
        _check(
            "MQTT broker",
            "fail",
            f"Unreachable: {mqtt_broker}:{cfg.mqtt.port} — {str(exc)[:40]}",
            "Check broker address and port",
        )


def _doctor_check_notifications(cfg, _check) -> None:
    """Check 9: notification channels."""
    notify_urls = cfg.notifications.apprise_urls
    if not notify_urls:
        _check(
            "Notifications",
            "warn",
            "No channels configured (optional)",
            "Run: tesla notify add <url>",
        )
    else:
        _check("Notifications", "ok", f"{len(notify_urls)} channel(s) configured")


def _doctor_check_home_assistant(cfg, _check) -> None:
    """Check 10: Home Assistant connectivity."""
    ha_url = cfg.home_assistant.url or ""
    if not ha_url:
        _check("Home Assistant", "warn", "Not configured (optional)", "Run: tesla ha setup")
        return
    try:
        import httpx

        r = httpx.get(f"{ha_url}/api/", timeout=5)
        if r.status_code < 500:
            _check("Home Assistant", "ok", f"Reachable: {ha_url}")
        else:
            _check("Home Assistant", "fail", f"Error {r.status_code}", "Check HA URL")
    except Exception as exc:
        _check("Home Assistant", "fail", f"Unreachable: {str(exc)[:40]}", "Check HA URL")


def _doctor_check_fleet_telemetry(cfg, _check) -> None:
    """Check 11: Fleet Telemetry container status."""
    if not cfg.telemetry.enabled:
        _check("Fleet Telemetry", "warn", "Not enabled (optional)", "Run: tesla telemetry install")
        return
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=fleet-telemetry", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            _check(
                "Fleet Telemetry",
                "warn",
                "Docker not available — cannot verify container status",
                "Ensure Docker is running",
            )
        elif result.stdout.strip():
            _check(
                "Fleet Telemetry",
                "ok",
                f"Container running — host: {cfg.telemetry.hostname}:{cfg.telemetry.port}",
            )
        else:
            _check(
                "Fleet Telemetry",
                "fail",
                "Enabled in config but container not running",
                "Run: tesla telemetry start",
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _check(
            "Fleet Telemetry",
            "warn",
            "Docker not found — cannot verify container status",
            "Install Docker or run: tesla telemetry status",
        )


def _doctor_check_automations(_check) -> None:
    """Check 12: automations configuration."""
    import json as _json
    from pathlib import Path as _Path

    automations_path = _Path.home() / ".tesla-cli" / "automations.json"
    if not automations_path.exists():
        _check(
            "Automations",
            "warn",
            "No automation rules configured (optional)",
            "Run: tesla setup or tesla automations add",
        )
        return
    try:
        raw = _json.loads(automations_path.read_text())
        rules = raw.get("rules", [])
        enabled_count = sum(1 for r in rules if r.get("enabled", True))
        _check(
            "Automations",
            "ok",
            f"{len(rules)} rule(s) configured, {enabled_count} enabled",
        )
    except Exception as exc:
        _check(
            "Automations",
            "warn",
            f"Could not parse automations.json: {str(exc)[:60]}",
            "Run: tesla automations list",
        )


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

    _doctor_check_tokens(cfg, _check)
    _doctor_check_teslaMate(cfg, _check)
    _doctor_check_config_file(_check)
    _doctor_check_mqtt(cfg, _check)
    _doctor_check_notifications(cfg, _check)
    _doctor_check_home_assistant(cfg, _check)
    _doctor_check_fleet_telemetry(cfg, _check)
    _doctor_check_automations(_check)

    # ── Output ───────────────────────────────────────────────────────────────
    if is_json_mode():
        console.print_json(
            _json.dumps(
                {
                    "ok": ok_count,
                    "warn": warn_count,
                    "fail": fail_count,
                    "checks": checks,
                },
                indent=2,
            )
        )
        return

    console.print()
    for c in checks:
        icon, color = {
            "ok": ("✅", "green"),
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


@config_app.command("migrate")
def config_migrate(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without saving"),
) -> None:
    """Migrate config to the current version — fills in new defaults, removes obsolete keys.

    Safe to run at any time. Makes a backup before modifying.

    \b
    tesla config migrate
    tesla config migrate --dry-run
    """
    import datetime as _dt
    import json as _json
    import shutil

    from tesla_cli.core.config import CONFIG_FILE, Config

    cfg_old = load_config()
    old_dict = cfg_old.model_dump()

    # Create a fresh config with all current defaults
    cfg_new = Config()
    new_dict = cfg_new.model_dump()

    def _diff_keys(old: dict, new: dict, prefix: str = "") -> list[str]:
        added = []
        for k, v in new.items():
            full = f"{prefix}.{k}" if prefix else k
            if k not in old:
                added.append(full)
            elif isinstance(v, dict) and isinstance(old.get(k), dict):
                added.extend(_diff_keys(old[k], v, full))
        return added

    additions = _diff_keys(old_dict, new_dict)

    if is_json_mode():
        import tesla_cli

        console.print(
            _json.dumps(
                {
                    "dry_run": dry_run,
                    "additions": additions,
                    "version": tesla_cli.__version__,
                }
            )
        )
        return

    if not additions:
        console.print(
            "[green]\u2713[/green] Config is already up to date \u2014 no new fields needed."
        )
        return

    console.print(f"[bold]{len(additions)} new field(s) to add:[/bold]")
    for a in additions:
        console.print(f"  [dim]+[/dim] {a}")

    if dry_run:
        console.print(
            "\n[dim]Dry run \u2014 no changes made. Run without --dry-run to apply.[/dim]"
        )
        return

    # Backup and save
    if CONFIG_FILE.exists():
        backup_path = CONFIG_FILE.with_suffix(f".bak.{_dt.date.today().isoformat()}")
        shutil.copy2(CONFIG_FILE, backup_path)
        console.print(f"[dim]Backup saved to {backup_path}[/dim]")

    cfg_merged = cfg_old.model_copy(deep=True)
    save_config(cfg_merged)
    console.print(
        f"\n[green]\u2713[/green] Config migrated \u2014 {len(additions)} new default(s) added."
    )


@config_app.command("validate")
def config_validate() -> None:
    """Validate config structure, required fields, and value ranges.

    Checks schema compliance, required fields, URL formats, and port ranges.
    Exits 0 if all checks pass, 1 if any failures.

    \b
    tesla config validate
    tesla -j config validate
    """
    import json as _json
    import re

    # We need __version__ for the report
    from tesla_cli import __version__

    cfg = load_config()

    checks: list[dict] = []

    def _ok(field: str, msg: str) -> None:
        checks.append({"field": field, "status": "ok", "message": msg})

    def _warn(field: str, msg: str) -> None:
        checks.append({"field": field, "status": "warn", "message": msg})

    def _fail(field: str, msg: str) -> None:
        checks.append({"field": field, "status": "fail", "message": msg})

    # ── Required fields ──────────────────────────────────────────────────────
    if cfg.general.default_vin:
        _ok("general.default_vin", f"VIN configured: {cfg.general.default_vin[-6:]}")
    else:
        _warn("general.default_vin", "No default VIN set — run: tesla config set default-vin <VIN>")

    valid_backends = {"owner", "tessie", "fleet", "fleet-signed"}
    if cfg.general.backend in valid_backends:
        _ok("general.backend", f"Backend: {cfg.general.backend}")
    else:
        _fail(
            "general.backend",
            f"Unknown backend '{cfg.general.backend}' — must be one of: {', '.join(sorted(valid_backends))}",
        )

    # ── TeslaMate URL format ─────────────────────────────────────────────────
    if cfg.teslaMate.database_url:
        if cfg.teslaMate.database_url.startswith(
            "postgresql://"
        ) or cfg.teslaMate.database_url.startswith("postgres://"):
            _ok("teslaMate.database_url", "PostgreSQL URL format looks valid")
        else:
            _fail("teslaMate.database_url", "URL must start with postgresql:// or postgres://")

    # ── Home Assistant URL format ────────────────────────────────────────────
    if cfg.home_assistant.url:
        if re.match(r"^https?://", cfg.home_assistant.url):
            _ok("home_assistant.url", f"HA URL: {cfg.home_assistant.url}")
        else:
            _fail("home_assistant.url", "URL must start with http:// or https://")

    # ── Server port range ────────────────────────────────────────────────────
    if hasattr(cfg, "server"):
        port = getattr(cfg.server, "port", None)
        if port is not None:
            if 1 <= port <= 65535:
                _ok("server.port", f"Port {port} is valid")
            else:
                _fail("server.port", f"Port {port} is out of range (1–65535)")

    # ── MQTT config ──────────────────────────────────────────────────────────
    if cfg.mqtt.broker:
        _ok("mqtt.broker", f"MQTT broker: {cfg.mqtt.broker}")
        if not (0 <= cfg.mqtt.qos <= 2):
            _fail("mqtt.qos", f"QoS {cfg.mqtt.qos} is invalid — must be 0, 1, or 2")
        else:
            _ok("mqtt.qos", f"QoS {cfg.mqtt.qos} is valid")
        if not (1 <= cfg.mqtt.port <= 65535):
            _fail("mqtt.port", f"Port {cfg.mqtt.port} is out of range")
        else:
            _ok("mqtt.port", f"MQTT port {cfg.mqtt.port} is valid")

    # ── Notification URLs ────────────────────────────────────────────────────
    for i, url in enumerate(cfg.notifications.apprise_urls):
        if "://" in url:
            _ok(
                f"notifications.apprise_urls[{i}]",
                f"URL format OK: {url[:40]}…" if len(url) > 40 else f"URL format OK: {url}",
            )
        else:
            _warn(f"notifications.apprise_urls[{i}]", f"URL missing scheme (://): {url[:40]}")

    # ── cost_per_kwh ─────────────────────────────────────────────────────────
    if cfg.general.cost_per_kwh < 0:
        _fail("general.cost_per_kwh", "cost_per_kwh cannot be negative")
    elif cfg.general.cost_per_kwh > 0:
        _ok("general.cost_per_kwh", f"Energy cost: ${cfg.general.cost_per_kwh:.4f}/kWh")

    failures = [c for c in checks if c["status"] == "fail"]
    warnings = [c for c in checks if c["status"] == "warn"]

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "version": __version__,
                    "checks": checks,
                    "summary": {
                        "ok": len(checks) - len(failures) - len(warnings),
                        "warn": len(warnings),
                        "fail": len(failures),
                    },
                    "valid": len(failures) == 0,
                }
            )
        )
        if failures:
            raise typer.Exit(1)
        return

    for c in checks:
        icon = (
            "[green]✓[/green]"
            if c["status"] == "ok"
            else "[yellow]⚠[/yellow]"
            if c["status"] == "warn"
            else "[red]✗[/red]"
        )
        field = f"[dim]{c['field']}[/dim]"
        console.print(f"  {icon}  {field}  {c['message']}")

    console.print()
    if failures:
        console.print(
            f"[red]Validation failed:[/red] {len(failures)} error(s), {len(warnings)} warning(s)"
        )
        raise typer.Exit(1)
    elif warnings:
        console.print(f"[yellow]Config valid with {len(warnings)} warning(s)[/yellow]")
    else:
        console.print(f"[green]✓ Config is valid[/green]  ({len(checks)} checks passed)")


def _run_config_checks(cfg) -> list[dict]:
    """Run all config validation checks and return list of {field, status, message}."""
    import string

    checks: list[dict] = []

    def _ok(field: str, msg: str) -> None:
        checks.append({"field": field, "status": "ok", "message": msg})

    def _warn(field: str, msg: str) -> None:
        checks.append({"field": field, "status": "warn", "message": msg})

    def _err(field: str, msg: str) -> None:
        checks.append({"field": field, "status": "error", "message": msg})

    valid_backends = {"fleet", "fleet-signed", "tessie", "owner"}
    if cfg.general.default_vin:
        _ok("general.default_vin", f"Set: {cfg.general.default_vin}")
    else:
        _warn("general.default_vin", "Not set — most vehicle commands will fail")

    if cfg.general.backend in valid_backends:
        _ok("general.backend", f"Valid: {cfg.general.backend}")
    else:
        _err(
            "general.backend",
            f"Unknown backend '{cfg.general.backend}' — must be one of: {', '.join(sorted(valid_backends))}",
        )

    if 0.0 <= cfg.general.cost_per_kwh <= 5.0:
        _ok("general.cost_per_kwh", str(cfg.general.cost_per_kwh))
    else:
        _warn(
            "general.cost_per_kwh", f"Unusual value {cfg.general.cost_per_kwh} — expected 0.0–5.0"
        )

    if cfg.mqtt.broker:
        if not 1 <= cfg.mqtt.port <= 65535:
            _err("mqtt.port", f"Port {cfg.mqtt.port} out of range (1–65535)")
        else:
            _ok("mqtt.port", str(cfg.mqtt.port))
        if cfg.mqtt.qos not in (0, 1, 2):
            _err("mqtt.qos", f"QoS {cfg.mqtt.qos} invalid — must be 0, 1, or 2")
        else:
            _ok("mqtt.qos", str(cfg.mqtt.qos))
    else:
        _ok("mqtt", "Not configured (optional)")

    if cfg.home_assistant.url:
        if cfg.home_assistant.url.startswith(("http://", "https://")):
            _ok("home_assistant.url", cfg.home_assistant.url)
        else:
            _err("home_assistant.url", "Must start with http:// or https://")

    if cfg.teslaMate.database_url:
        if cfg.teslaMate.database_url.startswith("postgresql"):
            _ok("teslaMate.database_url", "Valid PostgreSQL URL")
        else:
            _err("teslaMate.database_url", "Must be a postgresql:// URL")
        if cfg.teslaMate.car_id < 1:
            _err("teslaMate.car_id", f"car_id {cfg.teslaMate.car_id} must be ≥ 1")
        else:
            _ok("teslaMate.car_id", str(cfg.teslaMate.car_id))

    if cfg.server.api_key and len(cfg.server.api_key) < 8:
        _warn("server.api_key", "API key < 8 chars — consider a longer key")

    tmpl = cfg.notifications.message_template
    known = {"{event}", "{vehicle}", "{detail}", "{ts}"}
    try:
        used = {f"{{{f}}}" for _, f, _, _ in string.Formatter().parse(tmpl) if f}
        unknown_keys = used - known
        if unknown_keys:
            _warn(
                "notifications.message_template",
                f"Unknown placeholder(s): {', '.join(sorted(unknown_keys))}",
            )
        else:
            _ok("notifications.message_template", tmpl[:60])
    except Exception:
        _warn("notifications.message_template", "Could not parse template")

    return checks


def _auth_order() -> None:
    """Run Tesla OAuth2+PKCE flow for order tracking."""
    from tesla_cli.core.auth.oauth import run_tesla_oauth_flow

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
        "[bold]Fleet API Authentication[/bold]\n\n"
        "You need a [bold]client_id[/bold] registered at developer.tesla.com.\n\n"
        "[bold cyan]Steps to register your app (free):[/bold cyan]\n"
        "  1. Go to [link=https://developer.tesla.com]developer.tesla.com[/link] → Create App\n"
        "  2. Name: alphanumeric or with spaces — Tesla rejects dashes "
        "(e.g. [italic]CarMonitor[/italic] or [italic]My Tesla Dashboard[/italic])\n"
        "  3. [bold]Redirect URI:[/bold] [yellow]https://auth.tesla.com/void/callback[/yellow]\n"
        "  4. Scopes (check every one you want to use):\n"
        "     [yellow]user_data  vehicle_device_data  vehicle_location\n"
        "     vehicle_cmds  vehicle_charging_cmds\n"
        "     energy_device_data  energy_cmds[/yellow]\n"
        "  5. Copy the [bold]client_id[/bold] and [bold]client_secret[/bold] Tesla gives you\n"
    )
    client_id = Prompt.ask("Client ID")
    if not client_id.strip():
        console.print("[red]No client ID provided.[/red]")
        raise typer.Exit(1)
    client_secret = Prompt.ask("Client Secret", password=True)
    if not client_secret.strip():
        console.print("[red]No client secret provided.[/red]")
        raise typer.Exit(1)

    cfg = load_config()
    cfg.fleet.client_id = client_id.strip()
    save_config(cfg)
    tokens.set_token(tokens.FLEET_CLIENT_SECRET, client_secret.strip())

    from tesla_cli.core.auth.oauth import FLEET_SCOPES, register_fleet_partner, run_tesla_oauth_flow

    # Step 1: Register partner account (one-time, uses client_credentials)
    console.print("[dim]Registering partner account in Fleet API (region NA)...[/dim]")
    try:
        register_fleet_partner(client_id.strip(), client_secret.strip(), region="na")
        console.print("  [green]✓[/green] Partner account registered in region NA")
    except Exception as exc:
        if "already" in str(exc).lower() or "204" in str(exc):
            console.print("  [dim]✓ Partner already registered (OK)[/dim]")
        else:
            console.print(
                f"  [yellow]⚠[/yellow] Partner registration: {exc}\n  Continuing with user authentication..."
            )

    # Step 2: User OAuth2 PKCE for vehicle access
    console.print("[bold]Starting OAuth2 with vehicle scopes...[/bold]")
    token_data = run_tesla_oauth_flow(client_id=client_id.strip(), scopes=FLEET_SCOPES)
    tokens.set_token(tokens.FLEET_ACCESS_TOKEN, token_data["access_token"])
    tokens.set_token(tokens.FLEET_REFRESH_TOKEN, token_data["refresh_token"])
    cfg.general.backend = "fleet"
    save_config(cfg)
    render_success("Fleet API authenticated. Backend set to 'fleet'.")

    # Auto-sync tokens to TeslaMate if managed stack is running
    if cfg.teslaMate.managed:
        try:
            from pathlib import Path

            from tesla_cli.infra.teslamate_stack import TeslaMateStack

            stack = TeslaMateStack(
                Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None
            )
            if stack.is_running() and stack.sync_tokens_from_keyring():
                console.print("  [green]Tokens synced to TeslaMate automatically.[/green]")
        except Exception:
            pass  # Non-critical


def _auth_fleet_signed() -> None:
    """Set up Vehicle Command Protocol (signed commands) for 2024.26+ firmware.

    Sequence (see docs/fleet-signed-setup.md):
      a) verify tesla-fleet-api is installed
      b) generate (or reuse) a prime256v1 EC key pair at ~/.tesla-cli/keys/
      c) preflight: fetch public key from the registered fleet domain
      d) dry-run the signed handshake against the default VIN
      e) on success, flip backend → "fleet-signed" and persist config
    """
    import stat
    from pathlib import Path

    from tesla_cli.core.config import resolve_vin
    from tesla_cli.core.exceptions import BackendNotSupportedError

    rollback_hint = "To return to read-only Fleet API: tesla config set backend fleet"

    def print_preflight_failure(domain: str) -> None:
        console.print(
            f"Public key not found at https://{domain}/.well-known/appspecific/com.tesla.3p.public-key.pem\n"
            "Deploy your public key via GitHub Pages: see docs/fleet-signed-setup.md#publishing-your-public-key\n"
            f"{rollback_hint}"
        )

    def print_handshake_failure() -> None:
        console.print(
            "Vehicle Command Protocol required. Run: tesla config auth fleet-signed\n"
            "Then pair this VIN in the Tesla app under Manage Keys → Add Key.\n"
            "Check status any time with: tesla doctor\n"
            f"{rollback_hint}"
        )

    try:
        # ── (a) dependency check ─────────────────────────────────────────────
        try:
            from tesla_cli.core.backends.fleet_signed import _require_fleet_api

            _require_fleet_api()
        except RuntimeError:
            console.print("Install: uv pip install 'tesla-cli[fleet]'")
            raise typer.Exit(1)

        # ── (b) key generation (idempotent) ──────────────────────────────────
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        keys_dir = Path.home() / ".tesla-cli" / "keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        private_key_path = keys_dir / "private-key.pem"
        public_key_path = keys_dir / "public-key.pem"

        if private_key_path.exists() or public_key_path.exists():
            console.print(f"[dim]Reusing existing key pair at {keys_dir}[/dim]")
        else:
            private_key = ec.generate_private_key(ec.SECP256R1())
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            public_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            private_key_path.write_bytes(private_pem)
            public_key_path.write_bytes(public_pem)
            private_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            console.print(f"[green]✓[/green] Generated prime256v1 key pair at {keys_dir}")

        # ── (c) public-key preflight ─────────────────────────────────────────
        import httpx

        cfg = load_config()
        domain = (getattr(cfg.fleet, "domain", "") or "").strip()
        if not domain:
            console.print(
                "\n[bold]Fleet domain required[/bold]\n"
                "Your app's public key must be published at a domain you control.\n"
                "Tesla registers the domain on your developer app; every OSS user\n"
                "picks a different one (never reuse another person's).\n\n"
                "[cyan]Three common setups:[/cyan]\n"
                "  1. GitHub Pages       [italic]<username>.github.io[/italic]  "
                "(free, 5 min)\n"
                "  2. Custom domain      [italic]tesla.mydomain.com[/italic]   "
                "(if you already have a host)\n"
                "  3. Netlify / Vercel   [italic]my-tesla-keys.netlify.app[/italic]   "
                "(free tier)\n\n"
                "See [link]docs/fleet-signed-setup.md[/link] for step-by-step "
                "instructions for each option.\n"
            )
            domain = Prompt.ask("Fleet domain (bare host, no https://)").strip()
            if not domain:
                console.print("[red]No domain provided. Aborting.[/red]")
                raise typer.Exit(1)
            domain = domain.removeprefix("https://").removeprefix("http://").rstrip("/")
            cfg.fleet.domain = domain
            save_config(cfg)
            console.print(f"[dim]Saved fleet.domain = {domain}[/dim]")
        url = f"https://{domain}/.well-known/appspecific/com.tesla.3p.public-key.pem"
        try:
            resp = httpx.get(url, timeout=10)
        except Exception:
            print_preflight_failure(domain=domain)
            raise typer.Exit(1)
        if resp.status_code != 200 or "BEGIN PUBLIC KEY" not in resp.text:
            print_preflight_failure(domain=domain)
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Public key reachable at {url}")

        # ── (c2) refresh partner account so Tesla re-fetches our pubkey ─────
        # Tesla CACHES the pubkey at partner registration time. If the user
        # rotated keys or published a new pubkey after first registering the
        # partner, Tesla is still serving the old fingerprint and any signed
        # command will 404. Re-POSTing to /api/1/partner_accounts forces Tesla
        # to re-fetch from the well-known URL. Skipped silently when we don't
        # have a client_secret stashed (no-op; the user likely hasn't run
        # `tesla config auth fleet` yet — they'll need to do that separately).
        cs = tokens.get_token(tokens.FLEET_CLIENT_SECRET)
        if cs and cfg.fleet.client_id:
            try:
                from tesla_cli.core.auth.oauth import register_fleet_partner

                register_fleet_partner(cfg.fleet.client_id, cs, region=cfg.fleet.region or "na")
                console.print("[green]✓[/green] Refreshed Tesla partner pubkey cache")
            except Exception as exc:
                console.print(
                    f"[yellow]⚠[/yellow] Partner re-register skipped: {exc}\n"
                    "[dim]If the handshake below fails with NotFound, run manually:\n"
                    '    python -c "from tesla_cli.core.auth.oauth import register_fleet_partner; ..."\n'
                    "or re-run `tesla config auth fleet` first.[/dim]"
                )

        # ── (d) dry-run handshake ────────────────────────────────────────────
        import asyncio

        from tesla_cli.core.backends.fleet_signed import FleetSignedBackend

        vin = resolve_vin(cfg, None)
        backend = FleetSignedBackend()

        async def _handshake_and_close() -> None:
            try:
                await backend._get_vehicle(vin)
            finally:
                await backend.close()

        try:
            asyncio.run(_handshake_and_close())
        except BackendNotSupportedError:
            print_handshake_failure()
            raise typer.Exit(1)
        except typer.Exit:
            raise
        except Exception:
            print_handshake_failure()
            raise typer.Exit(1)

        # ── (e) success: flip backend ────────────────────────────────────────
        cfg.general.backend = "fleet-signed"
        save_config(cfg)
        console.print(
            "[green]Paired. Backend switched to fleet-signed. "
            "Try: tesla vehicle flash-lights[/green]"
        )
    except typer.Exit:
        raise
    except BaseException:
        # Print the rollback hint on unexpected failure so the user is never
        # left without a way back to the read-only fleet backend.
        console.print(rollback_hint)
        raise SystemExit(1)


@config_app.command("export-env")
def config_export_env(
    output: str | None = typer.Option(
        None, "--output", "-o", help="Write to file (default: stdout)"
    ),
    docker: bool = typer.Option(False, "--docker", help="Docker Compose format (with quotes)"),
) -> None:
    """Export configuration as environment variables.

    Useful for Docker, systemd, or shell scripts.

    tesla config export-env                    # stdout
    tesla config export-env -o .env            # write to file
    tesla config export-env --docker -o .env   # Docker format
    """
    cfg = load_config()

    lines = [
        f"TESLA_VIN={cfg.general.default_vin}",
        f"TESLA_BACKEND={cfg.general.backend}",
        f"TESLA_RN={cfg.order.reservation_number}",
        f"TESLA_COST_PER_KWH={cfg.general.cost_per_kwh}",
    ]

    if cfg.teslaMate.database_url:
        lines.append(f"TESLA_TESLAMATE_URL={cfg.teslaMate.database_url}")
    if cfg.mqtt.broker:
        lines.append(f"TESLA_MQTT_BROKER={cfg.mqtt.broker}")
        lines.append(f"TESLA_MQTT_PORT={cfg.mqtt.port}")
    if cfg.server.api_key:
        lines.append(f"TESLA_API_KEY={cfg.server.api_key}")
    if cfg.home_assistant.url:
        lines.append(f"TESLA_HA_URL={cfg.home_assistant.url}")

    if docker:
        lines = [f'      {line.split("=", 1)[0]}: "{line.split("=", 1)[1]}"' for line in lines]
        text = "    environment:\n" + "\n".join(lines)
    else:
        text = "\n".join(lines)

    if output:
        from pathlib import Path

        Path(output).write_text(text + "\n", encoding="utf-8")
        console.print(f"[green]Exported to {output}[/green]")
    else:
        console.print(text)
