"""Independent Data Source Registry.

Each source fetches from one external service, caches independently,
and can be refreshed without affecting other sources. Sources that use
Playwright (CAPTCHA) run as subprocesses to avoid uvicorn conflicts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    auto_refresh: bool = True
    fetch_fn: Callable | None = None  # inline fetch (non-playwright)
    openquery_source: str = ""  # openquery source id (e.g. "co.runt")
    openquery_params: dict = field(default_factory=dict)


# ── Source Registry ──────────────────────────────────────────────────────────

_SOURCES: dict[str, SourceDef] = {}
_OPENQUERY_AVAILABLE: set[str] | None = None


def register_source(source: SourceDef) -> None:
    if source.openquery_source and not _openquery_source_exists(source.openquery_source):
        log.warning("Skipping source %s: openquery source %s is not available", source.id, source.openquery_source)
        return
    _SOURCES[source.id] = source


def get_source_def(source_id: str) -> SourceDef | None:
    return _SOURCES.get(source_id)


def list_sources() -> list[dict[str, Any]]:
    """List all sources with their cached status."""
    result = []
    for sid, src in _SOURCES.items():
        cached = _load_cache(sid)
        visible_error = _visible_error(src, cached)
        result.append(
            {
                "id": sid,
                "name": src.name,
                "category": src.category,
                "country": src.country,
                "requires_auth": src.requires_auth,
                "auto_refresh": src.auto_refresh,
                "manual_only": not src.auto_refresh,
                "ttl": src.ttl,
                "refreshed_at": cached.get("refreshed_at") if cached else None,
                "stale": _is_stale(sid),
                "has_data": cached is not None and "data" in cached,
                "error": visible_error,
            }
        )
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
    src = get_source_def(source_id)
    return {
        "id": source_id,
        "data": cached.get("data"),
        "refreshed_at": cached.get("refreshed_at"),
        "error": _visible_error(src, cached),
        "stale": _is_stale(source_id),
    }


def _visible_error(src: SourceDef | None, cached: dict | None) -> str | None:
    """Hide noisy inherited errors for manual-only sources with no data."""
    if not cached:
        return None
    error = cached.get("error")
    if not error:
        return None
    if src and not src.auto_refresh and not cached.get("data"):
        return None
    return error


def refresh_source(source_id: str, *, _skip_dependents: bool = False) -> dict:
    """Refresh a single source. Returns {data, refreshed_at, error}."""
    src = _SOURCES.get(source_id)
    if not src:
        return {"error": f"Unknown source: {source_id}"}
    query_context = _current_query_context(source_id, src)

    # Check auth requirements
    if src.requires_auth:
        from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN, ORDER_ACCESS_TOKEN, has_token

        if src.requires_auth == "fleet" and not has_token(FLEET_ACCESS_TOKEN):
            result = _save_cache(
                source_id,
                None,
                error="Fleet API authentication required. Login in Settings.",
                query_context=query_context,
            )
            _append_query(source_id, src, result, {"mode": "auth_guard", "auth_type": "fleet"})
            return result
        if src.requires_auth == "order" and not has_token(ORDER_ACCESS_TOKEN):
            result = _save_cache(
                source_id,
                None,
                error="Tesla order authentication required. Login in Settings.",
                query_context=query_context,
            )
            _append_query(source_id, src, result, {"mode": "auth_guard", "auth_type": "order"})
            return result

    # Check required config values — try auto-detect from other sources
    params = src.openquery_params
    if params.get("doc_number") == "$CEDULA":
        cedula = _resolve_owner_cedula()
        if not cedula:
            result = _save_cache(
                source_id,
                None,
                error="Cédula del propietario requerida. Configúrala en Settings.",
                query_context=query_context,
            )
            _append_query(source_id, src, result, {"mode": "config_guard", "missing": "cedula"})
            return result
    if params.get("doc_number") == "$VIN":
        cfg = load_config()
        if not cfg.general.default_vin:
            result = _save_cache(source_id, None, error="VIN not configured.", query_context=query_context)
            _append_query(source_id, src, result, {"mode": "config_guard", "missing": "vin"})
            return result
    if params.get("doc_number") == "$PLACA":
        plate = _resolve_plate()
        if not plate:
            result = _save_cache(
                source_id,
                None,
                error="Plate not available yet. Refresh RUNT successfully first.",
                query_context=query_context,
            )
            _append_query(source_id, src, result, {"mode": "config_guard", "missing": "placa"})
            return result

    # Playwright sources run as subprocess
    if src.uses_playwright:
        result = _refresh_subprocess(source_id, src)
        _append_query(source_id, src, result, result.pop("_query_meta", {}))
        return result

    # Inline fetch
    if src.fetch_fn:
        try:
            query_meta: dict[str, Any] = {"mode": "fetch_fn"}
            fetched = src.fetch_fn()
            if isinstance(fetched, tuple) and len(fetched) == 2:
                data, extra_meta = fetched
                if isinstance(extra_meta, dict):
                    query_meta.update(extra_meta)
            else:
                data = fetched
            result = _save_cache(source_id, data, query_context=query_context)
            _append_query(source_id, src, result, query_meta)
            if not _skip_dependents and not result.get("error"):
                _refresh_invalidated_dependents(source_id)
            return result
        except Exception as exc:
            result = _save_cache(source_id, None, error=str(exc), query_context=query_context)
            _append_query(source_id, src, result, {"mode": "fetch_fn"})
            return result

    # openquery source
    if src.openquery_source:
        result = _refresh_openquery_inline(source_id, src)
        _append_query(source_id, src, result, result.pop("_query_meta", {}))
        if not _skip_dependents and not result.get("error"):
            _refresh_invalidated_dependents(source_id)
        return result

    result = _save_cache(source_id, None, error="No fetch method defined", query_context=query_context)
    _append_query(source_id, src, result, {"mode": "noop"})
    return result


def refresh_stale() -> dict[str, Any]:
    """Refresh all stale sources. Returns {refreshed: [...], failed: [...]}."""
    refreshed = []
    failed = []
    for sid in _SOURCES:
        if not _SOURCES[sid].auto_refresh:
            continue
        if _is_stale(sid):
            result = refresh_source(sid)
            if result.get("error"):
                failed.append({"id": sid, "error": result["error"]})
            else:
                refreshed.append(sid)
    return {"refreshed": refreshed, "failed": failed}


def _refresh_invalidated_dependents(source_id: str) -> None:
    """Refresh auto sources whose resolved query context changed after a dependency update."""
    if source_id not in {"tesla.order", "co.runt"}:
        return
    for dependent_id, dependent in _SOURCES.items():
        if dependent_id == source_id or not dependent.auto_refresh:
            continue
        if _is_stale(dependent_id):
            refresh_source(dependent_id, _skip_dependents=True)


def missing_auth() -> list[dict]:
    """Return sources that need authentication the user hasn't provided."""
    from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN, ORDER_ACCESS_TOKEN, has_token

    missing = []
    for sid, src in _SOURCES.items():
        if src.requires_auth == "fleet" and not has_token(FLEET_ACCESS_TOKEN):
            missing.append(
                {
                    "source": sid,
                    "name": src.name,
                    "auth_type": "fleet",
                    "message": "Connect your Tesla account in Settings",
                }
            )
        elif src.requires_auth == "order" and not has_token(ORDER_ACCESS_TOKEN):
            missing.append(
                {
                    "source": sid,
                    "name": src.name,
                    "auth_type": "order",
                    "message": "Connect Tesla order tracking in Settings",
                }
            )
    # Dedupe by auth_type
    seen = set()
    result = []
    for m in missing:
        if m["auth_type"] not in seen:
            seen.add(m["auth_type"])
            result.append(m)
    return result


# ── Cache + History + Audit ──────────────────────────────────────────────────

HISTORY_DIR = CONFIG_DIR / "source_history"
AUDIT_DIR = CONFIG_DIR / "source_audits"
DIFFS_DIR = CONFIG_DIR / "source_diffs"
QUERIES_DIR = CONFIG_DIR / "source_queries"


def _load_cache(source_id: str) -> dict | None:
    path = SOURCES_DIR / f"{source_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _openquery_source_exists(source_name: str) -> bool:
    """Check whether an openquery source is available in the installed package."""
    global _OPENQUERY_AVAILABLE
    if _OPENQUERY_AVAILABLE is None:
        try:
            from openquery.sources import list_sources

            _OPENQUERY_AVAILABLE = {source.meta().name for source in list_sources()}
        except Exception:
            _OPENQUERY_AVAILABLE = set()
    return source_name in _OPENQUERY_AVAILABLE


def _save_cache(
    source_id: str,
    data: Any,
    error: str | None = None,
    audit: Any = None,
    query_context: dict[str, Any] | None = None,
) -> dict:
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    cached = {"data": data, "refreshed_at": now, "error": error}
    if query_context is not None:
        cached["query_context"] = query_context

    # Detect changes from previous data
    prev = _load_cache(source_id)
    previous_data = prev.get("data") if prev else None
    previous_error = prev.get("error") if prev else None
    changes = _detect_changes(source_id, previous_data, data) if data else []
    if changes:
        cached["changes"] = changes

    (SOURCES_DIR / f"{source_id}.json").write_text(json.dumps(cached, default=str, indent=2))

    # Save to history (append-only log)
    if data:
        _append_history(source_id, data, changes)
        if changes:
            _append_diff(source_id, previous_data, data, changes)

    # Save audit PDF if present
    if audit:
        _save_audit(source_id, audit, now)

    try:
        from tesla_cli.core import events

        if changes:
            events.emit_source_change(source_id, changes, refreshed_at=now)
        events.emit_source_health(
            source_id,
            error=error,
            previous_error=previous_error,
            refreshed_at=now,
        )
    except Exception:
        pass

    return cached


def _detect_changes(source_id: str, old_data: Any, new_data: Any) -> list[dict]:
    """Compare old and new data, return list of changes."""
    if not old_data or not new_data:
        return []
    if not isinstance(old_data, dict) or not isinstance(new_data, dict):
        return []

    changes = []
    # Skip metadata fields
    skip = {"queried_at", "audit", "refreshed_at"}
    all_keys = set(old_data.keys()) | set(new_data.keys())

    for key in sorted(all_keys - skip):
        old_val = old_data.get(key)
        new_val = new_data.get(key)
        if old_val != new_val and (old_val or new_val):
            changes.append(
                {
                    "field": key,
                    "old": str(old_val) if old_val is not None else None,
                    "new": str(new_val) if new_val is not None else None,
                }
            )

    return changes


def _append_history(source_id: str, data: Any, changes: list) -> None:
    """Append a snapshot to the source's history log."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_file = HISTORY_DIR / f"{source_id}.jsonl"

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "data_hash": hashlib.sha256(
            json.dumps(data, default=str, sort_keys=True).encode()
        ).hexdigest()[:16],
        "changes": changes,
    }
    with open(history_file, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def _append_diff(source_id: str, previous_data: Any, current_data: Any, changes: list[dict]) -> None:
    """Append a structured diff entry for a source."""
    if not changes:
        return

    DIFFS_DIR.mkdir(parents=True, exist_ok=True)
    diff_file = DIFFS_DIR / f"{source_id}.jsonl"
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "source_id": source_id,
        "previous_data_hash": _data_hash(previous_data),
        "current_data_hash": _data_hash(current_data),
        "changed": True,
        "changes_count": len(changes),
        "changes": changes,
    }
    with open(diff_file, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def _save_audit(source_id: str, audit: Any, timestamp: str) -> None:
    """Save audit evidence (PDF, screenshots) to disk."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # Handle openquery AuditRecord
    audit_data = (
        audit.model_dump()
        if hasattr(audit, "model_dump")
        else audit
        if isinstance(audit, dict)
        else {}
    )

    # Save PDF if present
    pdf_b64 = audit_data.get("pdf_base64", "")
    if pdf_b64:
        import base64

        ts_slug = timestamp[:19].replace(":", "-").replace("T", "_")
        pdf_path = AUDIT_DIR / f"{source_id}_{ts_slug}.pdf"
        pdf_path.write_bytes(base64.b64decode(pdf_b64))
        log.info("Audit PDF saved: %s (%d KB)", pdf_path.name, pdf_path.stat().st_size // 1024)

    # Save audit metadata (without large base64 fields)
    meta = {k: v for k, v in audit_data.items() if not k.endswith("_base64") and k != "screenshots"}
    meta["has_pdf"] = bool(pdf_b64)
    meta["screenshot_count"] = len(audit_data.get("screenshots", []))
    meta_path = AUDIT_DIR / f"{source_id}_{timestamp[:19].replace(':', '-').replace('T', '_')}.json"
    meta_path.write_text(json.dumps(meta, default=str, indent=2))


def get_history(source_id: str, limit: int = 50) -> list[dict]:
    """Read recent history entries for a source."""
    history_file = HISTORY_DIR / f"{source_id}.jsonl"
    if not history_file.exists():
        return []
    lines = history_file.read_text().strip().splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries


def get_diffs(source_id: str, limit: int = 50) -> list[dict]:
    """Read recent diff entries for a source."""
    diff_file = DIFFS_DIR / f"{source_id}.jsonl"
    if not diff_file.exists():
        return []
    lines = diff_file.read_text().strip().splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries


def get_queries(source_id: str, limit: int = 50) -> list[dict]:
    """Read recent query audit entries for a source."""
    query_file = QUERIES_DIR / f"{source_id}.jsonl"
    if not query_file.exists():
        return []
    lines = query_file.read_text().strip().splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries


def get_audits(source_id: str) -> list[dict]:
    """List available audit files for a source."""
    if not AUDIT_DIR.exists():
        return []
    audits = []
    for f in sorted(AUDIT_DIR.glob(f"{source_id}_*.pdf"), reverse=True):
        meta_path = f.with_suffix(".json")
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        audits.append(
            {
                "filename": f.name,
                "size_kb": f.stat().st_size // 1024,
                "timestamp": meta.get(
                    "queried_at", f.stem.split("_", 1)[1] if "_" in f.stem else ""
                ),
                "source": meta.get("source", source_id),
                "duration_ms": meta.get("duration_ms"),
            }
        )
    return audits

def _is_stale(source_id: str) -> bool:
    src = _SOURCES.get(source_id)
    if not src:
        return True
    cached = _load_cache(source_id)
    if not cached or not cached.get("refreshed_at"):
        return True
    if cached.get("data") is None and not cached.get("error"):
        return True
    if not src.auto_refresh and cached.get("data") is None:
        return True
    current_context = _current_query_context(source_id, src)
    cached_context = cached.get("query_context")
    if current_context and cached_context != current_context:
        return True
    try:
        refreshed = datetime.fromisoformat(cached["refreshed_at"].replace("Z", "+00:00"))
        age = (datetime.now(UTC) - refreshed).total_seconds()
        return age > src.ttl
    except Exception:
        return True


def _resolve_owner_cedula() -> str:
    cfg = load_config()
    cedula = ""
    try:
        from tesla_cli.core.db import get_primary_driver

        vin = cfg.general.default_vin
        if vin:
            driver = get_primary_driver(vin)
            if driver:
                candidate = driver.get("doc_number", "")
                if _is_valid_doc_number(candidate):
                    cedula = candidate
    except Exception:
        pass
    if not cedula:
        candidate = cfg.general.cedula
        if _is_valid_doc_number(candidate):
            cedula = candidate
    if not cedula:
        runt_cache = _load_cache("co.runt")
        if runt_cache and runt_cache.get("data"):
            candidate = (runt_cache["data"] or {}).get("no_identificacion", "")
            if _is_valid_doc_number(candidate):
                cedula = candidate
    return cedula or ""


def _is_valid_doc_number(value: Any) -> bool:
    """Reject blank or obvious placeholder IDs that break real monitoring."""
    text = str(value or "").strip()
    if not text:
        return False
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return False
    invalid = {
        "1234567890",
        "123456789",
        "12345678",
        "0123456789",
        "0000000000",
        "000000000",
        "00000000",
    }
    if digits in invalid:
        return False
    return len(set(digits)) != 1


def _resolve_plate() -> str:
    runt_cache = _load_cache("co.runt")
    if not runt_cache:
        return ""
    return (((runt_cache or {}).get("data") or {}).get("placa", "")) or ""


def _resolve_vehicle_identity() -> dict[str, str]:
    """Resolve best-effort live make/model/year for custom vehicle sources."""
    cfg = load_config()
    current_vin = cfg.general.default_vin or ""

    def _matching_cache(source_id: str) -> dict[str, Any]:
        cached = _load_cache(source_id) or {}
        data = cached.get("data") or {}
        cached_vin = str(data.get("vin") or "").strip()
        if source_id == "vin.decode" and current_vin and cached_vin and cached_vin != current_vin:
            return {}
        if source_id == "us.nhtsa_vin" and current_vin and cached_vin and cached_vin != current_vin:
            return {}
        return data if isinstance(data, dict) else {}

    order_data = ((_load_cache("tesla.order") or {}).get("data") or {}) if current_vin else {}
    vin_data = _matching_cache("vin.decode")
    nhtsa_data = _matching_cache("us.nhtsa_vin")

    model_code = str(order_data.get("modelCode") or "").lower()
    model_fallbacks = {
        "my": "Model Y",
        "m3": "Model 3",
        "ms": "Model S",
        "mx": "Model X",
        "cybertruck": "Cybertruck",
    }

    make = (
        str(vin_data.get("manufacturer") or "").split("(", 1)[0].replace("Inc.", "").strip()
        or str(nhtsa_data.get("make") or "").strip()
        or "TESLA"
    )
    model = (
        str(vin_data.get("model") or "").strip()
        or str(nhtsa_data.get("model") or "").strip()
        or model_fallbacks.get(model_code, "")
    )
    year = (
        str(vin_data.get("model_year") or "").strip()
        or str(nhtsa_data.get("model_year") or "").strip()
    )
    return {"make": make, "model": model, "year": year}


def _resolve_template_value(value: Any) -> Any:
    """Resolve placeholder values in openquery params using live source state."""
    if isinstance(value, dict):
        return {key: _resolve_template_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_template_value(item) for item in value]
    if not isinstance(value, str):
        return value

    if value == "$VIN":
        return load_config().general.default_vin or ""
    if value == "$CEDULA":
        return _resolve_owner_cedula()
    if value == "$PLACA":
        return _resolve_plate()
    if value in {"$MAKE", "$MODEL", "$YEAR"}:
        identity = _resolve_vehicle_identity()
        return {
            "$MAKE": identity.get("make", ""),
            "$MODEL": identity.get("model", ""),
            "$YEAR": identity.get("year", ""),
        }[value]
    return value


def _current_query_context(source_id: str, src: SourceDef) -> dict[str, Any]:
    if src.openquery_source:
        params = dict(src.openquery_params)
        doc_number = _resolve_template_value(params.get("doc_number", ""))
        return {
            "openquery_source": src.openquery_source,
            "doc_type": params.get("doc_type", "custom"),
            "doc_number": doc_number,
            "extra": _resolve_template_value(params.get("extra", {})),
        }
    cfg = load_config()
    if source_id == "vin.decode":
        return {"vin": cfg.general.default_vin or ""}
    if source_id in {"tesla.delivery", "tesla.tasks"}:
        order_cached = _load_cache("tesla.order") or {}
        portal_cached = _load_cache("tesla.portal") or {}
        return {
            "order_hash": _data_hash(order_cached.get("data")),
            "portal_hash": _data_hash(portal_cached.get("data")),
            "delivery_cache": _file_signature(CONFIG_DIR / "state" / "delivery.json"),
        }
    return {}


def _file_signature(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _data_hash(data: Any) -> str | None:
    """Return a stable short hash for persisted source payloads."""
    if data is None:
        return None
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()[:16]


# ── Refresh methods ──────────────────────────────────────────────────────────


def _refresh_subprocess(source_id: str, src: SourceDef) -> dict:
    """Refresh a Playwright-based source via subprocess."""
    query_context = _current_query_context(source_id, src)
    script = f"""
import json
from openquery.sources import get_source
from openquery.sources.base import DocumentType, QueryInput
from tesla_cli.core.config import load_config

cfg = load_config()
vin = cfg.general.default_vin or ""
src = get_source("{src.openquery_source}")
params = {json.dumps(src.openquery_params)}
query_context = {json.dumps(query_context)}

# Build query input
resolved_doc_type = query_context.get("doc_type") or params.get("doc_type", "custom")
resolved_doc_number = query_context.get("doc_number") or ""
extra = query_context.get("extra") or params.get("extra", {{}})

if not resolved_doc_number:
    doc_number = params.get("doc_number", "")
    if doc_number == "$VIN":
        resolved_doc_number = vin
    elif doc_number == "$CEDULA":
        resolved_doc_number = cfg.general.cedula or ""
    elif doc_number == "$PLACA":
        import pathlib
        runt_cache = pathlib.Path.home() / ".tesla-cli" / "sources" / "co.runt.json"
        if runt_cache.exists():
            runt_data = json.loads(runt_cache.read_text()).get("data", {{}}) or {{}}
            resolved_doc_number = runt_data.get("placa", "")
    else:
        resolved_doc_number = doc_number

if not resolved_doc_number and resolved_doc_type == "cedula":
    print(json.dumps({{"error": "No cedula configured or resolved for co.simit."}}))
    import sys; sys.exit(0)

dt_map = {{"vin": DocumentType.VIN, "placa": DocumentType.PLATE, "cedula": DocumentType.CEDULA, "custom": DocumentType.CUSTOM}}
qi = QueryInput(document_type=dt_map.get(resolved_doc_type, DocumentType.CUSTOM), document_number=resolved_doc_number, extra=extra, audit=True)
result = src.query(qi)

# Save audit evidence to disk if present
if result.audit:
    from tesla_cli.core.sources import _save_audit
    from datetime import datetime, timezone
    _save_audit("{source_id}", result.audit, datetime.now(timezone.utc).isoformat())

print(json.dumps(result.model_dump(exclude={{"audit"}}), default=str))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            cached = _save_cache(source_id, data, query_context=query_context)
            cached["_query_meta"] = {
                "mode": "openquery_subprocess",
                "openquery_source": src.openquery_source,
                "openquery_params": src.openquery_params,
                "subprocess_returncode": result.returncode,
                "raw_output_excerpt": result.stdout.strip()[:2000],
            }
            return cached
        else:
            err = result.stderr.strip()[-200:] if result.stderr else "subprocess failed"
            log.debug("Source %s subprocess failed: %s", source_id, err)
            cached = _save_cache(source_id, None, error=err, query_context=query_context)
            cached["_query_meta"] = {
                "mode": "openquery_subprocess",
                "openquery_source": src.openquery_source,
                "openquery_params": src.openquery_params,
                "subprocess_returncode": result.returncode,
                "raw_error_excerpt": result.stderr.strip()[-2000:] if result.stderr else err,
            }
            return cached
    except subprocess.TimeoutExpired:
        cached = _save_cache(
            source_id,
            None,
            error="Query timed out (120s)",
            query_context=query_context,
        )
        cached["_query_meta"] = {
            "mode": "openquery_subprocess",
            "openquery_source": src.openquery_source,
            "openquery_params": src.openquery_params,
            "timeout_seconds": 120,
        }
        return cached
    except Exception as exc:
        cached = _save_cache(source_id, None, error=str(exc), query_context=query_context)
        cached["_query_meta"] = {
            "mode": "openquery_subprocess",
            "openquery_source": src.openquery_source,
            "openquery_params": src.openquery_params,
        }
        return cached


def _refresh_openquery_inline(source_id: str, src: SourceDef) -> dict:
    """Refresh a non-Playwright openquery source inline."""
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        query_context = _current_query_context(source_id, src)
        doc_number = query_context.get("doc_number", "")

        dt_map = {
            "vin": DocumentType.VIN,
            "placa": DocumentType.PLATE,
            "cedula": DocumentType.CEDULA,
            "custom": DocumentType.CUSTOM,
        }
        qi = QueryInput(
            document_type=dt_map.get(query_context.get("doc_type", "custom"), DocumentType.CUSTOM),
            document_number=doc_number,
            extra=query_context.get("extra", {}),
        )
        oq_src = get_source(src.openquery_source)
        result = oq_src.query(qi)
        data = result.model_dump(exclude={"audit"})
        cached = _save_cache(source_id, data, query_context=query_context)
        cached["_query_meta"] = {
            "mode": "openquery_inline",
            "openquery_source": src.openquery_source,
            "openquery_params": src.openquery_params,
            "query_input": qi.model_dump(mode="json") if hasattr(qi, "model_dump") else {},
        }
        return cached
    except Exception as exc:
        cached = _save_cache(
            source_id,
            None,
            error=str(exc),
            query_context=_current_query_context(source_id, src),
        )
        cached["_query_meta"] = {
            "mode": "openquery_inline",
            "openquery_source": src.openquery_source,
            "openquery_params": src.openquery_params,
        }
        return cached


def _append_query(source_id: str, src: SourceDef, result: dict, query_meta: dict | None = None) -> None:
    """Append a query audit entry for one source refresh attempt."""
    QUERIES_DIR.mkdir(parents=True, exist_ok=True)
    query_file = QUERIES_DIR / f"{source_id}.jsonl"
    data = result.get("data")
    error = result.get("error")
    entry = {
        "queried_at": result.get("refreshed_at"),
        "source_id": source_id,
        "status": "error" if error else "ok",
        "request": {
            "mode": (query_meta or {}).get("mode", "unknown"),
            "source_name": src.name,
            "category": src.category,
            "country": src.country,
            "requires_auth": src.requires_auth,
            "uses_playwright": src.uses_playwright,
            "openquery_source": (query_meta or {}).get("openquery_source") or src.openquery_source,
            "openquery_params": (query_meta or {}).get("openquery_params") or src.openquery_params,
            "query_input": (query_meta or {}).get("query_input"),
            "auth_type": (query_meta or {}).get("auth_type"),
            "missing": (query_meta or {}).get("missing"),
            "url": (query_meta or {}).get("url"),
            "method": (query_meta or {}).get("method"),
            "status_code": (query_meta or {}).get("status_code"),
        },
        "response": {
            "error": error,
            "data_hash": _data_hash(data),
            "normalized_data": data,
            "raw_output_excerpt": (query_meta or {}).get("raw_output_excerpt"),
            "raw_error_excerpt": (query_meta or {}).get("raw_error_excerpt"),
            "response_text_excerpt": (query_meta or {}).get("response_text_excerpt"),
            "subprocess_returncode": (query_meta or {}).get("subprocess_returncode"),
            "timeout_seconds": (query_meta or {}).get("timeout_seconds"),
        },
    }
    with open(query_file, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def append_query_audit(source_id: str, result: dict, query_meta: dict | None = None) -> None:
    """Public wrapper for routes or workers that bypass refresh_source."""
    src = get_source_def(source_id)
    if not src:
        return
    _append_query(source_id, src, result, query_meta)


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

        cfg = load_config()
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

        cfg = load_config()
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
                log.warning("Failed to enrich tesla.order source with tasks/delivery", exc_info=True)

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
            order_result = refresh_source("tesla.order", _skip_dependents=True)
            order_data = (order_result.get("data") or {}) if isinstance(order_result, dict) else {}
        delivery = order_data.get("delivery") or {}
        if not isinstance(delivery, dict):
            delivery = {}
        return delivery, {"mode": "derived_from_source", "derived_from": ["tesla.order", "tesla.portal"]}

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
            order_result = refresh_source("tesla.order", _skip_dependents=True)
            order_data = (order_result.get("data") or {}) if isinstance(order_result, dict) else {}
        tasks = _normalize_tesla_tasks(order_data.get("tasks") or {})
        return tasks, {"mode": "derived_from_source", "derived_from": ["tesla.order", "tesla.portal"]}

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
            name="Estado Cédula",
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
    cfg = load_config()
    country = cfg.general.country
    if country:
        _register_country_sources(country)
    else:
        # Backward-compatibility: when no country is set, register CO + US sources
        # so existing users don't lose functionality
        _register_country_sources("CO")
        _register_country_sources("US")


# Auto-register on import
_register_defaults()
