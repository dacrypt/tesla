"""Fleet API routes: /api/fleet/*"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Request

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config

router = APIRouter()


@router.get("/summary")
def fleet_summary(request: Request) -> list:
    """Get summary status of all configured vehicles.

    Returns list of {vin, alias, battery_level, charging_state, locked, sentry, lat, lon}.
    """
    cfg = load_config()
    aliases = cfg.vehicles.aliases  # {alias: vin}
    default_vin = cfg.general.default_vin

    # Build (alias, vin) pairs
    vins: list[tuple[str, str]] = [(alias, vin) for alias, vin in aliases.items()]
    aliased_vins = set(aliases.values())
    if default_vin and default_vin not in aliased_vins:
        vins.append((f"...{default_vin[-6:]}", default_vin))

    if not vins:
        return []

    backend = get_vehicle_backend(cfg)

    def _fetch(alias: str, vin: str) -> dict:
        try:
            cs = backend.get_charge_state(vin)
            vs = backend.get_vehicle_state(vin)
            ds = backend.get_drive_state(vin)
            return {
                "vin": vin,
                "alias": alias,
                "battery_level": cs.get("battery_level"),
                "battery_range": cs.get("battery_range"),
                "charging_state": cs.get("charging_state"),
                "locked": vs.get("locked"),
                "sentry": vs.get("sentry_mode"),
                "lat": ds.get("latitude"),
                "lon": ds.get("longitude"),
                "error": None,
            }
        except Exception as exc:
            return {
                "vin": vin,
                "alias": alias,
                "battery_level": None,
                "battery_range": None,
                "charging_state": None,
                "locked": None,
                "sentry": None,
                "lat": None,
                "lon": None,
                "error": str(exc),
            }

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(len(vins), 8)) as pool:
        futures = {pool.submit(_fetch, alias, vin): (alias, vin) for alias, vin in vins}
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: r["alias"])
    return results
