"""Home Assistant commands: tesla ha push|sync|status|setup.

Pushes Tesla vehicle state into Home Assistant as sensor entities via the
Home Assistant REST API (https://developers.home-assistant.io/docs/api/rest/).

Requires a Long-Lived Access Token from HA:
  Profile → Security → Long-Lived Access Tokens → Create Token
"""

from __future__ import annotations

import time

import typer

from tesla_cli.cli.commands.vehicle import _with_wake
from tesla_cli.cli.output import console, is_json_mode, render_success
from tesla_cli.core.config import load_config, resolve_vin, save_config

ha_app = typer.Typer(
    name="ha",
    help="Home Assistant integration — push vehicle state as sensor entities.",
)

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")

# Sensor entity prefix (slugified VIN tail)
_ENTITY_PREFIX = "tesla"

# Mapping: (nested_key_path) → (entity_slug, friendly_name, unit, device_class)
_SENSORS: list[tuple[str, str, str, str, str | None]] = [
    # (data_section, key, entity_slug, friendly_name, unit)
    ("charge_state", "battery_level", "battery_level", "Battery Level", "%"),
    ("charge_state", "battery_range", "battery_range", "Battery Range", "mi"),
    ("charge_state", "charging_state", "charging_state", "Charging State", None),
    ("charge_state", "charge_limit_soc", "charge_limit", "Charge Limit", "%"),
    ("charge_state", "charge_energy_added", "energy_added", "Energy Added", "kWh"),
    ("charge_state", "charger_power", "charger_power", "Charger Power", "kW"),
    ("drive_state", "speed", "speed", "Speed", "mph"),
    ("drive_state", "shift_state", "shift_state", "Shift State", None),
    ("drive_state", "latitude", "latitude", "Latitude", "°"),
    ("drive_state", "longitude", "longitude", "Longitude", "°"),
    ("drive_state", "heading", "heading", "Heading", "°"),
    ("climate_state", "inside_temp", "inside_temp", "Cabin Temperature", "°C"),
    ("climate_state", "outside_temp", "outside_temp", "Outside Temperature", "°C"),
    ("climate_state", "is_climate_on", "climate_on", "Climate On", None),
    ("vehicle_state", "locked", "locked", "Locked", None),
    ("vehicle_state", "odometer", "odometer", "Odometer", "mi"),
    ("vehicle_state", "software_version", "sw_version", "Software Version", None),
    ("vehicle_state", "is_user_present", "user_present", "User Present", None),
]


def _ha_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _push_state(base_url: str, token: str, entity_id: str, state: str, attributes: dict) -> dict:
    """PUT a single HA state entity. Returns parsed JSON response."""
    import json as _json
    import urllib.request as _req

    url = f"{base_url.rstrip('/')}/api/states/{entity_id}"
    payload = _json.dumps({"state": str(state), "attributes": attributes}).encode()
    req = _req.Request(url, data=payload, method="PUT", headers=_ha_headers(token))

    with _req.urlopen(req, timeout=10) as resp:  # noqa: S310
        return _json.loads(resp.read().decode())


def _push_all(data: dict, base_url: str, token: str, vin: str) -> list[dict]:
    """Push all sensor values from vehicle_data to HA. Returns list of results."""
    results = []
    for section, key, slug, friendly_name, unit in _SENSORS:
        sec = data.get(section) or {}
        val = sec.get(key)
        if val is None:
            continue
        entity_id = f"sensor.{_ENTITY_PREFIX}_{slug}"
        attributes = {"friendly_name": f"Tesla {friendly_name}", "vin": vin[-6:]}
        if unit:
            attributes["unit_of_measurement"] = unit
        try:
            resp = _push_state(base_url, token, entity_id, val, attributes)
            results.append(
                {"entity": entity_id, "state": str(val), "status": "ok", "ha_response": resp}
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {"entity": entity_id, "state": str(val), "status": "error", "error": str(exc)}
            )
    return results


# ──────────────────────────────────────────────────────────────────────────────


@ha_app.command("setup")
def ha_setup(
    url: str = typer.Argument(
        ..., help="Home Assistant URL (e.g. http://homeassistant.local:8123)"
    ),
    token: str = typer.Argument(..., help="Long-Lived Access Token from HA profile"),
) -> None:
    """Configure Home Assistant URL and access token.

    tesla ha setup http://homeassistant.local:8123 eyJ0eXAi...
    """
    cfg = load_config()
    cfg.home_assistant.url = url.rstrip("/")
    cfg.home_assistant.token = token
    save_config(cfg)
    render_success(f"Home Assistant configured: {url}\nTest with: tesla ha push")


@ha_app.command("status")
def ha_status() -> None:
    """Show Home Assistant configuration and connectivity.

    tesla ha status
    tesla -j ha status
    """
    import json as _json
    import urllib.request as _req

    cfg = load_config()
    base_url = cfg.home_assistant.url
    token = cfg.home_assistant.token
    configured = bool(base_url and token)

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "configured": configured,
                    "url": base_url or "",
                    "token_set": bool(token),
                }
            )
        )
        return

    from rich.table import Table

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("k", style="dim", width=22)
    t.add_column("v")
    t.add_row("URL", base_url or "[dim]not set[/dim]")
    t.add_row("Token", "[green]set[/green]" if token else "[red]not set[/red]")

    # Try pinging HA API
    if configured:
        try:
            req = _req.Request(
                f"{base_url}/api/",
                headers=_ha_headers(token),
            )
            with _req.urlopen(req, timeout=5) as resp:  # noqa: S310
                body = _json.loads(resp.read().decode())
                ha_ver = body.get("version", "?")
            t.add_row("HA Version", f"[green]{ha_ver}[/green]")
            t.add_row("Connectivity", "[green]✓ OK[/green]")
        except Exception as exc:  # noqa: BLE001
            t.add_row("Connectivity", f"[red]✗ {exc}[/red]")
    console.print(t)

    if not configured:
        console.print(
            "\n[yellow]Not configured.[/yellow]\nRun: [bold]tesla ha setup <URL> <TOKEN>[/bold]"
        )


@ha_app.command("push")
def ha_push(vin: str | None = VinOption) -> None:
    """Push current vehicle state to Home Assistant (one-shot).

    tesla ha push
    tesla -j ha push
    """
    import json as _json

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    url = cfg.home_assistant.url
    token = cfg.home_assistant.token

    if not url or not token:
        console.print(
            "[red]Home Assistant not configured.[/red]\n"
            "Run: [bold]tesla ha setup <URL> <TOKEN>[/bold]"
        )
        raise typer.Exit(1)

    data = _with_wake(lambda b, vv: b.get_vehicle_data(vv), v)
    results = _push_all(data, url, token, v)

    ok = sum(1 for r in results if r["status"] == "ok")
    errors = sum(1 for r in results if r["status"] == "error")

    if is_json_mode():
        console.print(_json.dumps({"pushed": ok, "errors": errors, "results": results}, indent=2))
        return

    if errors:
        console.print(f"[yellow]⚠ {errors} entity push(es) failed[/yellow]")
        for r in results:
            if r["status"] == "error":
                console.print(f"  [dim]{r['entity']}:[/dim] [red]{r['error']}[/red]")
    render_success(f"Pushed {ok} entities to Home Assistant  [dim](errors: {errors})[/dim]")


@ha_app.command("sync")
def ha_sync(
    interval: int = typer.Option(
        60, "--interval", "-i", help="Push interval in seconds (default 60)"
    ),
    notify: str = typer.Option("", "--notify", help="Apprise URL for error alerts"),
    vin: str | None = VinOption,
) -> None:
    """Continuously push vehicle state to Home Assistant (runs until Ctrl+C).

    tesla ha sync
    tesla ha sync --interval 30
    """
    import json as _json
    from datetime import datetime as _dt

    cfg = load_config()
    v = resolve_vin(cfg, vin)
    url = cfg.home_assistant.url
    token = cfg.home_assistant.token

    if not url or not token:
        console.print(
            "[red]Home Assistant not configured.[/red]\n"
            "Run: [bold]tesla ha setup <URL> <TOKEN>[/bold]"
        )
        raise typer.Exit(1)

    notifier = None
    if notify:
        try:
            import apprise

            notifier = apprise.Apprise()
            notifier.add(notify)
        except ImportError:
            console.print("[yellow]⚠ apprise not installed — notifications disabled[/yellow]")

    console.print(
        f"[bold cyan]HA sync[/bold cyan]  interval=[bold]{interval}s[/bold]  "
        f"target=[bold]{url}[/bold]\n"
        "Press [bold]Ctrl+C[/bold] to stop.\n"
    )

    push_count = 0
    error_count = 0

    try:
        while True:
            ts = _dt.now().strftime("%H:%M:%S")
            try:
                data = _with_wake(lambda b, vv: b.get_vehicle_data(vv), v)
                results = _push_all(data, url, token, v)
                ok = sum(1 for r in results if r["status"] == "ok")
                errs = sum(1 for r in results if r["status"] == "error")
                push_count += 1
                error_count += errs

                batt = (data.get("charge_state") or {}).get("battery_level", "?")
                locked = (data.get("vehicle_state") or {}).get("locked", "?")
                climate = (data.get("climate_state") or {}).get("is_climate_on", False)

                if is_json_mode():
                    console.print(
                        _json.dumps(
                            {
                                "ts": ts,
                                "push": push_count,
                                "entities_ok": ok,
                                "entities_error": errs,
                            }
                        )
                    )
                else:
                    err_str = f"  [red]{errs} err[/red]" if errs else ""
                    console.print(
                        f"  [dim]{ts}[/dim]  "
                        f"🔋 [bold]{batt}%[/bold]  "
                        f"🔒 {'yes' if locked else 'no'}  "
                        f"🌡️ {'on' if climate else 'off'}  "
                        f"[dim]{ok} entities → HA[/dim]{err_str}"
                    )
                if errs and notifier:
                    notifier.notify(title="HA sync error", body=f"{errs} entity push(es) failed")

            except Exception as exc:  # noqa: BLE001
                error_count += 1
                console.print(f"  [dim]{ts}[/dim]  [red]Error:[/red] {exc}")
                if notifier:
                    try:
                        notifier.notify(title="HA sync error", body=str(exc))
                    except Exception:  # noqa: BLE001
                        pass

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print(
            f"\n[dim]HA sync stopped.[/dim]  "
            f"[bold]{push_count}[/bold] pushes  "
            f"[bold]{error_count}[/bold] errors"
        )
