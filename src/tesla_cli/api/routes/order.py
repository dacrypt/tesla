"""Order API routes: /api/order/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.config import load_config

router = APIRouter()


@router.get("/status")
def order_status() -> dict:
    """Current order / delivery status."""
    from tesla_cli.backends.order import OrderBackend
    cfg = load_config()
    rn  = cfg.order.reservation_number
    if not rn:
        raise HTTPException(status_code=404, detail="No reservation number configured.")
    try:
        backend = OrderBackend(rn)
        return backend.get_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
