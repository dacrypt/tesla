"""/api/doctor — per-feature health report (offline-safe, read-only)."""

from __future__ import annotations

from fastapi import APIRouter

from tesla_cli.core.health.features import probe_all

router = APIRouter()


@router.get("")
def get_doctor() -> list[dict]:
    """List each registered feature with `status` and optional `remediation`.

    `status` is one of: `ok`, `missing-scope`, `external-blocker`, `not-configured`.
    Offline-safe — never contacts Tesla and never wakes the vehicle.
    """
    return probe_all()
