"""Vehicle API routes: /api/vehicle/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.exceptions import VehicleAsleepError

router = APIRouter()


def _backend_and_vin(request: Request):
    cfg = load_config()
    vin_override = request.query_params.get("vin") or request.app.state.override_vin
    v = resolve_vin(cfg, vin_override)
    return get_vehicle_backend(cfg), v


# ── Read endpoints ────────────────────────────────────────────────────────────


@router.get("/state")
def vehicle_state(request: Request) -> dict:
    """Full vehicle data (all states)."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_vehicle_data(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep. Call /wake first.")


@router.get("/location")
def vehicle_location(request: Request) -> dict:
    """Drive state including GPS location."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_drive_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/charge")
def vehicle_charge(request: Request) -> dict:
    """Charge state."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_charge_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/climate")
def vehicle_climate(request: Request) -> dict:
    """Climate state."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_climate_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/vehicle-state")
def vehicle_vehicle_state(request: Request) -> dict:
    """Vehicle state (locks, doors, software, etc.)."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_vehicle_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/list")
def vehicle_list(request: Request) -> list:
    """List all vehicles on the account."""
    backend, _ = _backend_and_vin(request)
    try:
        return backend.list_vehicles()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Command endpoint ──────────────────────────────────────────────────────────


class CommandRequest(BaseModel):
    command: str
    params: dict = {}


@router.get("/odometer")
def vehicle_odometer(request: Request) -> dict:
    """Current odometer reading and software version.

    Returns {vin, odometer_miles, car_version, queried_at}.
    """
    backend, v = _backend_and_vin(request)
    try:
        vs = backend.get_vehicle_state(v)
        from datetime import UTC, datetime

        return {
            "vin": v,
            "odometer_miles": vs.get("odometer"),
            "car_version": vs.get("car_version"),
            "queried_at": datetime.now(UTC).isoformat(),
        }
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/command")
def vehicle_command(body: CommandRequest, request: Request) -> dict:
    """Send a command to the vehicle.

    Commands: lock, unlock, honk_horn, flash_lights, charge_start,
              charge_stop, climate_on, climate_off, wake_up, ...
    """
    backend, v = _backend_and_vin(request)
    try:
        result = backend.command(v, body.command, **body.params)
        return {"status": "ok", "command": body.command, "result": result}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/wake")
def vehicle_wake(request: Request) -> dict:
    """Wake up the vehicle."""
    backend, v = _backend_and_vin(request)
    try:
        result = backend.wake_up(v)
        return {"status": "ok", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary")
def vehicle_summary(request: Request) -> dict:
    """Compact vehicle snapshot: battery, charging, climate, location, locks, software."""
    backend, v = _backend_and_vin(request)
    try:
        data = backend.get_vehicle_data(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")

    cs = data.get("charge_state", {})
    cl = data.get("climate_state", {})
    ds = data.get("drive_state", {})
    vs = data.get("vehicle_state", {})

    range_mi = cs.get("battery_range", 0)
    odo = vs.get("odometer")

    return {
        "vin": v,
        "battery": {
            "level": cs.get("battery_level"),
            "range_km": round(range_mi * 1.60934, 1) if range_mi else None,
            "limit": cs.get("charge_limit_soc"),
            "charging_state": cs.get("charging_state"),
            "charger_power": cs.get("charger_power"),
            "time_to_full_charge": cs.get("time_to_full_charge"),
        },
        "climate": {
            "inside_temp": cl.get("inside_temp"),
            "outside_temp": cl.get("outside_temp"),
            "hvac_on": cl.get("is_climate_on", False),
        },
        "location": {
            "latitude": ds.get("latitude"),
            "longitude": ds.get("longitude"),
            "speed": ds.get("speed"),
            "heading": ds.get("heading"),
        },
        "state": {
            "locked": vs.get("locked", False),
            "sentry_mode": vs.get("sentry_mode", False),
            "software": vs.get("car_version"),
            "odometer_km": round(odo * 1.60934) if odo else None,
        },
    }

@router.get("/alerts")
def vehicle_alerts(request: Request) -> dict:
    """Recent vehicle alerts and fault codes."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_recent_alerts(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/ready")
def vehicle_ready(request: Request) -> dict:
    """Morning check: is the vehicle ready to drive?

    Returns readiness assessment with battery, charge, climate, lock/sentry status,
    and a list of issues (if any).
    """
    backend, v = _backend_and_vin(request)
    try:
        data = backend.get_vehicle_data(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")

    cs = data.get("charge_state") or {}
    cl = data.get("climate_state") or {}
    vs = data.get("vehicle_state") or {}

    level = cs.get("battery_level", 0)
    range_mi = cs.get("battery_range", 0)
    range_km = round(range_mi * 1.60934, 1) if range_mi else 0
    charging = cs.get("charging_state", "Unknown")
    locked = vs.get("locked", False)
    sentry = vs.get("sentry_mode", False)
    inside = cl.get("inside_temp")
    outside = cl.get("outside_temp")
    climate_on = cl.get("is_climate_on", False)
    precond = cl.get("is_preconditioning", False)
    sw_update = vs.get("software_update") or {}

    issues = []
    if level < 20:
        issues.append(f"Low battery: {level}%")
    if charging == "Charging":
        issues.append("Still charging")
    if not locked:
        issues.append("Vehicle unlocked")
    if outside is not None and outside < 5 and not climate_on and not precond:
        issues.append(f"Cold outside ({outside}°C), consider preconditioning")
    if sw_update.get("status", "") not in ("", "available"):
        issues.append("Software update pending")

    return {
        "ready": len(issues) == 0,
        "battery_level": level,
        "range_km": range_km,
        "charging_state": charging,
        "inside_temp": inside,
        "outside_temp": outside,
        "locked": locked,
        "sentry_mode": sentry,
        "preconditioning": precond or climate_on,
        "issues": issues,
    }


@router.get("/last-seen")
def vehicle_last_seen(request: Request) -> dict:
    """When was the vehicle last online?"""
    from datetime import UTC, datetime

    backend, v = _backend_and_vin(request)

    try:
        data = backend.get_vehicle_data(v)
        online = True
    except VehicleAsleepError:
        data = {}
        online = False

    ds = data.get("drive_state") or {}
    gps_ts = ds.get("gps_as_of") or ds.get("timestamp")

    last_seen = None
    ago = None
    if gps_ts:
        try:
            if isinstance(gps_ts, (int, float)):
                last_dt = datetime.fromtimestamp(
                    gps_ts / 1000 if gps_ts > 1e12 else gps_ts, tz=UTC
                )
            else:
                last_dt = datetime.fromisoformat(str(gps_ts))
            last_seen = last_dt.isoformat()
            delta = datetime.now(tz=UTC) - last_dt
            ago = int(delta.total_seconds())
        except (ValueError, TypeError, OSError):
            pass

    return {
        "state": "online" if online else "asleep",
        "last_seen": last_seen,
        "ago_seconds": ago,
    }
