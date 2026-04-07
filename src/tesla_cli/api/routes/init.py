"""Init API route: /api/init — single payload for app startup.

Returns everything the frontend needs in one request: source data,
computed fields (real_status, specs), auth, automations, and vehicle state.
No dossier dependency — reads source caches directly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request

from tesla_cli.core.config import load_config

router = APIRouter()
log = logging.getLogger("tesla-cli.init")


@router.get("")
def app_init(request: Request) -> dict:
    """Bundle all data needed for initial app render.

    Returns {sources, computed, auth, automations, vehicle}.
    Each section is best-effort — failures return null, not errors.
    """
    cfg = load_config()
    vin = cfg.general.default_vin or ""

    result: dict = {
        "sources": {
            "order": None,
            "runt": None,
        },
        "computed": {
            "real_status": None,
            "specs": None,
        },
        "auth": None,
        "automations": None,
        "vehicle": None,
    }

    # ── Sources (read from cache, no API calls) ──

    order_data = None
    runt_data = None

    try:
        from tesla_cli.core.sources import get_cached

        order_data = get_cached("tesla.order")
        result["sources"]["order"] = order_data

        runt_data = get_cached("co.runt")
        result["sources"]["runt"] = runt_data
    except Exception as exc:
        log.debug("Init: source cache read failed: %s", exc)

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
                delivery_date = dc.get("date_utc", "")[:10] if dc.get("date_utc") else ""
                delivery_location = dc.get("location_name", "")
                delivery_appointment = dc.get("appointment_text", "")
        except Exception:
            pass

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

    # ── Vehicle state from hub (no API call) ──

    hub = getattr(request.app.state, "vehicle_hub", None)
    if hub:
        latest = hub.get_latest()
        if latest:
            result["vehicle"] = latest
        elif hub.is_pre_delivery():
            result["vehicle"] = {"_pre_delivery": True}

    return result
