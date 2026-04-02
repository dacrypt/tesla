"""ABRP commands: tesla abrp send|stream|status|setup.

A Better Route Planner (ABRP) live telemetry integration.
Pushes real-time vehicle state (SoC, speed, power, GPS, charging) to ABRP
so it can give accurate range predictions while driving.
"""

from __future__ import annotations

import time

import typer

from tesla_cli.cli.commands.vehicle import _with_wake
from tesla_cli.cli.output import console, is_json_mode, render_success
from tesla_cli.core.config import load_config, resolve_vin, save_config

abrp_app = typer.Typer(
    name="abrp",
    help="A Better Route Planner (ABRP) live telemetry integration.",
)

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")

_ABRP_API = "https://api.iternio.com/1/tlm/send"


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


def _build_tlm(data: dict) -> dict:
    """Extract ABRP telemetry fields from full vehicle_data response."""
    cs = data.get("charge_state") or {}
    ds = data.get("drive_state") or {}
    clim = data.get("climate_state") or {}

    soc = cs.get("battery_level")
    speed = ds.get("speed") or 0  # mph (Tesla API native)
    power = ds.get("power") or 0  # kW (negative = regen)
    lat = ds.get("latitude")
    lon = ds.get("longitude")
    is_charging = cs.get("charging_state") in ("Charging", "Complete")
    charger_pwr = cs.get("charger_power") or 0  # kW

    tlm: dict = {"utc": int(time.time())}
    if soc is not None:
        tlm["soc"] = soc
    tlm["speed"] = round(speed * 1.60934, 1)  # convert mph → km/h
    tlm["power"] = power
    tlm["is_charging"] = int(is_charging)
    tlm["charger_power"] = charger_pwr
    if lat is not None:
        tlm["lat"] = lat
    if lon is not None:
        tlm["lon"] = lon
    # Optionally include interior temp
    inside_temp = clim.get("inside_temp")
    if inside_temp is not None:
        tlm["temp"] = inside_temp

    return tlm


def _push(cfg, tlm: dict) -> dict:
    """POST telemetry to ABRP API. Returns parsed JSON response."""
    import json as _json

    try:
        import urllib.request as _req
    except ImportError:
        raise RuntimeError("urllib not available")

    user_token = cfg.abrp.user_token
    api_key = cfg.abrp.api_key

    if not user_token:
        raise typer.BadParameter(
            "ABRP user token not configured.\n"
            "Run: tesla config set abrp-user-token <TOKEN>\n"
            "(Get your token from ABRP app → Share → Live Data / API)"
        )

    params = f"token={user_token}"
    if api_key:
        params += f"&api_key={api_key}"

    url = f"{_ABRP_API}?{params}"
    payload = _json.dumps({"tlm": tlm}).encode()
    req = _req.Request(url, data=payload, headers={"Content-Type": "application/json"})

    with _req.urlopen(req, timeout=10) as resp:  # noqa: S310
        return _json.loads(resp.read().decode())


# ──────────────────────────────────────────────────────────────────────────────


@abrp_app.command("send")
def abrp_send(vin: str | None = VinOption) -> None:
    """Push current vehicle state to ABRP (one-shot).

    tesla abrp send
    tesla -j abrp send
    """
    import json as _json

    cfg = load_config()
    v = _vin(vin)
    data = _with_wake(lambda b, vv: b.get_vehicle_data(vv), v)
    tlm = _build_tlm(data)
    resp = _push(cfg, tlm)

    if is_json_mode():
        console.print(_json.dumps({"telemetry": tlm, "abrp_response": resp}, indent=2))
        return

    status = resp.get("status", "unknown")
    soc = tlm.get("soc", "?")
    speed = tlm.get("speed", 0)
    power = tlm.get("power", 0)
    charging = "yes" if tlm.get("is_charging") else "no"
    console.print(
        f"[green]✓[/green] ABRP telemetry sent  "
        f"SoC [bold]{soc}%[/bold]  "
        f"Speed [bold]{speed} km/h[/bold]  "
        f"Power [bold]{power} kW[/bold]  "
        f"Charging [bold]{charging}[/bold]  "
        f"[dim]status={status}[/dim]"
    )


@abrp_app.command("stream")
def abrp_stream(
    interval: int = typer.Option(
        30, "--interval", "-i", help="Push interval in seconds (default 30)"
    ),
    notify: str = typer.Option("", "--notify", help="Apprise URL for error alerts"),
    vin: str | None = VinOption,
) -> None:
    """Continuously push vehicle state to ABRP (runs until Ctrl+C).

    tesla abrp stream
    tesla abrp stream --interval 60
    """
    import json as _json

    cfg = load_config()
    v = _vin(vin)

    console.print(
        f"[bold cyan]ABRP live stream[/bold cyan]  "
        f"interval=[bold]{interval}s[/bold]  "
        "Press [bold]Ctrl+C[/bold] to stop.\n"
    )

    push_count = 0
    error_count = 0

    try:
        while True:
            ts = int(time.time())
            try:
                data = _with_wake(lambda b, vv: b.get_vehicle_data(vv), v)
                tlm = _build_tlm(data)
                resp = _push(cfg, tlm)
                push_count += 1
                soc = tlm.get("soc", "?")
                speed = tlm.get("speed", 0)
                power = tlm.get("power", 0)
                status = resp.get("status", "?")
                if is_json_mode():
                    console.print(
                        _json.dumps(
                            {
                                "ts": ts,
                                "push": push_count,
                                "telemetry": tlm,
                                "abrp_response": resp,
                            }
                        )
                    )
                else:
                    from datetime import datetime

                    ts_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                    console.print(
                        f"[dim]{ts_str}[/dim]  "
                        f"SoC [bold]{soc}%[/bold]  "
                        f"Speed [bold]{speed} km/h[/bold]  "
                        f"Power [bold]{power:+.0f} kW[/bold]  "
                        f"[dim]status={status} push={push_count}[/dim]"
                    )
            except Exception as exc:  # noqa: BLE001
                error_count += 1
                console.print(f"[red]Push #{push_count + 1} failed:[/red] {exc}")
                if notify:
                    try:
                        import apprise as _apprise  # type: ignore[import]

                        a = _apprise.Apprise()
                        a.add(notify)
                        a.notify(title="ABRP stream error", body=str(exc))
                    except Exception:  # noqa: BLE001
                        pass

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print(
            f"\n[dim]Stopped.[/dim]  "
            f"[bold]{push_count}[/bold] pushes  "
            f"[bold]{error_count}[/bold] errors"
        )


@abrp_app.command("status")
def abrp_status() -> None:
    """Show ABRP configuration status.

    tesla abrp status
    tesla -j abrp status
    """
    import json as _json

    cfg = load_config()
    has_user_token = bool(cfg.abrp.user_token)
    has_api_key = bool(cfg.abrp.api_key)

    if is_json_mode():
        console.print(
            _json.dumps(
                {
                    "user_token_set": has_user_token,
                    "api_key_set": has_api_key,
                    "abrp_api": _ABRP_API,
                }
            )
        )
        return

    from rich.table import Table

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("k", style="dim", width=22)
    t.add_column("v")
    t.add_row("User Token", "[green]set[/green]" if has_user_token else "[red]not set[/red]")
    t.add_row("API Key", "[green]set[/green]" if has_api_key else "[dim]not set (optional)[/dim]")
    t.add_row("API Endpoint", f"[dim]{_ABRP_API}[/dim]")
    console.print(t)

    if not has_user_token:
        console.print(
            "\n[yellow]To configure:[/yellow]\n"
            "  1. Open ABRP → Profile → share icon → Live Data / API\n"
            "  2. Copy your token and run:\n"
            "     [bold]tesla config set abrp-user-token <TOKEN>[/bold]"
        )


@abrp_app.command("setup")
def abrp_setup(
    user_token: str = typer.Argument(..., help="ABRP user token (from ABRP app → share → API)"),
    api_key: str = typer.Option("", "--api-key", help="Developer API key (optional)"),
) -> None:
    """Configure ABRP integration tokens.

    tesla abrp setup <USER_TOKEN>
    tesla abrp setup <USER_TOKEN> --api-key <DEV_KEY>
    """
    cfg = load_config()
    cfg.abrp.user_token = user_token
    if api_key:
        cfg.abrp.api_key = api_key
    save_config(cfg)
    render_success(
        "ABRP configured." + (" API key saved." if api_key else "") + "\nTest with: tesla abrp send"
    )
