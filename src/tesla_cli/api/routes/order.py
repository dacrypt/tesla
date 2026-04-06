"""Order API routes: /api/order/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.core.config import load_config

router = APIRouter()


@router.get("/status")
def order_status() -> dict:
    """Current order / delivery status."""
    from tesla_cli.core.backends.order import OrderBackend

    cfg = load_config()
    rn = cfg.order.reservation_number
    if not rn:
        raise HTTPException(status_code=404, detail="No reservation number configured.")
    try:
        backend = OrderBackend()
        status = backend.get_order_status(rn)
        return status.model_dump() if hasattr(status, "model_dump") else status
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/details")
def order_details() -> dict:
    """Full order details including tasks, financing, registration, delivery."""
    from tesla_cli.core.backends.order import OrderBackend

    cfg = load_config()
    rn = cfg.order.reservation_number
    if not rn:
        raise HTTPException(status_code=404, detail="No reservation number configured.")
    try:
        backend = OrderBackend()
        details = backend.get_order_details(rn)
        return {
            "status": details.status.model_dump(),
            "tasks": [t.model_dump() for t in details.tasks],
            "financing": details.financing,
            "registration": details.registration,
            "delivery": details.delivery,
            "vehicle_info": details.vehicle_info,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
