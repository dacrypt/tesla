"""Drivers API routes: /api/drivers/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tesla_cli.core.db import (
    add_driver,
    assign_vehicle,
    delete_driver,
    get_driver,
    get_drivers,
    get_vehicle_drivers,
    unassign_vehicle,
    update_driver,
)

router = APIRouter()


class DriverCreate(BaseModel):
    doc_number: str
    name: str = ""
    doc_type: str = "CC"
    email: str = ""
    phone: str = ""
    license_number: str = ""
    license_categories: str = ""
    license_expiry: str = ""
    license_status: str = ""


class DriverUpdate(BaseModel):
    name: str | None = None
    doc_type: str | None = None
    email: str | None = None
    phone: str | None = None
    license_number: str | None = None
    license_categories: str | None = None
    license_expiry: str | None = None
    license_status: str | None = None


class VehicleAssignment(BaseModel):
    vin: str
    role: str = "owner"
    alias: str = ""


# ── Driver CRUD ──────────────────────────────────────────────────────────────


@router.get("")
def list_drivers() -> list[dict]:
    """List all drivers with their vehicle assignments."""
    return get_drivers()


@router.post("")
def create_driver(body: DriverCreate) -> dict:
    """Add a new driver."""
    if not body.doc_number.strip():
        raise HTTPException(status_code=422, detail="doc_number is required")
    existing = get_driver(body.doc_number)
    if existing:
        raise HTTPException(status_code=409, detail="Driver already exists")
    return add_driver(**body.model_dump())


@router.get("/{doc_number}")
def read_driver(doc_number: str) -> dict:
    """Get a driver by document number."""
    d = get_driver(doc_number)
    if not d:
        raise HTTPException(status_code=404, detail="Driver not found")
    return d


@router.put("/{doc_number}")
def modify_driver(doc_number: str, body: DriverUpdate) -> dict:
    """Update driver fields."""
    d = update_driver(doc_number, **body.model_dump(exclude_none=True))
    if not d:
        raise HTTPException(status_code=404, detail="Driver not found")
    return d


@router.delete("/{doc_number}")
def remove_driver(doc_number: str) -> dict:
    """Delete a driver."""
    if not delete_driver(doc_number):
        raise HTTPException(status_code=404, detail="Driver not found")
    return {"ok": True}


# ── Vehicle assignments ──────────────────────────────────────────────────────


@router.post("/{doc_number}/vehicles")
def add_vehicle_assignment(doc_number: str, body: VehicleAssignment) -> dict:
    """Assign a vehicle to a driver."""
    if not assign_vehicle(doc_number, body.vin, body.role, body.alias):
        raise HTTPException(status_code=404, detail="Driver not found")
    return {"ok": True}


@router.delete("/{doc_number}/vehicles/{vin}")
def remove_vehicle_assignment(doc_number: str, vin: str) -> dict:
    """Remove a vehicle assignment."""
    if not unassign_vehicle(doc_number, vin):
        raise HTTPException(status_code=404, detail="Driver or assignment not found")
    return {"ok": True}


@router.get("/by-vehicle/{vin}")
def vehicle_drivers(vin: str) -> list[dict]:
    """Get all drivers assigned to a vehicle."""
    return get_vehicle_drivers(vin)
