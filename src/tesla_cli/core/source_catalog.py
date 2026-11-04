"""Catalog of registered data sources (Tesla, VIN, NHTSA, country registries).

Split from ``core/sources.py``, which keeps the engine (cache, history,
diffs, refresh). ``register_defaults()`` runs once when ``core.sources`` is
imported. Names tests patch on ``tesla_cli.core.sources`` (config, cache
helpers, directories, ``subprocess``) are looked up as ``_s.<name>``.
"""

from __future__ import annotations

from tesla_cli.core import sources as _s
from tesla_cli.core.sources import (  # noqa: F401
    Any,
    SourceDef,
    _load_cache,
    log,
    register_source,
)

# ── Default source registrations ─────────────────────────────────────────────


def _register_universal() -> None:
    """Register sources that are always active regardless of country."""

    # ── Tesla Portal (full web data) ──
    register_source(
        SourceDef(
            id="tesla.portal",
            name="Tesla Portal — Orden Completa",
            category="financiero",
            requires_auth="order",
            ttl=3600,
            country="",
            auto_refresh=False,
            # Refreshed via /api/auth/portal-scrape, not via source refresh
        )
    )

    # ── Vehicle identity ──
    def _fetch_vin_decode():
        from tesla_cli.core.backends.dossier import decode_vin

        cfg = _s.load_config()
        return decode_vin(cfg.general.default_vin).model_dump() if cfg.general.default_vin else None

    register_source(
        SourceDef(
            id="vin.decode",
            name="VIN Decode",
            category="vehiculo",
            ttl=86400 * 30,
            country="",
            fetch_fn=_fetch_vin_decode,
        )
    )

    # ── Tesla Order ──
    def _normalize_tesla_tasks(raw_tasks: Any) -> dict[str, dict[str, Any]]:
        if not raw_tasks:
            return {}
        mapped: dict[str, dict[str, Any]] = {}
        if isinstance(raw_tasks, list):
            for task in raw_tasks:
                if not isinstance(task, dict):
                    continue
                key = task.get("taskType") or task.get("task_type") or task.get("key")
                if not key:
                    continue
                mapped[str(key)] = {
                    "complete": bool(task.get("completed", task.get("complete", False))),
                    "enabled": bool(task.get("active", task.get("enabled", False))),
                    "status": task.get("taskStatus") or task.get("status") or "",
                    "name": task.get("taskName") or task.get("name") or str(key),
                    "details": task,
                }
            return mapped
        if isinstance(raw_tasks, dict):
            for key, task in raw_tasks.items():
                if not isinstance(task, dict):
                    continue
                mapped[str(key)] = {
                    "complete": bool(task.get("complete", task.get("completed", False))),
                    "enabled": bool(task.get("enabled", task.get("active", False))),
                    "status": task.get("status") or task.get("taskStatus") or "",
                    "name": task.get("name") or task.get("taskName") or str(key),
                    "details": task,
                }
        return mapped

    def _fetch_order():
        from tesla_cli.core.backends.order import OrderBackend
        from tesla_cli.core.config import save_config as _save

        cfg = _s.load_config()
        rn = cfg.order.reservation_number
        backend = OrderBackend()
        orders = backend.get_orders()
        order_list = orders if isinstance(orders, list) else [orders]

        # Auto-detect RN, VIN, and country if not configured
        if not rn and order_list:
            first = order_list[0]
            rn = first.get("referenceNumber", "")
            vin = first.get("vin", "")
            order_country = first.get("countryCode", "") or first.get("country", "")
            if rn:
                cfg.order.reservation_number = rn
                if vin and not cfg.general.default_vin:
                    cfg.general.default_vin = vin
                if order_country and not cfg.general.country:
                    cfg.general.country = order_country.upper()
                    log.info("Auto-detected country from order: %s", cfg.general.country)
                _save(cfg)
        elif rn and order_list:
            for order in order_list:
                if order.get("referenceNumber") == rn:
                    api_vin = order.get("vin", "")
                    if api_vin and api_vin != cfg.general.default_vin:
                        cfg.general.default_vin = api_vin
                        _save(cfg)
                        log.info("Updated default VIN from active order: %s", api_vin)
                    break

        selected_order = None
        for order in order_list:
            if order.get("referenceNumber") == rn:
                selected_order = order
                break
        if selected_order is None:
            selected_order = order_list[0] if order_list else None

        enriched_order = selected_order
        if selected_order:
            try:
                details = backend.get_order_details(selected_order.get("referenceNumber", ""))
                enriched_order = {
                    **selected_order,
                    "tasks": [task.model_dump(mode="json") for task in details.tasks],
                    "delivery": details.delivery,
                }
            except Exception:
                log.warning(
                    "Failed to enrich tesla.order source with tasks/delivery", exc_info=True
                )

        return (
            enriched_order,
            {
                "mode": "fetch_fn",
                "url": backend.last_query_meta.get("url"),
                "method": backend.last_query_meta.get("method"),
                "status_code": backend.last_query_meta.get("status_code"),
                "response_text_excerpt": backend.last_query_meta.get("response_text_excerpt"),
            },
        )

    register_source(
        SourceDef(
            id="tesla.order",
            name="Tesla Order",
            category="financiero",
            requires_auth="order",
            ttl=1800,
            country="",
            fetch_fn=_fetch_order,
        )
    )

    def _fetch_tesla_delivery():
        order_cached = _load_cache("tesla.order") or {}
        order_data = order_cached.get("data") or {}
        if not order_data:
            order_result = _s.refresh_source("tesla.order", _skip_dependents=True)
            order_data = (order_result.get("data") or {}) if isinstance(order_result, dict) else {}
        delivery = order_data.get("delivery") or {}
        if not isinstance(delivery, dict):
            delivery = {}
        return delivery, {
            "mode": "derived_from_source",
            "derived_from": ["tesla.order", "tesla.portal"],
        }

    register_source(
        SourceDef(
            id="tesla.delivery",
            name="Tesla Delivery",
            category="financiero",
            ttl=1800,
            country="",
            fetch_fn=_fetch_tesla_delivery,
        )
    )

    def _fetch_tesla_tasks():
        order_cached = _load_cache("tesla.order") or {}
        order_data = order_cached.get("data") or {}
        if not order_data:
            order_result = _s.refresh_source("tesla.order", _skip_dependents=True)
            order_data = (order_result.get("data") or {}) if isinstance(order_result, dict) else {}
        tasks = _normalize_tesla_tasks(order_data.get("tasks") or {})
        return tasks, {
            "mode": "derived_from_source",
            "derived_from": ["tesla.order", "tesla.portal"],
        }

    register_source(
        SourceDef(
            id="tesla.tasks",
            name="Tesla Tasks",
            category="financiero",
            ttl=1800,
            country="",
            fetch_fn=_fetch_tesla_tasks,
        )
    )

    # ── INTL: Ship Tracking ──
    register_source(
        SourceDef(
            id="intl.ship_tracking",
            name="Ship Tracking",
            category="servicios",
            uses_playwright=True,
            ttl=3600,
            country="",
            openquery_source="intl.ship_tracking",
            openquery_params={"doc_type": "custom", "doc_number": "Grand Venus"},
        )
    )

    # ── INTL: Electricity Carbon Intensity ──
    register_source(
        SourceDef(
            id="intl.electricity_maps",
            name="Electricity Carbon Intensity",
            category="servicios",
            ttl=3600,
            country="",
            auto_refresh=False,
            openquery_source="intl.electricity_maps",
            openquery_params={"doc_type": "custom", "doc_number": ""},
        )
    )

    # ── US: NHTSA VIN Decode — universal (VIN decode works for any Tesla) ──
    register_source(
        SourceDef(
            id="us.nhtsa_vin",
            name="NHTSA VIN Decode",
            category="vehiculo",
            ttl=86400 * 30,
            country="US",
            openquery_source="us.nhtsa_vin",
            openquery_params={"doc_type": "vin", "doc_number": "$VIN"},
        )
    )
    register_source(
        SourceDef(
            id="us.nhtsa_recalls",
            name="NHTSA Recalls",
            category="seguridad",
            ttl=86400,
            country="",
            openquery_source="us.nhtsa_recalls",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "TESLA",
                "extra": {"make": "TESLA", "model": "$MODEL", "year": "$YEAR"},
            },
        )
    )
    register_source(
        SourceDef(
            id="us.nhtsa_complaints",
            name="NHTSA Consumer Complaints",
            category="seguridad",
            ttl=86400,
            country="",
            openquery_source="us.nhtsa_complaints",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "$VIN",
                "extra": {"make": "$MAKE", "model": "$MODEL", "year": "$YEAR"},
            },
        )
    )
    register_source(
        SourceDef(
            id="us.nhtsa_investigations",
            name="NHTSA Defect Investigations",
            category="seguridad",
            ttl=86400,
            country="",
            openquery_source="us.nhtsa_investigations",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "$VIN",
                "extra": {"make": "$MAKE", "model": "$MODEL", "year": "$YEAR"},
            },
        )
    )
    register_source(
        SourceDef(
            id="us.epa_fuel_economy",
            name="EPA Fuel Economy",
            category="vehiculo",
            ttl=86400 * 30,
            country="",
            openquery_source="us.epa_fuel_economy",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "$VIN",
                "extra": {"make": "$MAKE", "model": "$MODEL", "year": "$YEAR"},
            },
        )
    )


# ── Country-specific source definitions ──────────────────────────────────────

# Public alias used by CLI commands
COUNTRY_SOURCES: dict[str, list[SourceDef]] = {
    "US": [
        SourceDef(
            id="us.nhtsa_recalls",
            name="NHTSA Recalls",
            category="seguridad",
            ttl=86400,
            country="US",
            openquery_source="us.nhtsa_recalls",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "TESLA",
                "extra": {"make": "TESLA", "model": "$MODEL", "year": "$YEAR"},
            },
        ),
        SourceDef(
            id="us.nhtsa_safety_ratings",
            name="NHTSA Safety Ratings",
            category="seguridad",
            ttl=86400 * 30,
            country="US",
            openquery_source="us.nhtsa_safety_ratings",
            openquery_params={
                "doc_type": "vin",
                "doc_number": "$VIN",
            },
        ),
        SourceDef(
            id="us.nhtsa_complaints",
            name="NHTSA Consumer Complaints",
            category="seguridad",
            ttl=86400,
            country="US",
            openquery_source="us.nhtsa_complaints",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "$VIN",
                "extra": {"make": "$MAKE", "model": "$MODEL", "year": "$YEAR"},
            },
        ),
        SourceDef(
            id="us.nhtsa_investigations",
            name="NHTSA Defect Investigations",
            category="seguridad",
            ttl=86400,
            country="US",
            openquery_source="us.nhtsa_investigations",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "$VIN",
                "extra": {"make": "$MAKE", "model": "$MODEL", "year": "$YEAR"},
            },
        ),
        SourceDef(
            id="us.epa_fuel_economy",
            name="EPA Fuel Economy",
            category="vehiculo",
            ttl=86400 * 30,
            country="US",
            openquery_source="us.epa_fuel_economy",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "$VIN",
                "extra": {"make": "$MAKE", "model": "$MODEL", "year": "$YEAR"},
            },
        ),
        SourceDef(
            id="us.nicb_vincheck",
            name="NICB Stolen Vehicle Check",
            category="seguridad",
            ttl=86400 * 7,
            country="US",
            openquery_source="us.nicb_vincheck",
            openquery_params={"doc_type": "vin", "doc_number": "$VIN"},
        ),
    ],
    "CO": [
        SourceDef(
            id="co.runt",
            name="RUNT — Registro Vehicular",
            category="registro",
            uses_playwright=True,
            ttl=3600,
            country="CO",
            openquery_source="co.runt",
            openquery_params={"doc_type": "vin", "doc_number": "$VIN"},
        ),
        SourceDef(
            id="co.runt_soat",
            name="RUNT — SOAT",
            category="registro",
            uses_playwright=True,
            ttl=3600,
            country="CO",
            openquery_source="co.runt_soat",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
        SourceDef(
            id="co.runt_rtm",
            name="RUNT — Técnico-Mecánica",
            category="registro",
            uses_playwright=True,
            ttl=3600,
            country="CO",
            openquery_source="co.runt_rtm",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
        SourceDef(
            id="co.runt_conductor",
            name="RUNT — Conductor",
            category="registro",
            uses_playwright=True,
            ttl=86400,
            country="CO",
            openquery_source="co.runt_conductor",
            openquery_params={"doc_type": "cedula", "doc_number": "$CEDULA"},
        ),
        SourceDef(
            id="co.simit",
            name="SIMIT — Multas de Tránsito",
            category="infracciones",
            uses_playwright=True,
            ttl=3600,
            country="CO",
            openquery_source="co.simit",
            openquery_params={"doc_type": "cedula", "doc_number": "$CEDULA"},
        ),
        SourceDef(
            id="co.pico_y_placa",
            name="Pico y Placa",
            category="servicios",
            ttl=43200,  # 12h (changes daily)
            country="CO",
            auto_refresh=False,
            openquery_source="co.pico_y_placa",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
        SourceDef(
            id="co.recalls",
            name="SIC — Recalls",
            category="seguridad",
            uses_playwright=True,
            ttl=86400,
            country="CO",
            openquery_source="co.recalls",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "TESLA",
                "extra": {"marca": "TESLA"},
            },
        ),
        SourceDef(
            id="co.fasecolda",
            name="Fasecolda — Valor Comercial",
            category="financiero",
            uses_playwright=True,
            ttl=86400 * 7,
            country="CO",
            auto_refresh=False,
            openquery_source="co.fasecolda",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "TESLA",
                "extra": {"marca": "TESLA", "linea": "MODEL Y"},
            },
        ),
        SourceDef(
            id="co.combustible",
            name="Precios de Combustible",
            category="servicios",
            ttl=86400,
            country="CO",
            auto_refresh=False,
            openquery_source="co.combustible",
            openquery_params={"doc_type": "custom", "doc_number": ""},
        ),
        SourceDef(
            id="co.peajes",
            name="Tarifas de Peajes",
            category="servicios",
            ttl=86400 * 7,
            country="CO",
            auto_refresh=False,
            openquery_source="co.peajes",
            openquery_params={"doc_type": "custom", "doc_number": ""},
        ),
        SourceDef(
            id="co.vehiculos",
            name="Parque Automotor Nacional",
            category="registro",
            ttl=86400,
            country="CO",
            auto_refresh=False,
            openquery_source="co.vehiculos",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
        SourceDef(
            id="co.multas_bogota",
            name="Multas de Tránsito — Bogotá",
            category="infracciones",
            ttl=3600,
            country="CO",
            auto_refresh=False,
            openquery_source="co.multas_bogota",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
        SourceDef(
            id="co.multas_medellin",
            name="Multas de Tránsito — Medellín",
            category="infracciones",
            ttl=3600,
            country="CO",
            auto_refresh=False,
            openquery_source="co.multas_medellin",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
        SourceDef(
            id="co.tarifas_energia",
            name="Tarifas de Energía (kWh)",
            category="servicios",
            ttl=86400,  # daily refresh
            country="CO",
            auto_refresh=False,
            openquery_source="co.tarifas_energia",
            openquery_params={"doc_type": "custom", "doc_number": ""},
        ),
        # ── Vehicle Sources (EV-specific) ──
        SourceDef(
            id="co.estaciones_ev_epm",
            name="Estaciones EV (EPM)",
            category="servicios",
            ttl=86400,
            country="CO",
            auto_refresh=False,
            openquery_source="co.estaciones_ev_epm",
            openquery_params={"doc_type": "custom", "doc_number": ""},
        ),
        SourceDef(
            id="co.peajes_tarifas",
            name="Tarifas Peajes (INVIAS)",
            category="servicios",
            ttl=604800,  # weekly
            country="CO",
            auto_refresh=False,
            openquery_source="co.peajes_tarifas",
            openquery_params={"doc_type": "custom", "doc_number": ""},
        ),
        SourceDef(
            id="co.impuesto_vehicular",
            name="Impuesto Vehicular",
            category="financiero",
            ttl=86400,
            country="CO",
            auto_refresh=False,
            openquery_source="co.impuesto_vehicular",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
        # ── Driver Sources ──
        SourceDef(
            id="co.simit_historico",
            name="SIMIT Histórico",
            category="infracciones",
            ttl=3600,
            country="CO",
            auto_refresh=False,
            openquery_source="co.simit_historico",
            openquery_params={"doc_type": "cedula", "doc_number": "$CEDULA"},
        ),
        SourceDef(
            id="co.comparendos_transito",
            name="Comparendos Tránsito",
            category="infracciones",
            ttl=3600,
            country="CO",
            auto_refresh=False,
            openquery_source="co.comparendos_transito",
            openquery_params={"doc_type": "cedula", "doc_number": "$CEDULA"},
        ),
        SourceDef(
            id="co.estado_cedula",
            name="Cédula Status",
            category="registro",
            ttl=86400,
            country="CO",
            auto_refresh=False,
            openquery_source="co.estado_cedula",
            openquery_params={"doc_type": "cedula", "doc_number": "$CEDULA"},
        ),
    ],
    "AR": [
        SourceDef(
            id="ar.dnrpa",
            name="DNRPA — Registro de Vehículos",
            category="registro",
            ttl=86400,
            country="AR",
            openquery_source="ar.dnrpa",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
    ],
    "BR": [
        SourceDef(
            id="br.fipe",
            name="FIPE — Tabela de Preços",
            category="financiero",
            ttl=86400 * 7,
            country="BR",
            openquery_source="br.fipe",
            openquery_params={
                "doc_type": "custom",
                "doc_number": "TESLA",
                "extra": {"marca": "TESLA", "modelo": "Model Y"},
            },
        ),
        SourceDef(
            id="br.detran_sp",
            name="DETRAN-SP — Débitos Veiculares",
            category="infracciones",
            ttl=3600,
            country="BR",
            openquery_source="br.detran_sp",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
    ],
    "CL": [
        SourceDef(
            id="cl.fiscalizacion",
            name="Fiscalización — Infracciones de Tránsito",
            category="infracciones",
            ttl=3600,
            country="CL",
            openquery_source="cl.fiscalizacion",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
    ],
    "CR": [
        SourceDef(
            id="cr.vehiculo",
            name="Registro de Vehículos — Costa Rica",
            category="registro",
            ttl=86400,
            country="CR",
            openquery_source="cr.vehiculo",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
        SourceDef(
            id="cr.marchamo",
            name="Marchamo — Seguro Obligatorio",
            category="financiero",
            ttl=86400 * 7,
            country="CR",
            openquery_source="cr.marchamo",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
    ],
    "MX": [
        SourceDef(
            id="mx.repuve",
            name="REPUVE — Vehículos Robados",
            category="seguridad",
            ttl=86400,
            country="MX",
            openquery_source="mx.repuve",
            openquery_params={"doc_type": "vin", "doc_number": "$VIN"},
        ),
    ],
    "PE": [
        SourceDef(
            id="pe.sunarp_vehicular",
            name="SUNARP — Registro Vehicular",
            category="registro",
            ttl=86400,
            country="PE",
            openquery_source="pe.sunarp_vehicular",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
    ],
    "PA": [
        SourceDef(
            id="pa.attt_placa",
            name="ATTT — Infracciones de Tránsito",
            category="infracciones",
            ttl=3600,
            country="PA",
            openquery_source="pa.attt_placa",
            openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
        ),
    ],
}

# ── CO: EV stations uses an inline fetch (not openquery) ─────────────────────


def _make_ev_stations_source() -> SourceDef:
    def _fetch_ev_stations():
        import httpx

        r = httpx.get(
            "https://www.datos.gov.co/resource/qqm3-dw2u.json", params={"$limit": 100}, timeout=10
        )
        r.raise_for_status()
        return {"estaciones": r.json(), "total": len(r.json())}

    return SourceDef(
        id="co.estaciones_ev",
        name="Electrolineras",
        category="servicios",
        ttl=86400,
        country="CO",
        fetch_fn=_fetch_ev_stations,
    )


def _register_country_sources(country: str) -> None:
    """Register data sources for a given country code (ISO 3166-1 alpha-2).

    Call this after _register_universal() to add country-specific sources.
    Passing an empty country string registers nothing.
    """
    if not country:
        return
    country_upper = country.upper()
    sources = COUNTRY_SOURCES.get(country_upper, [])
    for src in sources:
        register_source(src)
    # Special-case: CO EV stations use an inline fetch, not openquery
    if country_upper == "CO":
        register_source(_make_ev_stations_source())


def _register_defaults() -> None:
    """Register all built-in data sources based on config country."""
    _register_universal()
    cfg = _s.load_config()
    country = cfg.general.country
    if country:
        _register_country_sources(country)
    else:
        # Backward-compatibility: when no country is set, register CO + US sources
        # so existing users don't lose functionality
        _register_country_sources("CO")
        _register_country_sources("US")


# Auto-register on import
