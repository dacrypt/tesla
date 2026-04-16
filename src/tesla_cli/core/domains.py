"""Derived domain projections built from cached source snapshots."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from tesla_cli.core.config import CONFIG_DIR
from tesla_cli.core.sources import get_cached_with_meta, get_source_def, list_sources

DOMAINS_DIR = CONFIG_DIR / "domains"


def list_domains() -> list[dict[str, Any]]:
    """Recompute and return all supported domain projections."""
    return [recompute_domain(domain_id) for domain_id in _DOMAIN_BUILDERS]


def get_domain(domain_id: str) -> dict[str, Any] | None:
    """Recompute and return one domain projection."""
    if domain_id not in _DOMAIN_BUILDERS:
        return None
    return recompute_domain(domain_id)


def recompute_domain(domain_id: str) -> dict[str, Any]:
    """Recompute and persist a domain projection."""
    previous_projection = _load_domain(domain_id)
    projection = _DOMAIN_BUILDERS[domain_id]()
    _save_domain(domain_id, projection)
    try:
        from tesla_cli.core import events

        events.emit_domain_change(domain_id, projection, previous_projection)
    except Exception:
        logging.getLogger(__name__).debug("Domain event emission failed for %s", domain_id, exc_info=True)
    return projection


def _save_domain(domain_id: str, projection: dict[str, Any]) -> None:
    DOMAINS_DIR.mkdir(parents=True, exist_ok=True)
    (DOMAINS_DIR / f"{domain_id}.json").write_text(json.dumps(projection, default=str, indent=2))


def _load_domain(domain_id: str) -> dict[str, Any] | None:
    path = DOMAINS_DIR / f"{domain_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        logging.getLogger(__name__).debug("Failed to load domain cache", exc_info=True)
        return None


def _build_delivery() -> dict[str, Any]:
    order = _get_input("tesla.order")
    portal = _get_input("tesla.portal")
    ship = _get_input("intl.ship_tracking")

    order_data = order["data"] or {}
    portal_data = portal["data"] or {}
    ship_data = ship["data"] or {}

    vin = _first_value(order_data, "vin")
    order_status = _first_value(order_data, "orderStatus", "order_status")
    order_substatus = _first_value(order_data, "orderSubstatus", "order_substatus")
    estimated_delivery = _first_value(
        order_data,
        "delivery.estimatedDeliveryDate",
        "delivery.deliveryWindowStart",
        "estimatedDeliveryDate",
        "estimated_delivery",
    )
    appointment_date = _first_value(
        portal_data,
        "delivery_details.deliveryAppointmentDateUtc",
        "delivery.deliveryAppointmentDateUtc",
        "delivery.appointmentDateUtc",
    ) or _first_value(order_data, "delivery.appointmentDateUtc")
    appointment_text = _first_value(
        portal_data,
        "delivery_details.deliveryTiming.appointment",
        "delivery.deliveryTiming.appointment",
        "delivery.appointment",
    ) or _first_value(order_data, "delivery.appointment")
    delivery_location = _first_value(
        portal_data,
        "delivery_details.deliveryTiming.pickupLocationTitle",
        "delivery.deliveryTiming.pickupLocationTitle",
        "delivery.location",
    ) or _first_value(order_data, "delivery.location")
    ship_name = _first_value(ship_data, "ship", "vessel", "name")

    delivery_scheduled = bool(appointment_date or appointment_text)
    health = _compute_health([order, portal, ship])
    summary_bits = []
    if delivery_scheduled:
        summary_bits.append(f"Delivery scheduled{f' for {appointment_date[:10]}' if appointment_date else ''}")
    elif estimated_delivery:
        summary_bits.append(f"Estimated delivery {str(estimated_delivery)[:10]}")
    if vin:
        summary_bits.append(f"VIN assigned ({vin[-6:]})")
    if delivery_location:
        summary_bits.append(f"Pickup: {delivery_location}")
    if ship_name:
        summary_bits.append(f"Ship: {ship_name}")

    return {
        "domain_id": "delivery",
        "computed_at": _now(),
        "inputs": [order, portal, ship],
        "state": {
            "order_status": order_status,
            "order_substatus": order_substatus,
            "vin": vin,
            "estimated_delivery": estimated_delivery,
            "delivery_date": appointment_date,
            "delivery_appointment": appointment_text,
            "delivery_location": delivery_location,
            "ship_name": ship_name,
        },
        "derived_flags": {
            "has_order_data": bool(order_data),
            "has_portal_data": bool(portal_data),
            "vin_assigned": bool(vin),
            "delivery_scheduled": delivery_scheduled,
            "has_ship_tracking": bool(ship_data),
        },
        "summary": (
            f"Last known: {' · '.join(summary_bits)}"
            if summary_bits and health.get("status") != "ok"
            else " · ".join(summary_bits)
            if summary_bits
            else "No verified delivery data yet"
        ),
        "health": health,
    }


def _build_legal() -> dict[str, Any]:
    runt = _get_input("co.runt")
    soat = _get_input("co.runt_soat")
    rtm = _get_input("co.runt_rtm")
    simit = _get_input("co.simit")

    runt_data = runt["data"] or {}
    soat_data = soat["data"] or {}
    rtm_data = rtm["data"] or {}
    simit_data = simit["data"] or {}

    plate = _first_value(runt_data, "placa", "plate")
    owner_id = _first_value(runt_data, "no_identificacion", "documento", "cedula")
    lien_count = _count_value(_first_value(runt_data, "gravamenes", "liens", "gravamen"))
    comparendos = _coerce_number(
        _first_value(simit_data, "comparendos", "multas", "total_multas", "cantidad")
    )
    total_deuda = _first_value(simit_data, "total_deuda", "deuda_total", "saldo_total")

    soat_valid = _truthy_value(_first_value(soat_data, "soat_vigente", "vigente", "estado"))
    rtm_valid = _truthy_value(
        _first_value(rtm_data, "tecnico_mecanica_vigente", "rtm_vigente", "vigente", "estado")
    )

    health = _compute_health([runt, soat, rtm, simit])
    summary_bits = []
    if plate:
        summary_bits.append(f"Plate assigned: {plate}")
    if soat_valid is True:
        summary_bits.append("SOAT valid")
    elif soat_valid is False and soat_data:
        summary_bits.append("SOAT missing or expired")
    if rtm_valid is True:
        summary_bits.append("RTM valid")
    elif rtm_valid is False and rtm_data:
        summary_bits.append("RTM missing or expired")
    if comparendos and comparendos > 0:
        summary_bits.append(f"{comparendos} fine(s)")
    if lien_count > 0:
        summary_bits.append(f"{lien_count} lien(s)")

    return {
        "domain_id": "legal",
        "computed_at": _now(),
        "inputs": [runt, soat, rtm, simit],
        "state": {
            "plate": plate,
            "owner_id": owner_id,
            "lien_count": lien_count,
            "soat_valid": soat_valid,
            "rtm_valid": rtm_valid,
            "fines_count": comparendos,
            "fines_total": total_deuda,
        },
        "derived_flags": {
            "runt_registered": bool(runt_data),
            "plate_assigned": bool(plate),
            "has_soat": soat_valid is True,
            "has_rtm": rtm_valid is True,
            "has_fines": bool(comparendos and comparendos > 0),
            "has_liens": lien_count > 0,
        },
        "summary": (
            f"Last known: {' · '.join(summary_bits)}"
            if summary_bits and health.get("status") != "ok"
            else " · ".join(summary_bits)
            if summary_bits
            else "No verified legal data yet"
        ),
        "health": health,
    }


def _build_safety() -> dict[str, Any]:
    nhtsa_recalls = _get_input("us.nhtsa_recalls")
    nhtsa_complaints = _get_input("us.nhtsa_complaints")
    nhtsa_investigations = _get_input("us.nhtsa_investigations")
    co_recalls = _get_input("co.recalls")

    recalls_data = nhtsa_recalls["data"] or {}
    complaints_data = nhtsa_complaints["data"] or {}
    investigations_data = nhtsa_investigations["data"] or {}
    local_recalls_data = co_recalls["data"] or {}

    recalls_count = _extract_count(recalls_data, "count", "total", array_keys=("recalls", "results"))
    complaints_count = _extract_count(
        complaints_data, "count", "total", array_keys=("complaints", "results")
    )
    investigations_count = _extract_count(
        investigations_data, "count", "total", array_keys=("investigations", "results")
    )
    local_recalls_count = _extract_count(
        local_recalls_data, "count", "total", array_keys=("recalls", "results")
    )

    health = _compute_health([nhtsa_recalls, nhtsa_complaints, nhtsa_investigations, co_recalls])
    summary_bits = []
    if recalls_count:
        summary_bits.append(f"{recalls_count} NHTSA model-year recall(s)")
    if local_recalls_count:
        summary_bits.append(f"{local_recalls_count} local recall(s)")
    if investigations_count:
        summary_bits.append(f"{investigations_count} investigation(s)")
    if complaints_count:
        summary_bits.append(f"{complaints_count} complaint(s)")

    return {
        "domain_id": "safety",
        "computed_at": _now(),
        "inputs": [nhtsa_recalls, nhtsa_complaints, nhtsa_investigations, co_recalls],
        "state": {
            "nhtsa_recalls_count": recalls_count,
            "local_recalls_count": local_recalls_count,
            "complaints_count": complaints_count,
            "investigations_count": investigations_count,
        },
        "derived_flags": {
            "has_open_recalls": (recalls_count + local_recalls_count) > 0,
            "has_complaints": complaints_count > 0,
            "has_investigations": investigations_count > 0,
        },
        "summary": (
            f"Last known: {' · '.join(summary_bits)}"
            if summary_bits and health.get("status") != "ok"
            else " · ".join(summary_bits)
            if summary_bits
            else "No verified safety signals detected"
        ),
        "health": health,
    }


def _build_financial() -> dict[str, Any]:
    portal = _get_input("tesla.portal")
    order = _get_input("tesla.order")
    fasecolda = _get_input("co.fasecolda")
    simit = _get_input("co.simit")

    portal_data = portal["data"] or {}
    order_data = order["data"] or {}
    fasecolda_data = fasecolda["data"] or {}
    simit_data = simit["data"] or {}

    payment_method = _first_value(
        portal_data,
        "payment_method",
        "financing.paymentMethod",
        "financing.payment_method",
        "order.payment_method",
    ) or _first_value(order_data, "paymentMethod", "payment_method")
    lender = _first_value(
        portal_data,
        "financing.lender",
        "financing.bank",
        "lender",
    ) or _first_value(order_data, "financing.lender", "financing.bank")
    final_payment_status = _first_value(
        portal_data,
        "financing.finalPaymentStatus",
        "financing.final_payment_status",
        "financing.status",
    )
    commercial_value = _first_value(
        fasecolda_data,
        "valor_comercial",
        "valor",
        "precio",
        "avaluo",
    )
    fines_total = _first_value(simit_data, "total_deuda", "deuda_total", "saldo_total")
    fines_count = _coerce_number(
        _first_value(simit_data, "comparendos", "multas", "cantidad", "count")
    )

    health = _compute_health([portal, order, fasecolda, simit])
    summary_bits = []
    if payment_method:
        summary_bits.append(f"Payment: {payment_method}")
    if lender:
        summary_bits.append(f"Lender: {lender}")
    if final_payment_status:
        summary_bits.append(f"Final payment: {final_payment_status}")
    if commercial_value not in (None, "", [], {}):
        summary_bits.append(f"Value: {commercial_value}")
    if fines_count and fines_count > 0:
        summary_bits.append(f"Fines debt: {fines_total}")

    if not summary_bits and not portal_data:
        summary = "Manual Tesla portal refresh required for financing details"
    elif not summary_bits:
        summary = "No verified financial data yet"
    elif health.get("status") != "ok":
        summary = f"Last known: {' · '.join(summary_bits)}"
    else:
        summary = " · ".join(summary_bits)

    return {
        "domain_id": "financial",
        "computed_at": _now(),
        "inputs": [portal, order, fasecolda, simit],
        "state": {
            "payment_method": payment_method,
            "lender": lender,
            "final_payment_status": final_payment_status,
            "commercial_value": commercial_value,
            "fines_total": fines_total,
            "fines_count": fines_count,
        },
        "derived_flags": {
            "has_financing": bool(payment_method or lender),
            "has_valuation": commercial_value not in (None, "", [], {}),
            "has_fines_debt": bool(fines_count and fines_count > 0),
            "portal_refresh_required": not bool(portal_data),
        },
        "summary": summary,
        "health": health,
    }


def _build_identity() -> dict[str, Any]:
    order = _get_input("tesla.order")
    vin_decode = _get_input("vin.decode")
    nhtsa_vin = _get_input("us.nhtsa_vin")
    portal = _get_input("tesla.portal")

    order_data = order["data"] or {}
    vin_data = vin_decode["data"] or {}
    nhtsa_data = nhtsa_vin["data"] or {}
    portal_data = portal["data"] or {}

    vin = _first_value(order_data, "vin") or _first_value(vin_data, "vin") or _first_value(
        nhtsa_data, "vin"
    )
    model = _first_value(vin_data, "model", "vehicle", "model_name") or _first_value(
        nhtsa_data, "model", "vehicle", "model_name"
    ) or _first_value(order_data, "modelCode", "model")
    model_year = _first_value(vin_data, "model_year", "modelYear", "year") or _first_value(
        nhtsa_data, "model_year", "modelYear", "year"
    )
    manufacturer = _first_value(vin_data, "manufacturer", "make") or _first_value(
        nhtsa_data, "manufacturer", "make"
    )
    plant = _first_value(vin_data, "plant") or _first_value(nhtsa_data, "plant")
    color = _first_value(
        portal_data,
        "vehicle.color",
        "vehicle_info.color",
        "configuration.color",
    )

    health = _compute_health([order, vin_decode, nhtsa_vin, portal])
    summary_bits = []
    if vin:
        summary_bits.append(f"VIN …{str(vin)[-6:]}")
    if model:
        summary_bits.append(str(model))
    if model_year:
        summary_bits.append(str(model_year))
    if manufacturer:
        summary_bits.append(str(manufacturer))
    if plant:
        summary_bits.append(f"Plant: {plant}")

    return {
        "domain_id": "identity",
        "computed_at": _now(),
        "inputs": [order, vin_decode, nhtsa_vin, portal],
        "state": {
            "vin": vin,
            "model": model,
            "model_year": model_year,
            "manufacturer": manufacturer,
            "plant": plant,
            "color": color,
        },
        "derived_flags": {
            "has_vin": bool(vin),
            "has_decoded_identity": bool(model or manufacturer or plant),
            "has_color": bool(color),
        },
        "summary": (
            f"Last known: {' · '.join(summary_bits)}"
            if summary_bits and health.get("status") != "ok"
            else " · ".join(summary_bits)
            if summary_bits
            else "No verified identity data yet"
        ),
        "health": health,
    }


def _build_source_health() -> dict[str, Any]:
    entries = list_sources()
    health_entries = [item for item in entries if item.get("auto_refresh", True)]
    total_sources = len(health_entries)
    ok_sources = sum(
        1 for item in health_entries if not item.get("stale") and not item.get("error")
    )
    stale_sources = [item["id"] for item in health_entries if item.get("stale")]
    error_sources = [item["id"] for item in health_entries if item.get("error")]
    degraded_sources = sorted(set(stale_sources + error_sources))
    manual_sources = [item["id"] for item in entries if not item.get("auto_refresh", True)]

    by_category: dict[str, dict[str, int]] = {}
    for item in health_entries:
        category = item.get("category") or "other"
        bucket = by_category.setdefault(category, {"total": 0, "ok": 0, "degraded": 0})
        bucket["total"] += 1
        if item.get("stale") or item.get("error"):
            bucket["degraded"] += 1
        else:
            bucket["ok"] += 1

    status = "ok" if ok_sources == total_sources else "degraded" if ok_sources else "missing"
    summary = (
        f"{ok_sources}/{total_sources} sources healthy"
        if total_sources
        else "No sources registered"
    )

    return {
        "domain_id": "source_health",
        "computed_at": _now(),
        "inputs": [],
        "state": {
            "ok_sources": ok_sources,
            "total_sources": total_sources,
            "stale_sources": stale_sources,
            "error_sources": error_sources,
            "manual_sources": manual_sources,
            "by_category": by_category,
        },
        "derived_flags": {
            "has_degraded_sources": bool(degraded_sources),
            "has_error_sources": bool(error_sources),
            "has_stale_sources": bool(stale_sources),
        },
        "summary": summary,
        "health": {
            "status": status,
            "ok_sources": ok_sources,
            "total_sources": total_sources,
            "degraded_sources": degraded_sources,
        },
    }


def _get_input(source_id: str) -> dict[str, Any]:
    source = get_cached_with_meta(source_id)
    src_def = get_source_def(source_id)
    raw_data = source.get("data") if source else None
    error = source.get("error") if source else None
    stale = source.get("stale", True) if source else True
    status = "error" if error else "stale" if stale else "ok" if raw_data else "missing"
    return {
        "source_id": source_id,
        "name": src_def.name if src_def else source_id,
        "category": src_def.category if src_def else "",
        "refreshed_at": source.get("refreshed_at") if source else None,
        "status": status,
        "stale": stale,
        "error": error,
        "has_data": raw_data is not None,
        "verified": status == "ok",
        "last_known_data": raw_data,
        "data": raw_data,
    }


def _compute_health(inputs: list[dict[str, Any]]) -> dict[str, Any]:
    ok = sum(1 for item in inputs if item["status"] == "ok")
    degraded = [item["source_id"] for item in inputs if item["status"] in {"error", "stale"}]
    if ok == len(inputs):
        status = "ok"
    elif ok == 0:
        status = "missing"
    else:
        status = "degraded"
    return {
        "status": status,
        "ok_sources": ok,
        "total_sources": len(inputs),
        "degraded_sources": degraded,
    }


def _first_value(data: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        value = _nested_get(data, path)
        if value not in (None, "", [], {}):
            return value
    return None


def _nested_get(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _truthy_value(value: Any) -> bool | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "si", "sí", "vigente", "active", "ok"}:
        return True
    if text in {"false", "no", "expired", "expirado", "vencido", "inactive"}:
        return False
    return None


def _coerce_number(value: Any) -> int | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(char for char in str(value) if char.isdigit())
    return int(digits) if digits else None


def _count_value(value: Any) -> int:
    if value in (None, "", False):
        return 0
    if isinstance(value, list):
        return len(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 1


def _extract_count(data: dict[str, Any], *count_keys: str, array_keys: tuple[str, ...] = ()) -> int:
    for key in count_keys:
        value = _coerce_number(_nested_get(data, key))
        if value is not None:
            return value
    for key in array_keys:
        value = _nested_get(data, key)
        if isinstance(value, list):
            return len(value)
    return 0


def _now() -> str:
    return datetime.now(UTC).isoformat()


_DOMAIN_BUILDERS = {
    "delivery": _build_delivery,
    "financial": _build_financial,
    "identity": _build_identity,
    "legal": _build_legal,
    "safety": _build_safety,
    "source_health": _build_source_health,
}
