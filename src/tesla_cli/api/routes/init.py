"""Init API route: /api/init — single payload for app startup.

Returns everything the frontend needs in one request: all source data
for the configured country, computed fields (real_status, specs),
geolocation, auth, automations, and vehicle state.
No dossier dependency — reads source caches directly.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request

from tesla_cli.core.config import load_config

router = APIRouter()
log = logging.getLogger("tesla-cli.init")


@router.get("")
def app_init(request: Request) -> dict:
    """Bundle all data needed for initial app render.

    Returns {sources, computed, location, auth, automations, vehicle}.
    Each section is best-effort — failures return null/empty, not errors.
    """
    cfg = load_config()
    vin = cfg.general.default_vin or ""
    country = cfg.general.country or "CO"

    result: dict = {
        "sources": {},
        "computed": {
            "real_status": None,
            "specs": None,
        },
        "location": None,
        "drivers": [],
        "auth": None,
        "automations": None,
        "vehicle": None,
    }

    # ── All sources for this country (read from cache, no API calls) ──

    order_data = None
    runt_data = None

    try:
        from tesla_cli.core.sources import _SOURCES, get_cached

        for sid, src in _SOURCES.items():
            if src.country in ("", country):
                cached = get_cached(sid)
                if cached is not None:
                    result["sources"][sid] = cached
                    # Track specific sources for computed fields
                    if sid == "tesla.order":
                        order_data = cached
                    elif sid == "co.runt":
                        runt_data = cached
    except Exception as exc:
        log.debug("Init: source cache read failed: %s", exc)

    # ── Geolocation (vehicle GPS → delivery cache → default) ──

    try:
        result["location"] = _resolve_location(request, cfg)
    except Exception as exc:
        log.debug("Init: location resolution failed: %s", exc)

    # ── Computed fields ──

    try:
        from tesla_cli.core.computed import compute_real_status, compute_specs

        # Delivery info from cache
        delivery_date = ""
        delivery_location = ""
        delivery_appointment = ""
        try:
            from tesla_cli.core.backends.order import DELIVERY_CACHE_FILE

            if DELIVERY_CACHE_FILE.exists():
                dc = json.loads(DELIVERY_CACHE_FILE.read_text())
                # Try top-level fields first, then nested delivery_details
                dd = dc.get("delivery_details", {})
                dt = dd.get("deliveryTiming", {})
                raw_date = dc.get("date_utc") or dd.get("deliveryAppointmentDateUtc") or ""
                delivery_date = raw_date[:10] if raw_date else ""
                delivery_location = dc.get("location_name") or dt.get("pickupLocationTitle") or ""
                delivery_appointment = dc.get("appointment_text") or dt.get("appointment") or ""
        except Exception:
            logging.getLogger(__name__).debug("Delivery date resolution failed", exc_info=True)

        result["computed"]["real_status"] = compute_real_status(
            order_data=order_data,
            runt_data=runt_data,
            vin=vin,
            delivery_date=delivery_date,
            delivery_location=delivery_location,
            delivery_appointment=delivery_appointment,
        )

        # Option codes from order data
        option_codes_raw = ""
        if order_data:
            mkt = order_data.get("mktOptions") or order_data.get("optionCodes") or ""
            if isinstance(mkt, list):
                option_codes_raw = ",".join(
                    str(o.get("code", o) if isinstance(o, dict) else o) for o in mkt
                )
            elif isinstance(mkt, str):
                option_codes_raw = mkt

        result["computed"]["specs"] = compute_specs(vin=vin, option_codes_raw=option_codes_raw)
    except Exception as exc:
        log.debug("Init: computed fields failed: %s", exc)

    # ── Auth status ──

    try:
        from tesla_cli.core.auth.tokens import (
            FLEET_ACCESS_TOKEN,
            ORDER_ACCESS_TOKEN,
            TESSIE_TOKEN,
            has_token,
        )

        result["auth"] = {
            "authenticated": has_token(FLEET_ACCESS_TOKEN)
            or has_token(TESSIE_TOKEN)
            or has_token(ORDER_ACCESS_TOKEN),
            "backend": cfg.general.backend,
            "has_fleet": has_token(FLEET_ACCESS_TOKEN),
            "has_order": has_token(ORDER_ACCESS_TOKEN),
            "has_tessie": has_token(TESSIE_TOKEN),
        }
    except Exception as exc:
        log.debug("Init: auth check failed: %s", exc)

    # ── Automations status ──

    try:
        from tesla_cli.core.automations import AutomationEngine

        engine = AutomationEngine()
        engine.load()
        enabled = sum(1 for r in engine.rules if r.enabled)
        result["automations"] = {
            "total": len(engine.rules),
            "enabled": enabled,
        }
    except Exception as exc:
        log.debug("Init: automations check failed: %s", exc)

    # ── Drivers for this vehicle ──

    try:
        from tesla_cli.core.db import get_vehicle_drivers

        if vin:
            result["drivers"] = get_vehicle_drivers(vin)
    except Exception as exc:
        log.debug("Init: drivers load failed: %s", exc)

    # ── Vehicle state from hub (no API call) ──

    hub = getattr(request.app.state, "vehicle_hub", None)
    if hub:
        latest = hub.get_latest()
        if latest:
            result["vehicle"] = latest
        elif hub.is_pre_delivery():
            result["vehicle"] = {"_pre_delivery": True}

    return result


def _resolve_location(request: Request, cfg) -> dict:
    """Resolve vehicle/user location with fallback chain.

    Priority: vehicle GPS → delivery cache → config → default (bogota).
    """
    from tesla_cli.core.backends.energy_prices import CITY_COORDS, nearest_city

    # 1. Try vehicle GPS from hub
    hub = getattr(request.app.state, "vehicle_hub", None)
    if hub:
        latest = hub.get_latest()
        if latest:
            ds = latest.get("drive_state") or {}
            lat = ds.get("latitude")
            lon = ds.get("longitude")
            if lat is not None and lon is not None:
                city = nearest_city(float(lat), float(lon))
                return {
                    "lat": float(lat),
                    "lon": float(lon),
                    "city": city,
                    "source": "vehicle_gps",
                }

    # 2. Try delivery cache location
    try:
        from tesla_cli.core.backends.order import DELIVERY_CACHE_FILE

        if DELIVERY_CACHE_FILE.exists():
            dc = json.loads(DELIVERY_CACHE_FILE.read_text())
            dd = dc.get("delivery_details", {})
            dt = dd.get("deliveryTiming", {})
            loc_name = dc.get("location_name") or dt.get("pickupLocationTitle") or ""
            # Parse city from location name (e.g., "Tesla Medellin Centro de Entrega")
            for city_key in CITY_COORDS:
                if city_key in loc_name.lower():
                    clat, clon = CITY_COORDS[city_key]
                    return {
                        "lat": clat,
                        "lon": clon,
                        "city": city_key,
                        "source": "delivery_cache",
                    }
    except Exception:
        logging.getLogger(__name__).debug(
            "Location resolution from delivery cache failed", exc_info=True
        )

    # 3. Default: bogota
    clat, clon = CITY_COORDS.get("bogota", (4.711, -74.072))
    return {
        "lat": clat,
        "lon": clon,
        "city": "bogota",
        "source": "default",
    }
