"""Data Sources API: /api/sources/* — independent data source management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.core import sources

router = APIRouter()


@router.get("")
def sources_list() -> list:
    """List all registered data sources with status and freshness."""
    return sources.list_sources()


@router.get("/missing-auth")
def sources_missing_auth() -> list:
    """Sources that need authentication the user hasn't provided."""
    return sources.missing_auth()


@router.get("/{source_id}")
def source_get(source_id: str) -> dict:
    """Get cached data for a specific source."""
    result = sources.get_cached_with_meta(source_id)
    if result is None:
        raise HTTPException(404, f"Unknown source: {source_id}")
    return result


@router.post("/{source_id}/refresh")
def source_refresh(source_id: str) -> dict:
    """Refresh a specific source. May take 3-60s depending on the source."""
    src = sources.get_source_def(source_id)
    if not src:
        raise HTTPException(404, f"Unknown source: {source_id}")
    return sources.refresh_source(source_id)


@router.post("/refresh-stale")
def sources_refresh_stale() -> dict:
    """Refresh all stale sources."""
    return sources.refresh_stale()
