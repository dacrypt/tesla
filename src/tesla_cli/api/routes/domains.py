"""Domain projection API: /api/domains/*."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.core import domains

router = APIRouter()


@router.get("")
def domains_list() -> list:
    """List all computed domain projections."""
    return domains.list_domains()


@router.get("/{domain_id}")
def domain_get(domain_id: str) -> dict:
    """Get one computed domain projection."""
    result = domains.get_domain(domain_id)
    if result is None:
        raise HTTPException(404, f"Unknown domain: {domain_id}")
    return result


@router.post("/{domain_id}/recompute")
def domain_recompute(domain_id: str) -> dict:
    """Recompute one domain projection and persist it."""
    if domains.get_domain(domain_id) is None:
        raise HTTPException(404, f"Unknown domain: {domain_id}")
    return domains.recompute_domain(domain_id)
