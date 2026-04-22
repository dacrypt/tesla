"""OpenChargeMap client for charger discovery along a route.

Taxonomy constants are from the public OpenChargeMap reference data. They can
be re-verified at any time by running `tesla nav plan-probe-taxonomy`.

References:
- https://openchargemap.org/site/develop/api
- https://api.openchargemap.io/v3/referencedata/
"""

from __future__ import annotations

from typing import Any

import httpx

from tesla_cli.core.planner.models import ChargerSuggestion

OCM_BASE = "https://api.openchargemap.io/v3"
OCM_OPERATOR_TESLA = 23  # Tesla Motors Inc (Superchargers + destination + magic dock)
OCM_CONNECTION_TESLA_SUPERCHARGER = 27
OCM_CONNECTION_TESLA_ROADSTER = 8
OCM_CONNECTION_TESLA_DEST_US = 30  # Tesla "dest" wall connector (US, old)
OCM_CONNECTION_CCS_COMBO_1 = 32  # CCS-1 (J1772 Combo)
OCM_CONNECTION_CCS_COMBO_2 = 33  # CCS-2 (Mennekes Combo)
OCM_CONNECTION_CHADEMO = 2  # CHAdeMO
OCM_CONNECTION_TYPE_2 = 25  # Type 2 Mennekes (may include Tesla Model S/X EU)

NETWORK_FILTERS: dict[str, dict[str, Any]] = {
    "tesla": {
        "operatorid": OCM_OPERATOR_TESLA,
        "connectiontypeid": ",".join(
            str(x)
            for x in [
                OCM_CONNECTION_TESLA_SUPERCHARGER,
                OCM_CONNECTION_CCS_COMBO_2,
                OCM_CONNECTION_CCS_COMBO_1,
                OCM_CONNECTION_TESLA_ROADSTER,
            ]
        ),
    },
    "ccs": {
        "connectiontypeid": f"{OCM_CONNECTION_CCS_COMBO_1},{OCM_CONNECTION_CCS_COMBO_2}",
    },
    "any": {},  # no filter
}


class ChargerLookupError(Exception):
    """OpenChargeMap call failed (network, HTTP >= 400, or parse error)."""


class ChargerAuthError(ChargerLookupError):
    """API key missing or rejected."""


def find_chargers_near_point(
    lat: float,
    lon: float,
    api_key: str,
    radius_km: float = 10.0,
    max_results: int = 10,
    network: str = "any",
    min_power_kw: float | None = None,
    timeout_s: float = 20.0,
) -> list[ChargerSuggestion]:
    """Query OpenChargeMap for chargers near (lat, lon), apply filters, return list."""
    if not api_key:
        raise ChargerAuthError(
            "OpenChargeMap API key not configured. Get one free at "
            "https://openchargemap.org/site/profile/applications then run: "
            "tesla config set planner-openchargemap-key <KEY>"
        )
    params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "distance": radius_km,
        "distanceunit": "km",
        "maxresults": max_results,
        "compact": "true",
        "verbose": "false",
        "key": api_key,
    }
    params.update(NETWORK_FILTERS.get(network, {}))
    try:
        r = httpx.get(
            f"{OCM_BASE}/poi/",
            params=params,
            timeout=timeout_s,
            headers={"User-Agent": "tesla-cli"},
        )
    except httpx.HTTPError as exc:
        raise ChargerLookupError(f"OpenChargeMap request failed: {exc}") from exc
    if r.status_code in (401, 403):
        raise ChargerAuthError("OpenChargeMap rejected the API key")
    if r.status_code == 429:
        raise ChargerLookupError("OpenChargeMap rate-limited")
    if r.status_code >= 400:
        raise ChargerLookupError(f"OpenChargeMap HTTP {r.status_code}")
    try:
        data = r.json()
    except ValueError as exc:
        raise ChargerLookupError(f"OpenChargeMap returned invalid JSON: {exc}") from exc

    out: list[ChargerSuggestion] = []
    for poi in data:
        if not isinstance(poi, dict):
            continue
        addr = poi.get("AddressInfo") or {}
        pt_lat = addr.get("Latitude")
        pt_lon = addr.get("Longitude")
        if pt_lat is None or pt_lon is None:
            continue
        title = addr.get("Title") or f"Charger #{poi.get('ID', 0)}"
        op_info = poi.get("OperatorInfo") or {}
        operator = op_info.get("Title")
        connections = poi.get("Connections") or []
        powers = [c.get("PowerKW") for c in connections if c.get("PowerKW") is not None]
        max_pwr = max(powers) if powers else None
        conn_titles_set: set[str] = set()
        for c in connections:
            ct = c.get("ConnectionType") or {}
            t = ct.get("Title")
            if t:
                conn_titles_set.add(t)
        conn_titles = sorted(conn_titles_set)
        # Apply min_power_kw filter
        if min_power_kw is not None and (max_pwr is None or max_pwr < min_power_kw):
            continue
        # Classify network
        op_id = op_info.get("ID")
        conn_ids = [(c.get("ConnectionType") or {}).get("ID") for c in connections]
        if op_id == OCM_OPERATOR_TESLA:
            net = "tesla"
        elif any(
            cid in (OCM_CONNECTION_CCS_COMBO_1, OCM_CONNECTION_CCS_COMBO_2) for cid in conn_ids
        ):
            net = "ccs"
        else:
            net = "other"
        display_name = f"{operator} — {title}" if operator else title
        out.append(
            ChargerSuggestion(
                ocm_id=poi.get("ID", 0),
                name=display_name,
                lat=float(pt_lat),
                lon=float(pt_lon),
                operator=operator,
                network=net,
                max_power_kw=float(max_pwr) if max_pwr is not None else None,
                connection_types=conn_titles,
            )
        )
    return out


def probe_taxonomy(api_key: str, timeout_s: float = 20.0) -> dict:
    """Fetch current OCM reference data for verification.

    Call via `tesla nav plan-probe-taxonomy`.
    """
    if not api_key:
        raise ChargerAuthError(
            "OpenChargeMap API key required for taxonomy probe. Get one free at "
            "https://openchargemap.org/site/profile/applications then run: "
            "tesla config set planner-openchargemap-key <KEY>"
        )
    try:
        r = httpx.get(
            f"{OCM_BASE}/referencedata/",
            params={"key": api_key},
            timeout=timeout_s,
            headers={"User-Agent": "tesla-cli"},
        )
    except httpx.HTTPError as exc:
        raise ChargerLookupError(f"OpenChargeMap request failed: {exc}") from exc
    if r.status_code in (401, 403):
        raise ChargerAuthError("OpenChargeMap rejected the API key")
    if r.status_code >= 400:
        raise ChargerLookupError(f"OpenChargeMap HTTP {r.status_code}")
    try:
        d = r.json()
    except ValueError as exc:
        raise ChargerLookupError(f"OpenChargeMap returned invalid JSON: {exc}") from exc
    tesla_ops = [
        {"ID": o.get("ID"), "Title": o.get("Title")}
        for o in d.get("Operators", [])
        if "tesla" in (o.get("Title") or "").lower()
    ]
    keywords = ("tesla", "ccs", "combo", "supercharger", "chademo", "type 2")
    types = [
        {"ID": c.get("ID"), "Title": c.get("Title")}
        for c in d.get("ConnectionTypes", [])
        if any(k in (c.get("Title") or "").lower() for k in keywords)
    ]
    return {"tesla_operators": tesla_ops, "connection_types": types}
