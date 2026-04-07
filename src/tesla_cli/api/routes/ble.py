"""BLE API routes: /api/ble/*"""

from __future__ import annotations

import shutil
import subprocess

from fastapi import APIRouter, HTTPException

from tesla_cli.core.config import load_config, resolve_vin

router = APIRouter()

_INSTALL_HINT = (
    "go install github.com/teslamotors/vehicle-command/cmd/tesla-control@latest"
    " (requires Go >=1.21)"
)


def _tesla_control_bin() -> str | None:
    return shutil.which("tesla-control")


def _run_ble_cmd(cmd: str) -> dict:
    """Run `tesla-control -ble -vin <VIN> <cmd>` and return result dict."""
    cfg = load_config()
    v = resolve_vin(cfg, None)
    binary = _tesla_control_bin()
    if not binary:
        raise HTTPException(
            status_code=501,
            detail=f"tesla-control binary not found. Install: {_INSTALL_HINT}",
        )

    args = [binary, "-ble"]
    if v:
        args += ["-vin", v]
    if cfg.ble.key_path:
        args += ["-key-file", cfg.ble.key_path]
    args.append(cmd)

    try:
        result = subprocess.run(  # noqa: S603
            args,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="tesla-control timed out (30s)")

    ok = result.returncode == 0
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()

    if not ok:
        raise HTTPException(status_code=502, detail=err or "BLE command failed")

    return {
        "ok": True,
        "command": cmd,
        "vin": v,
        "stdout": out,
    }


@router.get("/status")
def ble_status() -> dict:
    """BLE connection status and key configuration."""
    cfg = load_config()
    binary = _tesla_control_bin()
    return {
        "tesla_control_found": binary is not None,
        "tesla_control_path": binary or None,
        "key_configured": bool(cfg.ble.key_path),
        "key_path": cfg.ble.key_path or None,
        "ble_mac": cfg.ble.ble_mac or None,
    }


@router.post("/lock")
def ble_lock() -> dict:
    """Lock vehicle via BLE."""
    return _run_ble_cmd("lock")


@router.post("/unlock")
def ble_unlock() -> dict:
    """Unlock vehicle via BLE."""
    return _run_ble_cmd("unlock")


@router.post("/climate/on")
def ble_climate_on() -> dict:
    """Turn climate on via BLE."""
    return _run_ble_cmd("climate-on")


@router.post("/climate/off")
def ble_climate_off() -> dict:
    """Turn climate off via BLE."""
    return _run_ble_cmd("climate-off")


@router.post("/charge/start")
def ble_charge_start() -> dict:
    """Start charging via BLE."""
    return _run_ble_cmd("charging-start")


@router.post("/charge/stop")
def ble_charge_stop() -> dict:
    """Stop charging via BLE."""
    return _run_ble_cmd("charging-stop")
