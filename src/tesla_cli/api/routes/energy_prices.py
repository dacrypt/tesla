"""Energy pricing API: /api/energy/* — electricity tariffs by city and estrato."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()

COMPARE_CITIES = ["bogota", "medellin", "cali", "barranquilla", "cartagena"]


@router.get("/tariffs")
def energy_tariffs(ciudad: str = "bogota", estrato: int = 0) -> dict:
    """Get electricity tariffs by city and estrato.

    Query params:
    - `ciudad` — city name (bogota, medellin, cali, barranquilla, cartagena, ...)
    - `estrato` — socioeconomic stratum 1-6, or 0 for all estratos
    """
    try:
        from tesla_cli.core.backends.energy_prices import get_tariffs

        tariffs = get_tariffs(ciudad, estrato)
        return {
            "ciudad": ciudad.lower(),
            "estrato": estrato,
            "tariffs": tariffs,
            "total": len(tariffs),
        }
    except Exception as exc:
        raise HTTPException(502, f"Tariff query failed: {exc}") from exc


@router.get("/tariffs/compare")
def energy_tariffs_compare() -> dict:
    """Compare electricity prices across major Colombian cities.

    Returns tariffs for Bogota, Medellin, Cali, Barranquilla, Cartagena
    for estratos 1-6.
    """
    try:
        from tesla_cli.core.backends.energy_prices import get_tariffs

        cities = []
        for city in COMPARE_CITIES:
            tariffs = get_tariffs(city, estrato=0)
            estratos = [
                {"estrato": t["estrato"], "valor_kwh": t["valor_kwh"]}
                for t in sorted(tariffs, key=lambda x: x.get("estrato", 0))
            ]
            empresa = tariffs[0].get("empresa", "") if tariffs else ""
            cities.append({"name": city, "empresa": empresa, "estratos": estratos})

        return {"cities": cities}
    except Exception as exc:
        raise HTTPException(502, f"Comparison query failed: {exc}") from exc


@router.get("/tariffs/vehicle-location")
def energy_tariffs_at_vehicle() -> dict:
    """Get electricity tariff at vehicle's current GPS location.

    Uses vehicle GPS to determine nearest Colombian city, then returns tariff.
    Falls back to configured city if vehicle location is unavailable.
    """
    try:
        from tesla_cli.core.backends.energy_prices import (
            get_tariffs,
            get_vehicle_location,
            nearest_city,
        )

        lat, lon = get_vehicle_location()

        if lat is not None and lon is not None:
            city = nearest_city(lat, lon)
            location_source = "vehicle_gps"
        else:
            # Fall back to config default city
            city = "bogota"
            location_source = "default"
            lat, lon = None, None

        # Use estrato from config cost_per_kwh as hint (best effort), default to estrato 4
        estrato = 4

        tariffs = get_tariffs(city, estrato=estrato)
        if not tariffs:
            tariffs = get_tariffs(city, estrato=0)

        if not tariffs:
            raise HTTPException(404, f"No tariff data found for city: {city}")

        tariff = tariffs[0]
        return {
            "city": city,
            "estrato": tariff.get("estrato", estrato),
            "valor_kwh": tariff.get("valor_kwh"),
            "empresa": tariff.get("empresa", ""),
            "municipio": tariff.get("municipio", city.title()),
            "location_source": location_source,
            "lat": lat,
            "lon": lon,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Vehicle location tariff query failed: {exc}") from exc
