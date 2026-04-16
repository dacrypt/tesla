"""Data Sources API: /api/sources/* — independent data source management."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tesla_cli.core import sources
from tesla_cli.core.config import load_config, save_config

router = APIRouter()

_SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9._-]+$")


def _validate_source_id(source_id: str) -> None:
    if not _SOURCE_ID_RE.match(source_id):
        raise HTTPException(400, "Invalid source ID")


@router.get("")
def sources_list() -> list:
    """List all registered data sources with status and freshness."""
    return sources.list_sources()


@router.get("/missing-auth")
def sources_missing_auth() -> list:
    """Sources that need authentication the user hasn't provided."""
    return sources.missing_auth()


class ConfigUpdate(BaseModel):
    cedula: str | None = None
    vin: str | None = None


@router.get("/config")
def get_source_config() -> dict:
    """Get config values used by sources."""
    cfg = load_config()
    return {
        "cedula": cfg.general.cedula or "",
        "vin": cfg.general.default_vin or "",
        "reservation_number": cfg.order.reservation_number or "",
    }


@router.post("/config")
def update_source_config(req: ConfigUpdate) -> dict:
    """Update config values needed by sources (cedula, VIN, etc.)."""
    cfg = load_config()
    changed = []
    if req.cedula is not None:
        cfg.general.cedula = req.cedula
        changed.append("cedula")
    if req.vin is not None:
        cfg.general.default_vin = req.vin
        changed.append("vin")
    if changed:
        save_config(cfg)
    return {"ok": True, "changed": changed}


@router.get("/{source_id}/history")
def source_history(source_id: str, limit: int = 50) -> list:
    """History of data changes for a source."""
    _validate_source_id(source_id)
    return sources.get_history(source_id, limit)


@router.get("/{source_id}/diffs")
def source_diffs(source_id: str, limit: int = 50) -> list:
    """Structured diff log for a source."""
    _validate_source_id(source_id)
    return sources.get_diffs(source_id, limit)


@router.get("/{source_id}/queries")
def source_queries(source_id: str, limit: int = 50) -> list:
    """Query audit trail for a source."""
    _validate_source_id(source_id)
    return sources.get_queries(source_id, limit)


@router.get("/{source_id}/audits")
def source_audits(source_id: str) -> list:
    """List available audit/evidence PDFs for a source."""
    _validate_source_id(source_id)
    return sources.get_audits(source_id)


@router.get("/{source_id}/audit/{filename}")
def source_audit_pdf(source_id: str, filename: str):
    """Download an audit evidence PDF."""
    from fastapi.responses import FileResponse

    from tesla_cli.core.config import CONFIG_DIR

    _validate_source_id(source_id)
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    pdf_path = CONFIG_DIR / "source_audits" / filename
    if not pdf_path.exists() or not filename.startswith(source_id):
        raise HTTPException(404, "Audit PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


@router.post("/refresh-stale")
def sources_refresh_stale() -> dict:
    """Refresh all stale sources."""
    return sources.refresh_stale()


@router.get("/by-profile")
def sources_by_profile() -> dict:
    """Sources grouped by vehicle and driver profile."""
    all_sources = sources.list_sources()
    return {
        "vehicle": [
            s for s in all_sources if s["category"] in ("vehiculo", "registro", "servicios")
        ],
        "driver": [s for s in all_sources if s["category"] in ("infracciones", "registro")],
        "financial": [s for s in all_sources if s["category"] == "financiero"],
    }


# ── Wildcard routes LAST ──


@router.get("/{source_id}")
def source_get(source_id: str) -> dict:
    """Get cached data for a specific source."""
    _validate_source_id(source_id)
    result = sources.get_cached_with_meta(source_id)
    if result is None:
        raise HTTPException(404, f"Unknown source: {source_id}")
    return result


@router.post("/{source_id}/refresh")
def source_refresh(source_id: str) -> dict:
    """Refresh a specific source. May take 3-60s depending on the source."""
    _validate_source_id(source_id)
    src = sources.get_source_def(source_id)
    if not src:
        raise HTTPException(404, f"Unknown source: {source_id}")
    return sources.refresh_source(source_id)
