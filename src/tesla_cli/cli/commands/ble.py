"""BLE commands: tesla ble lock|unlock|climate-on|climate-off|charge-start|charge-stop|status.

L0 layer — direct Bluetooth Low Energy control via the `tesla-control` binary.
Works without internet or Tesla server connectivity.

Requires: https://github.com/teslamotors/vehicle-command (tesla-control binary)
Install:  go install github.com/teslamotors/vehicle-command/cmd/tesla-control@latest
"""

from __future__ import annotations

import shutil
import subprocess

import typer

from tesla_cli.core.config import load_config, resolve_vin, save_config
from tesla_cli.core.exceptions import ExternalToolNotFoundError
from tesla_cli.cli.output import console, is_json_mode, render_success

ble_app = typer.Typer(
    name="ble",
    help="BLE direct control via tesla-control (no internet required).",
)

VinOption = typer.Option(None, "--vin", "-v", help="VIN or alias")

_INSTALL_HINT = (
    "go install github.com/teslamotors/vehicle-command/cmd/tesla-control@latest\n"
    "  (requires Go ≥1.21)  https://github.com/teslamotors/vehicle-command"
)


def _tesla_control_bin() -> str:
    """Return path to tesla-control or raise ExternalToolNotFoundError."""
    path = shutil.which("tesla-control")
    if not path:
        raise ExternalToolNotFoundError("tesla-control", _INSTALL_HINT)
    return path


def _vin(vin: str | None) -> str:
    return resolve_vin(load_config(), vin)


def _run_ble(cmd: str, vin: str) -> dict:
    """Run `tesla-control -ble -vin <VIN> <cmd>` and return result dict."""

    cfg      = load_config()
    key_path = cfg.ble.key_path
    binary   = _tesla_control_bin()

    args = [binary, "-ble"]
    if vin:
        args += ["-vin", vin]
    if key_path:
        args += ["-key-file", key_path]
    args.append(cmd)

    try:
        result = subprocess.run(  # noqa: S603
            args,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "tesla-control timed out (30s)"}

    ok = result.returncode == 0
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()

    return {
        "status":    "ok" if ok else "error",
        "command":   cmd,
        "vin":       vin,
        "returncode": result.returncode,
        "stdout":    out,
        "stderr":    err,
    }


def _print_result(result: dict, success_msg: str) -> None:
    import json as _json
    if is_json_mode():
        console.print(_json.dumps(result, indent=2))
        return
    if result["status"] == "ok":
        render_success(success_msg)
        if result.get("stdout"):
            console.print(f"  [dim]{result['stdout']}[/dim]")
    else:
        msg = result.get("stderr") or result.get("message") or "Unknown error"
        console.print(f"[red]BLE command failed:[/red] {msg}")
        raise typer.Exit(1)


# ──────────────────────────────────────────────────────────────────────────────


@ble_app.command("lock")
def ble_lock(vin: str | None = VinOption) -> None:
    """Lock vehicle via BLE (no internet required).

    tesla ble lock
    tesla -j ble lock
    """
    v = _vin(vin)
    result = _run_ble("lock", v)
    _print_result(result, "Vehicle locked via BLE 🔒")


@ble_app.command("unlock")
def ble_unlock(vin: str | None = VinOption) -> None:
    """Unlock vehicle via BLE (no internet required)."""
    v = _vin(vin)
    result = _run_ble("unlock", v)
    _print_result(result, "Vehicle unlocked via BLE 🔓")


@ble_app.command("climate-on")
def ble_climate_on(vin: str | None = VinOption) -> None:
    """Turn climate on via BLE."""
    v = _vin(vin)
    result = _run_ble("climate-on", v)
    _print_result(result, "Climate on via BLE 🌡️")


@ble_app.command("climate-off")
def ble_climate_off(vin: str | None = VinOption) -> None:
    """Turn climate off via BLE."""
    v = _vin(vin)
    result = _run_ble("climate-off", v)
    _print_result(result, "Climate off via BLE")


@ble_app.command("charge-start")
def ble_charge_start(vin: str | None = VinOption) -> None:
    """Start charging via BLE."""
    v = _vin(vin)
    result = _run_ble("charging-start", v)
    _print_result(result, "Charging started via BLE ⚡")


@ble_app.command("charge-stop")
def ble_charge_stop(vin: str | None = VinOption) -> None:
    """Stop charging via BLE."""
    v = _vin(vin)
    result = _run_ble("charging-stop", v)
    _print_result(result, "Charging stopped via BLE")


@ble_app.command("flash")
def ble_flash(vin: str | None = VinOption) -> None:
    """Flash headlights via BLE."""
    v = _vin(vin)
    result = _run_ble("flash-lights", v)
    _print_result(result, "Headlights flashed via BLE 💡")


@ble_app.command("honk")
def ble_honk(vin: str | None = VinOption) -> None:
    """Honk horn via BLE."""
    v = _vin(vin)
    result = _run_ble("honk", v)
    _print_result(result, "Horn honked via BLE 📯")


@ble_app.command("status")
def ble_status() -> None:
    """Show BLE configuration and tesla-control availability.

    tesla ble status
    tesla -j ble status
    """
    import json as _json

    cfg    = load_config()
    binary = shutil.which("tesla-control")

    data = {
        "tesla_control_found": binary is not None,
        "tesla_control_path":  binary or "",
        "key_path_set":        bool(cfg.ble.key_path),
        "key_path":            cfg.ble.key_path or "",
        "ble_mac":             cfg.ble.ble_mac or "",
    }

    if is_json_mode():
        console.print(_json.dumps(data, indent=2))
        return

    from rich.table import Table
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("k", style="dim", width=26)
    t.add_column("v")
    found_str  = f"[green]found[/green] [dim]({binary})[/dim]" if binary else "[red]not found[/red]"
    t.add_row("tesla-control binary", found_str)
    t.add_row("BLE key path", cfg.ble.key_path or "[dim]not set[/dim]")
    t.add_row("BLE MAC",      cfg.ble.ble_mac  or "[dim]auto-detect[/dim]")
    console.print(t)

    if not binary:
        console.print(
            f"\n[yellow]tesla-control not found.[/yellow]\n"
            f"Install: [bold]{_INSTALL_HINT}[/bold]"
        )
    elif not cfg.ble.key_path:
        console.print(
            "\n[yellow]BLE key not configured.[/yellow]  "
            "Run: [bold]tesla ble setup-key[/bold]"
        )


@ble_app.command("setup-key")
def ble_setup_key(
    key_path: str = typer.Argument(..., help="Path to tesla-control private key .pem file"),
    ble_mac: str = typer.Option("", "--mac", help="Vehicle BLE MAC address (optional)"),
) -> None:
    """Configure BLE private key path for tesla-control.

    tesla ble setup-key ~/.tesla/private.pem
    """
    from pathlib import Path
    p = Path(key_path).expanduser()
    if not p.exists():
        raise typer.BadParameter(f"Key file not found: {p}")
    cfg = load_config()
    cfg.ble.key_path = str(p)
    if ble_mac:
        cfg.ble.ble_mac = ble_mac
    save_config(cfg)
    render_success(f"BLE key configured: {p}")
