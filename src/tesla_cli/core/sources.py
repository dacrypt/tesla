"""Independent Data Source Registry.

Each source fetches from one external service, caches independently,
and can be refreshed without affecting other sources. Sources that use
Playwright (CAPTCHA) run as subprocesses to avoid uvicorn conflicts.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tesla_cli.core.config import CONFIG_DIR, load_config

log = logging.getLogger("tesla-cli.sources")

SOURCES_DIR = CONFIG_DIR / "sources"


@dataclass
class SourceDef:
    """Definition of a data source."""
    id: str
    name: str
    category: str  # vehiculo | registro | infracciones | financiero | seguridad | servicios
    requires_auth: str = ""  # "fleet" | "order" | "" (none)
    uses_playwright: bool = False  # True = refresh via subprocess
    ttl: int = 3600  # seconds before stale
    country: str = "CO"
    fetch_fn: Callable | None = None  # inline fetch (non-playwright)
    openquery_source: str = ""  # openquery source id (e.g. "co.runt")
    openquery_params: dict = field(default_factory=dict)


# ── Source Registry ──────────────────────────────────────────────────────────

_SOURCES: dict[str, SourceDef] = {}


def register_source(source: SourceDef) -> None:
    _SOURCES[source.id] = source


def get_source_def(source_id: str) -> SourceDef | None:
    return _SOURCES.get(source_id)


def list_sources() -> list[dict[str, Any]]:
    """List all sources with their cached status."""
    result = []
    for sid, src in _SOURCES.items():
        cached = _load_cache(sid)
        result.append({
            "id": sid,
            "name": src.name,
            "category": src.category,
            "country": src.country,
            "requires_auth": src.requires_auth,
            "ttl": src.ttl,
            "refreshed_at": cached.get("refreshed_at") if cached else None,
            "stale": _is_stale(sid),
            "has_data": cached is not None and "data" in cached,
            "error": cached.get("error") if cached else None,
        })
    return result


def get_cached(source_id: str) -> dict | None:
    """Get cached data for a source."""
    cached = _load_cache(source_id)
    if not cached:
        return None
    return cached.get("data")


def get_cached_with_meta(source_id: str) -> dict | None:
    """Get cached data + metadata (refreshed_at, error, stale)."""
    cached = _load_cache(source_id)
    if not cached:
        return {"id": source_id, "data": None, "refreshed_at": None, "error": None, "stale": True}
    return {
        "id": source_id,
        "data": cached.get("data"),
        "refreshed_at": cached.get("refreshed_at"),
        "error": cached.get("error"),
        "stale": _is_stale(source_id),
    }


def refresh_source(source_id: str) -> dict:
    """Refresh a single source. Returns {data, refreshed_at, error}."""
    src = _SOURCES.get(source_id)
    if not src:
        return {"error": f"Unknown source: {source_id}"}

    # Check auth requirements
    if src.requires_auth:
        from tesla_cli.core.auth.tokens import has_token, FLEET_ACCESS_TOKEN, ORDER_ACCESS_TOKEN
        if src.requires_auth == "fleet" and not has_token(FLEET_ACCESS_TOKEN):
            return _save_cache(source_id, None, error="Fleet API authentication required. Login in Settings.")
        if src.requires_auth == "order" and not has_token(ORDER_ACCESS_TOKEN):
            return _save_cache(source_id, None, error="Tesla order authentication required. Login in Settings.")

    # Check required config values — try auto-detect from other sources
    params = src.openquery_params
    if params.get("doc_number") == "$CEDULA":
        cfg = load_config()
        cedula = cfg.general.cedula
        # Auto-detect from RUNT cache if not configured
        if not cedula:
            runt_cache = _load_cache("co.runt")
            if runt_cache and runt_cache.get("data"):
                cedula = runt_cache["data"].get("no_identificacion", "")
        if not cedula:
            return _save_cache(source_id, None, error="Cédula del propietario requerida. Configúrala en Settings.")
    if params.get("doc_number") == "$VIN":
        cfg = load_config()
        if not cfg.general.default_vin:
            return _save_cache(source_id, None, error="VIN not configured.")

    # Playwright sources run as subprocess
    if src.uses_playwright:
        return _refresh_subprocess(source_id, src)

    # Inline fetch
    if src.fetch_fn:
        try:
            data = src.fetch_fn()
            return _save_cache(source_id, data)
        except Exception as exc:
            return _save_cache(source_id, None, error=str(exc))

    # openquery source
    if src.openquery_source:
        return _refresh_openquery_inline(source_id, src)

    return _save_cache(source_id, None, error="No fetch method defined")


def refresh_stale() -> dict[str, Any]:
    """Refresh all stale sources. Returns {refreshed: [...], failed: [...]}."""
    refreshed = []
    failed = []
    for sid in _SOURCES:
        if _is_stale(sid):
            result = refresh_source(sid)
            if result.get("error"):
                failed.append({"id": sid, "error": result["error"]})
            else:
                refreshed.append(sid)
    return {"refreshed": refreshed, "failed": failed}


def missing_auth() -> list[dict]:
    """Return sources that need authentication the user hasn't provided."""
    from tesla_cli.core.auth.tokens import has_token, FLEET_ACCESS_TOKEN, ORDER_ACCESS_TOKEN
    missing = []
    for sid, src in _SOURCES.items():
        if src.requires_auth == "fleet" and not has_token(FLEET_ACCESS_TOKEN):
            missing.append({"source": sid, "name": src.name, "auth_type": "fleet", "message": "Connect your Tesla account in Settings"})
        elif src.requires_auth == "order" and not has_token(ORDER_ACCESS_TOKEN):
            missing.append({"source": sid, "name": src.name, "auth_type": "order", "message": "Connect Tesla order tracking in Settings"})
    # Dedupe by auth_type
    seen = set()
    result = []
    for m in missing:
        if m["auth_type"] not in seen:
            seen.add(m["auth_type"])
            result.append(m)
    return result


# ── Cache ────────────────────────────────────────────────────────────────────

def _load_cache(source_id: str) -> dict | None:
    path = SOURCES_DIR / f"{source_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _save_cache(source_id: str, data: Any, error: str | None = None) -> dict:
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    cached = {"data": data, "refreshed_at": now, "error": error}
    (SOURCES_DIR / f"{source_id}.json").write_text(json.dumps(cached, default=str, indent=2))
    return cached


def _is_stale(source_id: str) -> bool:
    src = _SOURCES.get(source_id)
    if not src:
        return True
    cached = _load_cache(source_id)
    if not cached or not cached.get("refreshed_at"):
        return True
    try:
        refreshed = datetime.fromisoformat(cached["refreshed_at"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - refreshed).total_seconds()
        return age > src.ttl
    except Exception:
        return True


# ── Refresh methods ──────────────────────────────────────────────────────────

def _refresh_subprocess(source_id: str, src: SourceDef) -> dict:
    """Refresh a Playwright-based source via subprocess."""
    script = f"""
import json
from openquery.sources import get_source
from openquery.sources.base import DocumentType, QueryInput
from tesla_cli.core.config import load_config

cfg = load_config()
vin = cfg.general.default_vin or ""
src = get_source("{src.openquery_source}")
params = {json.dumps(src.openquery_params)}

# Build query input
doc_type = params.get("doc_type", "custom")
doc_number = params.get("doc_number", "")

# Auto-fill from config
if doc_number == "$VIN":
    doc_number = vin
elif doc_number == "$CEDULA":
    doc_number = cfg.general.cedula or ""
    if not doc_number:
        print(json.dumps({{"error": "No cedula configured. Set general.cedula in config."}}))
        import sys; sys.exit(0)
elif doc_number == "$PLACA":
    # Try to get placa from cached RUNT
    import pathlib
    runt_cache = pathlib.Path.home() / ".tesla-cli" / "sources" / "co.runt.json"
    if runt_cache.exists():
        runt_data = json.loads(runt_cache.read_text()).get("data", {{}})
        doc_number = runt_data.get("placa", "")

dt_map = {{"vin": DocumentType.VIN, "placa": DocumentType.PLATE, "cedula": DocumentType.CEDULA, "custom": DocumentType.CUSTOM}}
qi = QueryInput(document_type=dt_map.get(doc_type, DocumentType.CUSTOM), document_number=doc_number, extra=params.get("extra", {{}}))
result = src.query(qi)
print(json.dumps(result.model_dump(exclude={{"audit"}}), default=str))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            return _save_cache(source_id, data)
        else:
            err = result.stderr.strip()[-200:] if result.stderr else "subprocess failed"
            log.debug("Source %s subprocess failed: %s", source_id, err)
            return _save_cache(source_id, None, error=err)
    except subprocess.TimeoutExpired:
        return _save_cache(source_id, None, error="Query timed out (120s)")
    except Exception as exc:
        return _save_cache(source_id, None, error=str(exc))


def _refresh_openquery_inline(source_id: str, src: SourceDef) -> dict:
    """Refresh a non-Playwright openquery source inline."""
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        cfg = load_config()
        params = src.openquery_params
        doc_number = params.get("doc_number", "")
        if doc_number == "$VIN":
            doc_number = cfg.general.default_vin or ""
        elif doc_number == "$CEDULA":
            doc_number = cfg.general.cedula or ""
        elif doc_number == "$PLACA":
            # Try to get placa from cached RUNT
            runt_cache = _load_cache("co.runt")
            doc_number = (runt_cache or {}).get("data", {}).get("placa", "") if runt_cache else ""

        dt_map = {"vin": DocumentType.VIN, "placa": DocumentType.PLATE, "cedula": DocumentType.CEDULA, "custom": DocumentType.CUSTOM}
        qi = QueryInput(
            document_type=dt_map.get(params.get("doc_type", "custom"), DocumentType.CUSTOM),
            document_number=doc_number,
            extra=params.get("extra", {}),
        )
        oq_src = get_source(src.openquery_source)
        result = oq_src.query(qi)
        data = result.model_dump(exclude={"audit"})
        return _save_cache(source_id, data)
    except Exception as exc:
        return _save_cache(source_id, None, error=str(exc))


# ── Default source registrations ─────────────────────────────────────────────

def _register_defaults() -> None:
    """Register all built-in data sources."""

    # ── Vehicle identity ──
    def _fetch_vin_decode():
        from tesla_cli.core.backends.dossier import decode_vin
        cfg = load_config()
        return decode_vin(cfg.general.default_vin).model_dump() if cfg.general.default_vin else None

    register_source(SourceDef(
        id="vin.decode", name="VIN Decode", category="vehiculo",
        ttl=86400 * 30, country="", fetch_fn=_fetch_vin_decode,
    ))

    # ── Tesla Order ──
    def _fetch_order():
        from tesla_cli.core.backends.order import OrderBackend
        from tesla_cli.core.config import save_config as _save
        cfg = load_config()
        rn = cfg.order.reservation_number
        backend = OrderBackend()
        orders = backend.get_orders()
        order_list = orders if isinstance(orders, list) else [orders]

        # Auto-detect RN and VIN if not configured
        if not rn and order_list:
            first = order_list[0]
            rn = first.get("referenceNumber", "")
            vin = first.get("vin", "")
            if rn:
                cfg.order.reservation_number = rn
                if vin and not cfg.general.default_vin:
                    cfg.general.default_vin = vin
                _save(cfg)

        for order in order_list:
            if order.get("referenceNumber") == rn:
                return order
        return order_list[0] if order_list else None

    register_source(SourceDef(
        id="tesla.order", name="Tesla Order", category="financiero",
        requires_auth="order", ttl=1800, country="", fetch_fn=_fetch_order,
    ))

    # ── Colombia: RUNT (Playwright) ──
    register_source(SourceDef(
        id="co.runt", name="RUNT — Registro Vehicular", category="registro",
        uses_playwright=True, ttl=3600, country="CO",
        openquery_source="co.runt",
        openquery_params={"doc_type": "vin", "doc_number": "$VIN"},
    ))

    # ── Colombia: SIMIT (Playwright) ──
    register_source(SourceDef(
        id="co.simit", name="SIMIT — Multas de Tránsito", category="infracciones",
        uses_playwright=True, ttl=3600, country="CO",
        openquery_source="co.simit",
        openquery_params={"doc_type": "cedula", "doc_number": "$CEDULA"},
    ))

    # ── Colombia: Pico y Placa (fast, no Playwright) ──
    register_source(SourceDef(
        id="co.pico_y_placa", name="Pico y Placa", category="servicios",
        ttl=43200, country="CO",  # 12h (changes daily)
        openquery_source="co.pico_y_placa",
        openquery_params={"doc_type": "placa", "doc_number": "$PLACA"},
    ))

    # ── Colombia: EV Stations (fast API) ──
    def _fetch_ev_stations():
        import httpx
        r = httpx.get("https://www.datos.gov.co/resource/qqm3-dw2u.json", params={"$limit": 100}, timeout=10)
        r.raise_for_status()
        return {"estaciones": r.json(), "total": len(r.json())}

    register_source(SourceDef(
        id="co.estaciones_ev", name="Electrolineras", category="servicios",
        ttl=86400, country="CO", fetch_fn=_fetch_ev_stations,
    ))

    # ── Colombia: SIC Recalls (Playwright) ──
    register_source(SourceDef(
        id="co.recalls", name="SIC — Recalls", category="seguridad",
        uses_playwright=True, ttl=86400, country="CO",
        openquery_source="co.recalls",
        openquery_params={"doc_type": "custom", "doc_number": "TESLA", "extra": {"marca": "TESLA"}},
    ))

    # ── Colombia: Fasecolda (Playwright) ──
    register_source(SourceDef(
        id="co.fasecolda", name="Fasecolda — Valor Comercial", category="financiero",
        uses_playwright=True, ttl=86400 * 7, country="CO",
        openquery_source="co.fasecolda",
        openquery_params={"doc_type": "custom", "doc_number": "TESLA", "extra": {"marca": "TESLA", "linea": "MODEL Y"}},
    ))

    # ── US: NHTSA Recalls (fast API) ──
    register_source(SourceDef(
        id="us.nhtsa_recalls", name="NHTSA Recalls", category="seguridad",
        ttl=86400, country="US",
        openquery_source="us.nhtsa_recalls",
        openquery_params={"doc_type": "custom", "doc_number": "TESLA", "extra": {"make": "TESLA", "model": "Model Y", "year": "2026"}},
    ))

    # ── US: NHTSA VIN Decode (fast API) ──
    register_source(SourceDef(
        id="us.nhtsa_vin", name="NHTSA VIN Decode", category="vehiculo",
        ttl=86400 * 30, country="US",
        openquery_source="us.nhtsa_vin",
        openquery_params={"doc_type": "vin", "doc_number": "$VIN"},
    ))

    # ── INTL: Ship Tracking ──
    register_source(SourceDef(
        id="intl.ship_tracking", name="Ship Tracking", category="servicios",
        uses_playwright=True, ttl=3600, country="",
        openquery_source="intl.ship_tracking",
        openquery_params={"doc_type": "custom", "doc_number": "Grand Venus"},
    ))


# Auto-register on import
_register_defaults()
