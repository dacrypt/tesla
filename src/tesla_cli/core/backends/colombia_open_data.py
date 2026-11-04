"""Colombian open-data portal (datos.gov.co, Socrata) — EV stations and tolls.

Routes used to call these endpoints inline; backends are the API boundary.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from tesla_cli.core.backends.http import send_with_retry

EV_STATIONS_URL = "https://www.datos.gov.co/resource/qqm3-dw2u.json"
TOLLS_URL = "https://www.datos.gov.co/resource/7gj8-j6i3.json"


def _get(url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    with httpx.Client(timeout=10) as client:
        resp = send_with_retry(client, "GET", url, params=params, max_retries=2)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def ev_stations(city: str = "", limit: int = 50) -> list[dict[str, Any]]:
    """Raw EV charging-station rows, optionally filtered by city."""
    params: dict[str, Any] = {"$limit": max(1, min(limit, 500))}
    if city:
        params["$q"] = re.sub(r"[^a-zA-Z0-9\s\-áéíóúñÁÉÍÓÚÑ]", "", city)
    return _get(EV_STATIONS_URL, params)


def toll_rates(route: str = "") -> list[dict[str, Any]]:
    """Raw toll-booth tariff rows, optionally filtered by route/sector name."""
    params: dict[str, Any] = {"$limit": 100}
    if route:
        # Only [A-Z0-9 -] survive, so the SoQL $where cannot be broken out of.
        safe = re.sub(r"[^a-zA-Z0-9\s\-]", "", route.upper())
        params["$where"] = (
            f"upper(nombre_estacion_peaje) like '%{safe}%' OR upper(sector) like '%{safe}%'"
        )
    return _get(TOLLS_URL, params)
