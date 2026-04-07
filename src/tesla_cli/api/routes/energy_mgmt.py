"""Energy management API: /api/energy/mgmt/* — Powerwall/Solar site control."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.core.backends.energy import load_energy_backend
from tesla_cli.core.config import load_config

router = APIRouter()


def _site_id(site_id: int) -> int:
    """Resolve site_id — if 0, fall back to config."""
    if site_id:
        return site_id
    cfg = load_config()
    configured = getattr(cfg.energy, "site_id", 0) if hasattr(cfg, "energy") else 0
    return configured or 0


@router.get("/sites")
def energy_sites() -> list:
    """List all energy sites (Powerwall / Solar installations)."""
    try:
        backend = load_energy_backend()
        return backend.list_energy_sites()
    except Exception as exc:
        raise HTTPException(502, f"Energy sites unavailable: {exc}") from exc


@router.get("/status")
def energy_status(site_id: int = 0) -> dict:
    """Live power flow — solar, battery, grid, home."""
    try:
        backend = load_energy_backend()
        resolved = _site_id(site_id)
        if not resolved:
            # Try first available site
            sites = backend.list_energy_sites()
            if not sites:
                raise HTTPException(404, "No energy sites configured")
            resolved = sites[0].get("energy_site_id", 0)
        return backend.live_status(resolved)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Energy status unavailable: {exc}") from exc


@router.get("/info")
def energy_info(site_id: int = 0) -> dict:
    """Site configuration and asset info."""
    try:
        backend = load_energy_backend()
        resolved = _site_id(site_id)
        if not resolved:
            sites = backend.list_energy_sites()
            if not sites:
                raise HTTPException(404, "No energy sites configured")
            resolved = sites[0].get("energy_site_id", 0)
        return backend.get_site_info(resolved)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Energy info unavailable: {exc}") from exc


@router.get("/history")
def energy_history(site_id: int = 0, period: str = "day") -> dict:
    """Energy production/consumption history."""
    try:
        backend = load_energy_backend()
        resolved = _site_id(site_id)
        if not resolved:
            sites = backend.list_energy_sites()
            if not sites:
                raise HTTPException(404, "No energy sites configured")
            resolved = sites[0].get("energy_site_id", 0)
        return backend.energy_history(resolved, period=period)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Energy history unavailable: {exc}") from exc


@router.post("/backup")
def set_backup(site_id: int, percent: int) -> dict:
    """Set backup reserve percentage (0–100)."""
    if not 0 <= percent <= 100:
        raise HTTPException(422, "percent must be between 0 and 100")
    try:
        backend = load_energy_backend()
        return backend.set_backup_reserve(site_id, percent)
    except Exception as exc:
        raise HTTPException(502, f"Set backup reserve failed: {exc}") from exc


@router.post("/mode")
def set_mode(site_id: int, mode: str) -> dict:
    """Set operation mode: self_consumption | autonomous | backup."""
    valid_modes = {"self_consumption", "autonomous", "backup"}
    if mode not in valid_modes:
        raise HTTPException(422, f"mode must be one of: {', '.join(sorted(valid_modes))}")
    try:
        backend = load_energy_backend()
        return backend.set_operation_mode(site_id, mode)
    except Exception as exc:
        raise HTTPException(502, f"Set operation mode failed: {exc}") from exc


@router.post("/storm")
def set_storm(site_id: int, enabled: bool) -> dict:
    """Enable or disable storm watch mode."""
    try:
        backend = load_energy_backend()
        return backend.set_storm_mode(site_id, enabled)
    except Exception as exc:
        raise HTTPException(502, f"Set storm mode failed: {exc}") from exc
