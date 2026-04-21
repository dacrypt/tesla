"""Energy pricing backend — electricity tariffs by location."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

CITY_COORDS: dict[str, tuple[float, float]] = {
    "bogota": (4.711, -74.072),
    "medellin": (6.244, -75.574),
    "cali": (3.437, -76.522),
    "barranquilla": (10.964, -74.796),
    "cartagena": (10.390, -75.514),
    "bucaramanga": (7.120, -73.122),
    "pereira": (4.813, -75.696),
    "manizales": (5.070, -75.517),
}

# Fallback static tariff data (COP/kWh) when openquery is unavailable.
# Values are approximate 2024 residential rates per estrato.
_FALLBACK_TARIFFS: dict[str, list[dict]] = {
    "bogota": [
        {"estrato": 1, "valor_kwh": 398.0, "empresa": "Enel Colombia", "municipio": "Bogotá"},
        {"estrato": 2, "valor_kwh": 466.0, "empresa": "Enel Colombia", "municipio": "Bogotá"},
        {"estrato": 3, "valor_kwh": 548.0, "empresa": "Enel Colombia", "municipio": "Bogotá"},
        {"estrato": 4, "valor_kwh": 648.0, "empresa": "Enel Colombia", "municipio": "Bogotá"},
        {"estrato": 5, "valor_kwh": 810.0, "empresa": "Enel Colombia", "municipio": "Bogotá"},
        {"estrato": 6, "valor_kwh": 810.0, "empresa": "Enel Colombia", "municipio": "Bogotá"},
    ],
    "medellin": [
        {"estrato": 1, "valor_kwh": 354.0, "empresa": "EPM", "municipio": "Medellín"},
        {"estrato": 2, "valor_kwh": 412.0, "empresa": "EPM", "municipio": "Medellín"},
        {"estrato": 3, "valor_kwh": 486.0, "empresa": "EPM", "municipio": "Medellín"},
        {"estrato": 4, "valor_kwh": 574.0, "empresa": "EPM", "municipio": "Medellín"},
        {"estrato": 5, "valor_kwh": 717.0, "empresa": "EPM", "municipio": "Medellín"},
        {"estrato": 6, "valor_kwh": 717.0, "empresa": "EPM", "municipio": "Medellín"},
    ],
    "cali": [
        {"estrato": 1, "valor_kwh": 376.0, "empresa": "EMCALI", "municipio": "Cali"},
        {"estrato": 2, "valor_kwh": 440.0, "empresa": "EMCALI", "municipio": "Cali"},
        {"estrato": 3, "valor_kwh": 518.0, "empresa": "EMCALI", "municipio": "Cali"},
        {"estrato": 4, "valor_kwh": 612.0, "empresa": "EMCALI", "municipio": "Cali"},
        {"estrato": 5, "valor_kwh": 765.0, "empresa": "EMCALI", "municipio": "Cali"},
        {"estrato": 6, "valor_kwh": 765.0, "empresa": "EMCALI", "municipio": "Cali"},
    ],
    "barranquilla": [
        {"estrato": 1, "valor_kwh": 412.0, "empresa": "Air-e", "municipio": "Barranquilla"},
        {"estrato": 2, "valor_kwh": 482.0, "empresa": "Air-e", "municipio": "Barranquilla"},
        {"estrato": 3, "valor_kwh": 567.0, "empresa": "Air-e", "municipio": "Barranquilla"},
        {"estrato": 4, "valor_kwh": 670.0, "empresa": "Air-e", "municipio": "Barranquilla"},
        {"estrato": 5, "valor_kwh": 837.0, "empresa": "Air-e", "municipio": "Barranquilla"},
        {"estrato": 6, "valor_kwh": 837.0, "empresa": "Air-e", "municipio": "Barranquilla"},
    ],
    "cartagena": [
        {"estrato": 1, "valor_kwh": 420.0, "empresa": "Afinia", "municipio": "Cartagena"},
        {"estrato": 2, "valor_kwh": 491.0, "empresa": "Afinia", "municipio": "Cartagena"},
        {"estrato": 3, "valor_kwh": 578.0, "empresa": "Afinia", "municipio": "Cartagena"},
        {"estrato": 4, "valor_kwh": 683.0, "empresa": "Afinia", "municipio": "Cartagena"},
        {"estrato": 5, "valor_kwh": 854.0, "empresa": "Afinia", "municipio": "Cartagena"},
        {"estrato": 6, "valor_kwh": 854.0, "empresa": "Afinia", "municipio": "Cartagena"},
    ],
    "bucaramanga": [
        {"estrato": 1, "valor_kwh": 365.0, "empresa": "ESSA", "municipio": "Bucaramanga"},
        {"estrato": 2, "valor_kwh": 427.0, "empresa": "ESSA", "municipio": "Bucaramanga"},
        {"estrato": 3, "valor_kwh": 503.0, "empresa": "ESSA", "municipio": "Bucaramanga"},
        {"estrato": 4, "valor_kwh": 594.0, "empresa": "ESSA", "municipio": "Bucaramanga"},
        {"estrato": 5, "valor_kwh": 742.0, "empresa": "ESSA", "municipio": "Bucaramanga"},
        {"estrato": 6, "valor_kwh": 742.0, "empresa": "ESSA", "municipio": "Bucaramanga"},
    ],
    "pereira": [
        {"estrato": 1, "valor_kwh": 358.0, "empresa": "CHEC", "municipio": "Pereira"},
        {"estrato": 2, "valor_kwh": 419.0, "empresa": "CHEC", "municipio": "Pereira"},
        {"estrato": 3, "valor_kwh": 493.0, "empresa": "CHEC", "municipio": "Pereira"},
        {"estrato": 4, "valor_kwh": 582.0, "empresa": "CHEC", "municipio": "Pereira"},
        {"estrato": 5, "valor_kwh": 728.0, "empresa": "CHEC", "municipio": "Pereira"},
        {"estrato": 6, "valor_kwh": 728.0, "empresa": "CHEC", "municipio": "Pereira"},
    ],
    "manizales": [
        {"estrato": 1, "valor_kwh": 361.0, "empresa": "CHEC", "municipio": "Manizales"},
        {"estrato": 2, "valor_kwh": 422.0, "empresa": "CHEC", "municipio": "Manizales"},
        {"estrato": 3, "valor_kwh": 497.0, "empresa": "CHEC", "municipio": "Manizales"},
        {"estrato": 4, "valor_kwh": 587.0, "empresa": "CHEC", "municipio": "Manizales"},
        {"estrato": 5, "valor_kwh": 734.0, "empresa": "CHEC", "municipio": "Manizales"},
        {"estrato": 6, "valor_kwh": 734.0, "empresa": "CHEC", "municipio": "Manizales"},
    ],
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two GPS points."""
    from tesla_cli.core.geo import haversine_km

    return haversine_km(lat1, lon1, lat2, lon2)


def nearest_city(lat: float, lon: float) -> str:
    """Find nearest Colombian city to given coordinates."""
    best_city = "bogota"
    best_dist = float("inf")
    for city, (clat, clon) in CITY_COORDS.items():
        dist = _haversine_km(lat, lon, clat, clon)
        if dist < best_dist:
            best_dist = dist
            best_city = city
    return best_city


def get_tariffs(ciudad: str, estrato: int = 0) -> list[dict]:
    """Return electricity tariffs for a city, optionally filtered by estrato.

    Tries openquery first; falls back to static data if unavailable.
    estrato=0 returns all estratos.
    """
    ciudad_key = ciudad.lower().strip()

    # Try openquery first
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        src = get_source("co.tarifas_energia")
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number=ciudad_key,
                extra={"ciudad": ciudad_key, "estrato": estrato},
            )
        )
        data = result.model_dump(exclude={"audit"})
        tariffs = data.get("tariffs") or data.get("items") or []
        if tariffs:
            if estrato > 0:
                tariffs = [t for t in tariffs if t.get("estrato") == estrato]
            return tariffs
    except Exception:
        logger.warning(
            "Failed to fetch dynamic energy prices, using fallback tariffs", exc_info=True
        )
        # Fall through to static data

    # Fallback: static tariff table
    fallback = _FALLBACK_TARIFFS.get(ciudad_key, _FALLBACK_TARIFFS["bogota"])
    if estrato > 0:
        fallback = [t for t in fallback if t.get("estrato") == estrato]
    return fallback


def get_vehicle_location() -> tuple[float | None, float | None]:
    """Get vehicle GPS coordinates from vehicle backend or config.

    Returns (lat, lon) or (None, None) if unavailable.
    """
    try:
        from tesla_cli.core.backends import get_vehicle_backend
        from tesla_cli.core.config import load_config, resolve_vin

        cfg = load_config()
        vin = resolve_vin(cfg)
        backend = get_vehicle_backend(cfg)
        data = backend.get_vehicle_data(vin)
        ds = data.get("drive_state") or {}
        lat = ds.get("latitude")
        lon = ds.get("longitude")
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    except Exception:
        logger.warning("Failed to resolve vehicle location for energy pricing", exc_info=True)
    return None, None
