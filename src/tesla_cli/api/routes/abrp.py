"""ABRP API routes: /api/abrp/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from tesla_cli.core.config import load_config, resolve_vin

router = APIRouter()

_ABRP_API = "https://api.iternio.com/1/tlm/send"


@router.get("/status")
def abrp_status() -> dict:
    """ABRP connection status and configuration."""
    cfg = load_config()
    return {
        "user_token_set": bool(cfg.abrp.user_token),
        "api_key_set": bool(cfg.abrp.api_key),
        "configured": bool(cfg.abrp.user_token),
        "abrp_api": _ABRP_API,
    }


@router.get("/config")
def abrp_config() -> dict:
    """Get ABRP configuration (api_key configured, user_token set)."""
    cfg = load_config()
    return {
        "user_token_set": bool(cfg.abrp.user_token),
        "api_key_set": bool(cfg.abrp.api_key),
        "abrp_api": _ABRP_API,
    }


@router.post("/send")
def abrp_send(request: Request) -> dict:
    """Send current vehicle telemetry to ABRP."""
    cfg = load_config()

    if not cfg.abrp.user_token:
        raise HTTPException(
            status_code=400,
            detail="ABRP user token not configured. Run: tesla config set abrp-user-token <TOKEN>",
        )

    try:
        from tesla_cli.core.backends import get_vehicle_backend

        v = resolve_vin(cfg, request.app.state.override_vin)
        backend = get_vehicle_backend(cfg)
        data = backend.get_vehicle_data(v)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to get vehicle data: {exc}")

    try:
        from tesla_cli.core.providers.impl.abrp import AbrpProvider

        provider = AbrpProvider(cfg)
        result = provider.execute("push", data=data)
        if not result.ok:
            raise HTTPException(status_code=502, detail=result.error or "ABRP push failed")
        return {
            "ok": True,
            "telemetry": result.data.get("tlm") if result.data else {},
            "abrp_response": result.data.get("response") if result.data else {},
            "latency_ms": result.latency_ms,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
