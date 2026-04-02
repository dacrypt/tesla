"""Colombian data sources: /api/co/* — Pico y Placa, EV stations, Fasecolda, Recalls."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/pico-y-placa")
def pico_y_placa(placa: str = "") -> dict:
    """Check if a vehicle can circulate today (Pico y Placa restriction).

    Query params:
    - `placa` — license plate number. If empty, uses plate from RUNT/dossier.
    """
    if not placa:
        try:
            import json

            from tesla_cli.core.config import CONFIG_DIR

            dossier_path = CONFIG_DIR / "dossier" / "dossier.json"
            if dossier_path.exists():
                d = json.loads(dossier_path.read_text())
                placa = (d.get("runt") or {}).get("placa", "")
        except Exception:
            pass

    if not placa:
        return {
            "available": True,
            "placa": "",
            "message": "No plate assigned yet",
            "restricted": False,
        }

    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        src = get_source("co.pico_y_placa")
        result = src.query(QueryInput(document_type=DocumentType.PLATE, document_number=placa))
        return result.model_dump(exclude={"audit"})
    except Exception as exc:
        return {"placa": placa, "restricted": False, "error": str(exc)}


@router.get("/estaciones-ev")
def estaciones_ev(ciudad: str = "", limit: int = 50) -> dict:
    """EV charging stations in Colombia from datos.gov.co."""
    try:
        import httpx

        params: dict = {"$limit": limit}
        if ciudad:
            # Socrata SoQL search — use contains for accent-insensitive matching
            params["$q"] = ciudad
        r = httpx.get("https://www.datos.gov.co/resource/qqm3-dw2u.json", params=params, timeout=10)
        r.raise_for_status()
        stations = r.json()
        return {
            "total": len(stations),
            "ciudad": ciudad or "all",
            "estaciones": [
                {
                    "nombre": s.get("estaci_n", s.get("tipo_de_estacion", "")),
                    "ciudad": s.get("ciudad", ""),
                    "direccion": s.get("direcci_n", ""),
                    "tipo": s.get("tipo", ""),
                    "horario": s.get("horario", ""),
                    "operador": s.get("tipo_de_estacion", ""),
                    "latitude": s.get("latitud"),
                    "longitude": s.get("longitud"),
                }
                for s in stations
            ],
        }
    except Exception as exc:
        raise HTTPException(502, f"EV stations query failed: {exc}") from exc


@router.get("/fasecolda")
def fasecolda_value(marca: str = "TESLA", linea: str = "") -> dict:
    """Vehicle commercial value from Fasecolda guide."""
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        src = get_source("co.fasecolda")
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number=marca,
                extra={"marca": marca, "linea": linea or "MODEL Y"},
            )
        )
        return result.model_dump(exclude={"audit"})
    except Exception as exc:
        return {"marca": marca, "linea": linea, "error": str(exc)}


@router.get("/recalls-sic")
def recalls_sic(marca: str = "TESLA") -> dict:
    """Safety recalls from SIC (Colombian consumer protection)."""
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        src = get_source("co.recalls")
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number=marca,
                extra={"marca": marca},
            )
        )
        return result.model_dump(exclude={"audit"})
    except Exception as exc:
        return {"marca": marca, "recalls": [], "error": str(exc)}


@router.get("/peajes")
def peajes(ruta: str = "") -> dict:
    """Toll booth tariffs from datos.gov.co."""
    try:
        import httpx

        params: dict = {"$limit": 100}
        if ruta:
            params["$where"] = (
                f"upper(nombre_estacion_peaje) like '%{ruta.upper()}%' OR upper(sector) like '%{ruta.upper()}%'"
            )
        r = httpx.get("https://www.datos.gov.co/resource/7gj8-j6i3.json", params=params, timeout=10)
        r.raise_for_status()
        return {"total": len(r.json()), "peajes": r.json()}
    except Exception as exc:
        raise HTTPException(502, f"Peajes query failed: {exc}") from exc
