"""Order API routes: /api/order/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.core.config import load_config

router = APIRouter()


@router.get("/summary")
def order_summary() -> dict:
    """Human-readable order status summary."""
    from tesla_cli.core.backends.order import OrderBackend, generate_summary

    cfg = load_config()
    rn = cfg.order.reservation_number
    if not rn:
        raise HTTPException(status_code=404, detail="No reservation number configured.")
    try:
        backend = OrderBackend()
        status = backend.get_order_status(rn)
        summary = generate_summary(status)
        return {"summary": summary, "reservation_number": rn}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/share")
def order_share(include_vin: bool = False) -> dict:
    """Shareable formatted order status text."""
    from tesla_cli.core.backends.order import (
        OrderBackend,
        format_share_text,
        generate_summary,
    )

    cfg = load_config()
    rn = cfg.order.reservation_number
    if not rn:
        raise HTTPException(status_code=404, detail="No reservation number configured.")
    try:
        backend = OrderBackend()
        status = backend.get_order_status(rn)
        summary = generate_summary(status)
        text = format_share_text(status, summary, include_vin=include_vin)
        return {"text": text, "summary": summary}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/status")
def order_status_with_summary() -> dict:
    """Current order status with summary."""
    from tesla_cli.core.backends.order import OrderBackend, generate_summary

    cfg = load_config()
    rn = cfg.order.reservation_number
    if not rn:
        raise HTTPException(status_code=404, detail="No reservation number configured.")
    try:
        backend = OrderBackend()
        status = backend.get_order_status(rn)
        summary = generate_summary(status)
        result = status.model_dump() if hasattr(status, "model_dump") else status
        result["summary"] = summary
        return result
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

        # Enrich delivery with _details data from raw order (Owner API)
        delivery = dict(details.delivery)
        raw = details.status.raw or {}
        raw_details = raw.get("_details", {})
        scheduling = {}
        if isinstance(raw_details, dict):
            tasks_raw = raw_details.get("tasks", {})
            if isinstance(tasks_raw, dict):
                scheduling = tasks_raw.get("scheduling", {})
            # Merge Owner API scheduling data into delivery
            if isinstance(scheduling, dict) and scheduling.get("deliveryAddressTitle"):
                delivery.setdefault("location", scheduling.get("deliveryAddressTitle", ""))
                delivery.setdefault("address", scheduling.get("deliveryAddressDetail", ""))
                delivery.setdefault("appointmentDateUtc", scheduling.get("appointmentDate", ""))
                delivery.setdefault("mapUrl", raw_details.get("schedulingMapUrl", ""))
                delivery.setdefault("deliveryType", raw_details.get("schedulingDeliveryType", ""))
                delivery.setdefault("readyToAccept", scheduling.get("readyToAccept", False))
                delivery.setdefault("vehicleIsReady", False)
                delivery.setdefault("withinAppointmentWindow", False)
                da = tasks_raw.get("deliveryAcceptance", {})
                if isinstance(da, dict):
                    delivery["vehicleIsReady"] = da.get("vehicleIsReady", False)
                    delivery["withinAppointmentWindow"] = da.get("withinAppointmentWindow", False)
            # Amount due from financing
            financing_raw = raw_details.get("financing", {})
            if isinstance(financing_raw, dict) and financing_raw.get("amountDueCustomer") is not None:
                delivery.setdefault("amountDue", financing_raw["amountDueCustomer"])

        return {
            "status": details.status.model_dump(),
            "tasks": [t.model_dump() for t in details.tasks],
            "financing": details.financing,
            "registration": details.registration,
            "delivery": delivery,
            "vehicle_info": details.vehicle_info,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
