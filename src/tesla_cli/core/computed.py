"""Computed vehicle fields — pure functions that derive status and specs from sources.

These functions take raw source data as input (not a dossier object) and
return structured models. Used by /api/init to compute real_status and
specs without requiring a full dossier build.
"""

from __future__ import annotations

import logging
import re

import httpx

from tesla_cli.core.models.dossier import RealStatus, VehicleSpecs

log = logging.getLogger("tesla-cli.computed")


def compute_real_status(
    order_data: dict | None,
    runt_data: dict | None,
    vin: str = "",
    delivery_date: str = "",
    delivery_location: str = "",
    delivery_appointment: str = "",
) -> dict:
    """Compute actual vehicle status from source data.

    Tesla's API for Colombia stays at BOOKED even when the car is
    in-country, registered in RUNT, and ready for delivery.
    We use multi-source intelligence to determine the real phase.
    """
    rs = RealStatus()

    # Tesla API signal
    if order_data:
        current = order_data.get("current") or order_data
        rs.tesla_api_status = (
            current.get("order_status", "") or order_data.get("orderStatus", "") or ""
        )

    # VIN assigned?
    rs.vin_assigned = bool(vin)

    # RUNT signals
    if runt_data:
        rs.runt_status = runt_data.get("estado", "")
        rs.in_runt = rs.runt_status == "REGISTRADO"
        rs.has_placa = bool(runt_data.get("placa", ""))
        rs.has_soat = bool(runt_data.get("soat_vigente", False))

    # Delivery info
    rs.delivery_date = delivery_date
    rs.delivery_location = delivery_location
    rs.delivery_appointment = delivery_appointment

    # Derive timeline flags
    rs.is_produced = rs.vin_assigned
    rs.is_shipped = rs.in_runt
    rs.is_in_country = rs.in_runt
    rs.is_customs_cleared = rs.in_runt
    rs.is_registered = rs.in_runt
    rs.is_delivery_scheduled = bool(rs.delivery_date)
    rs.is_delivered = rs.has_placa and rs.has_soat

    # Determine phase
    if rs.is_delivered:
        rs.phase = "delivered"
        rs.phase_description = "Entregado — en circulación"
    elif rs.is_delivery_scheduled:
        rs.phase = "delivery_scheduled"
        if rs.delivery_appointment:
            rs.phase_description = rs.delivery_appointment
        elif rs.delivery_location:
            rs.phase_description = (
                f"Entrega programada: {rs.delivery_date} — {rs.delivery_location}"
            )
        else:
            rs.phase_description = f"Entrega programada: {rs.delivery_date}"
    elif rs.is_registered:
        rs.phase = "registered"
        rs.phase_description = "Registrado en RUNT — pendiente matrícula y entrega"
    elif rs.is_in_country:
        rs.phase = "in_country"
        rs.phase_description = "En Colombia — pendiente registro"
    elif rs.is_shipped:
        rs.phase = "shipped"
        rs.phase_description = "En tránsito marítimo"
    elif rs.is_produced:
        rs.phase = "produced"
        rs.phase_description = "Producido — VIN asignado, pendiente envío"
    else:
        rs.phase = "ordered"
        rs.phase_description = "Orden confirmada — en espera"

    return rs.model_dump(mode="json")


def compute_specs(vin: str = "", option_codes_raw: str = "") -> dict:
    """Build vehicle specs from VIN decode and option codes."""
    from tesla_cli.core.backends.dossier import decode_option_codes, decode_vin

    vd = decode_vin(vin) if vin else None
    year = int(vd.model_year) if vd and vd.model_year.isdigit() else 0
    epa = _get_epa_data()

    # Decode option codes
    ext_color = ""
    interior = ""
    wheels = ""
    supercharging = ""
    connectivity = ""
    if option_codes_raw:
        codes = decode_option_codes(option_codes_raw)
        for oc in codes.codes:
            if oc.category == "paint":
                ext_color = oc.description_es
            elif oc.category == "interior":
                interior = oc.description_es
            elif oc.category == "wheels":
                wheels = oc.description_es
            elif oc.category == "charging":
                supercharging = oc.description_es
            elif oc.category == "connectivity":
                connectivity = oc.description_es

    # Motor config from EPA
    ev_motor = epa.get("ev_motor", "")
    if ev_motor:
        motor_config = f"Dual Motor AWD ({ev_motor})"
        kw_values = re.findall(r"(\d+)\s*kW", ev_motor)
        total_kw = sum(int(k) for k in kw_values) if kw_values else 0
        hp = int(total_kw * 1.341) if total_kw else 389
    else:
        motor_config = "Dual Motor AWD (90 kW front + 200 kW rear ACPM)"
        hp = 389

    epa_range_mi = epa.get("range_mi")
    range_km = int(float(epa_range_mi) * 1.60934) if epa_range_mi else 600

    specs = VehicleSpecs(
        model="Model Y",
        variant="Long Range Dual Motor AWD",
        generation="Juniper (2025+ refresh)",
        model_year=year,
        factory=vd.plant if vd else "",
        battery_type=vd.battery_chemistry if vd else "",
        battery_capacity_kwh=79.0,
        range_km=range_km,
        motor_config=motor_config,
        horsepower=hp,
        zero_to_100_kmh=4.8,
        top_speed_kmh=201,
        curb_weight_kg=2029,
        dimensions="4791 x 1981 x 1623 mm",
        seating=5,
        wheels=wheels or '19" Gemini',
        exterior_color=ext_color or "Stealth Grey",
        interior=interior or "Premium Black",
        autopilot_hardware="HW5 (AI5)",
        has_fsd=False,
        supercharging=supercharging or "Pay Per Use",
        connectivity=connectivity or "Standard",
    )
    return specs.model_dump(mode="json")


def _get_epa_data() -> dict:
    """Get EPA specs. Priority: source cache → API → fallback."""
    try:
        from tesla_cli.core.sources import get_cached

        epa = get_cached("us.epa_fuel_economy") or {}
        if epa and epa.get("ev_motor"):
            return epa
    except Exception:
        pass

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://www.fueleconomy.gov/ws/rest/vehicle/49744",
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                raw = resp.json()
                return {
                    "ev_motor": raw.get("evMotor", ""),
                    "range_mi": raw.get("range"),
                    "range_city_mi": raw.get("rangeCity"),
                    "range_hwy_mi": raw.get("rangeHwy"),
                }
    except Exception:
        pass

    return {}
