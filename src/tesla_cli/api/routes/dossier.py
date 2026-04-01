"""Dossier API routes: /api/dossier/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.core.config import load_config, resolve_vin

router = APIRouter()


@router.get("")
def dossier_cached() -> dict:
    """Load the cached dossier from disk (fast, <100ms).

    Returns the full VehicleDossier JSON from the last build.
    Returns 404 if no dossier has been built yet.
    """
    from tesla_cli.core.backends.dossier import DossierBackend

    backend = DossierBackend()
    dossier = backend._load_dossier()
    if not dossier:
        raise HTTPException(
            status_code=404,
            detail="No dossier built yet. Call GET /api/dossier/refresh to build.",
        )
    return dossier.model_dump(mode="json")


@router.get("/refresh")
def dossier_refresh() -> dict:
    """Rebuild the full dossier from all sources (slow, 5-15s).

    Aggregates data from Tesla API, VIN decode, RUNT, ship tracking,
    NHTSA recalls, EPA, and more. Saves to disk for future cached reads.
    """
    from tesla_cli.core.backends.dossier import DossierBackend

    try:
        backend = DossierBackend()
        dossier = backend.build_dossier()
        return dossier.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/runt")
def dossier_runt() -> dict:
    """Live RUNT query (Colombia vehicle registry, 3-5s).

    Queries by VIN from config. Returns RuntData JSON.
    """
    from tesla_cli.core.backends.runt import RuntBackend, RuntError

    cfg = load_config()
    vin = resolve_vin(cfg, None)
    if not vin:
        raise HTTPException(status_code=404, detail="No VIN configured.")
    try:
        backend = RuntBackend(timeout=30)
        return backend.query_by_vin(vin).model_dump(mode="json")
    except RuntError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/simit")
def dossier_simit() -> dict:
    """Live SIMIT query (Colombia traffic fines, 3-5s).

    Attempts to find cedula from cached dossier or config.
    Returns SimitData JSON.
    """
    import json
    from pathlib import Path

    from tesla_cli.core.backends.simit import SimitBackend, SimitError

    # Try to get cedula from cached dossier
    cedula = None
    from tesla_cli.core.backends.dossier import DossierBackend

    db = DossierBackend()
    dossier = db._load_dossier()
    if dossier and dossier.runt.no_identificacion:
        cedula = dossier.runt.no_identificacion

    # Fallback: mission-control-data.json
    if not cedula:
        mc_file = Path(__file__).parent.parent.parent.parent / "mission-control-data.json"
        if mc_file.exists():
            try:
                mc = json.loads(mc_file.read_text())
                if mc.get("simit_cedula"):
                    cedula = mc["simit_cedula"]
            except Exception:
                pass

    if not cedula:
        raise HTTPException(
            status_code=404,
            detail="No cédula found. Build dossier with RUNT first, or set simit_cedula in mission-control-data.json.",
        )

    try:
        backend = SimitBackend(timeout=30)
        return backend.query_by_cedula(cedula).model_dump(mode="json")
    except SimitError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
