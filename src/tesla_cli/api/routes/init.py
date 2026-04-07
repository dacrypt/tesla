"""Init API route: /api/init — single payload for app startup.

Returns everything the frontend needs in one request to avoid
waterfall loading and UI flicker on page open.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from tesla_cli.core.config import load_config

router = APIRouter()
log = logging.getLogger("tesla-cli.init")


@router.get("")
def app_init(request: Request) -> dict:
    """Bundle all data needed for initial app render.

    Returns {dossier, auth, automations, vehicle} in a single response.
    Each section is best-effort — failures return null, not errors.
    """
    result: dict = {
        "dossier": None,
        "auth": None,
        "automations": None,
        "vehicle": None,
    }

    # Dossier (disk read, <100ms)
    try:
        from tesla_cli.core.backends.dossier import DossierBackend

        backend = DossierBackend()
        dossier = backend._load_dossier()
        if dossier:
            result["dossier"] = dossier.model_dump(mode="json")
    except Exception as exc:
        log.debug("Init: dossier load failed: %s", exc)

    # Auth status
    try:
        from tesla_cli.core.auth.tokens import (
            FLEET_ACCESS_TOKEN,
            ORDER_ACCESS_TOKEN,
            TESSIE_TOKEN,
            has_token,
        )

        cfg = load_config()
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

    # Automations status
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

    # Vehicle state from hub (no API call)
    hub = getattr(request.app.state, "vehicle_hub", None)
    if hub:
        latest = hub.get_latest()
        if latest:
            result["vehicle"] = latest
        elif hub.is_pre_delivery():
            result["vehicle"] = {"_pre_delivery": True}

    return result
