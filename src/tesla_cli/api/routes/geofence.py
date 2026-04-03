"""Geofence API routes: /api/geofences/*"""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin

router = APIRouter()


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two GPS points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.get("")
def geofence_list(request: Request) -> list[dict]:
    """List all geofence zones with current vehicle distance.

    Returns each zone's name, center coordinates, radius, and vehicle proximity.
    """
    cfg = load_config()
    zones = cfg.geofences.zones

    # Try to get vehicle location
    vehicle_lat, vehicle_lon = None, None
    try:
        vin_override = request.query_params.get("vin") or request.app.state.override_vin
        v = resolve_vin(cfg, vin_override)
        backend = get_vehicle_backend(cfg)
        drive = backend.get_drive_state(v)
        vehicle_lat = drive.get("latitude")
        vehicle_lon = drive.get("longitude")
    except Exception:
        pass

    result = []
    for name, zone in zones.items():
        entry: dict = {
            "name": name,
            "lat": zone.get("lat"),
            "lon": zone.get("lon"),
            "radius_km": zone.get("radius_km", 0.2),
        }
        if vehicle_lat is not None and vehicle_lon is not None:
            dist = _haversine(vehicle_lat, vehicle_lon, zone["lat"], zone["lon"])
            entry["distance_km"] = round(dist, 3)
            entry["inside"] = dist <= zone.get("radius_km", 0.2)
        result.append(entry)

    return result


@router.get("/{name}")
def geofence_status(name: str, request: Request) -> dict:
    """Check if the vehicle is inside a specific geofence zone."""
    cfg = load_config()
    zones = cfg.geofences.zones

    if name not in zones:
        raise HTTPException(status_code=404, detail=f"Zone '{name}' not found.")

    zone = zones[name]

    try:
        vin_override = request.query_params.get("vin") or request.app.state.override_vin
        v = resolve_vin(cfg, vin_override)
        backend = get_vehicle_backend(cfg)
        drive = backend.get_drive_state(v)
        lat = drive.get("latitude")
        lon = drive.get("longitude")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cannot get vehicle location: {exc}")

    if lat is None or lon is None:
        raise HTTPException(status_code=503, detail="No GPS data available.")

    dist = _haversine(lat, lon, zone["lat"], zone["lon"])

    return {
        "zone": name,
        "zone_lat": zone["lat"],
        "zone_lon": zone["lon"],
        "radius_km": zone.get("radius_km", 0.2),
        "vehicle_lat": lat,
        "vehicle_lon": lon,
        "distance_km": round(dist, 3),
        "inside": dist <= zone.get("radius_km", 0.2),
    }


class AddZoneRequest(BaseModel):
    lat: float
    lon: float
    radius_km: float = 0.2


@router.post("/{name}")
def geofence_add(name: str, body: AddZoneRequest) -> dict:
    """Add or update a geofence zone."""
    from tesla_cli.core.config import save_config

    cfg = load_config()
    cfg.geofences.zones[name] = {
        "lat": body.lat,
        "lon": body.lon,
        "radius_km": body.radius_km,
    }
    save_config(cfg)
    return {"status": "ok", "zone": name, "total_zones": len(cfg.geofences.zones)}


@router.delete("/{name}")
def geofence_remove(name: str) -> dict:
    """Remove a geofence zone."""
    from tesla_cli.core.config import save_config

    cfg = load_config()
    if name not in cfg.geofences.zones:
        raise HTTPException(status_code=404, detail=f"Zone '{name}' not found.")
    del cfg.geofences.zones[name]
    save_config(cfg)
    return {"status": "ok", "removed": name, "remaining_zones": len(cfg.geofences.zones)}
