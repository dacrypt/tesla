"""SQLite database for tesla-cli — drivers, vehicles, and future data.

Database file: ~/.tesla-cli/tesla.db
Auto-creates tables on first access. Migrates cedula from config on init.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tesla_cli.core.config import CONFIG_DIR

log = logging.getLogger("tesla-cli.db")

DB_PATH = CONFIG_DIR / "tesla.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    doc_type TEXT NOT NULL DEFAULT 'CC',
    doc_number TEXT NOT NULL UNIQUE,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    license_number TEXT DEFAULT '',
    license_categories TEXT DEFAULT '',
    license_expiry TEXT DEFAULT '',
    license_status TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS driver_vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_id INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    vin TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'owner',
    alias TEXT DEFAULT '',
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(driver_id, vin)
);
"""

_migrated = False


def get_db() -> sqlite3.Connection:
    """Get a database connection. Creates tables and migrates on first call."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)

    global _migrated
    if not _migrated:
        _migrate_cedula_from_config(conn)
        _migrated = True

    return conn


def _migrate_cedula_from_config(conn: sqlite3.Connection) -> None:
    """One-time migration: if config has cedula, create a driver entry."""
    try:
        from tesla_cli.core.config import load_config

        cfg = load_config()
        cedula = cfg.general.cedula
        vin = cfg.general.default_vin
        if not cedula:
            return

        # Check if already migrated
        row = conn.execute("SELECT id FROM drivers WHERE doc_number = ?", (cedula,)).fetchone()
        if row:
            return

        conn.execute(
            "INSERT INTO drivers (name, doc_type, doc_number) VALUES (?, 'CC', ?)",
            ("", cedula),
        )
        driver_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        if vin:
            conn.execute(
                "INSERT OR IGNORE INTO driver_vehicles (driver_id, vin, role) VALUES (?, ?, 'owner')",
                (driver_id, vin),
            )
        conn.commit()
        log.info("Migrated cedula %s from config to database", cedula[:4] + "***")
    except Exception as exc:
        log.debug("Cedula migration skipped: %s", exc)


# ── Driver CRUD ──────────────────────────────────────────────────────────────


def add_driver(
    doc_number: str,
    name: str = "",
    doc_type: str = "CC",
    email: str = "",
    phone: str = "",
    license_number: str = "",
    license_categories: str = "",
    license_expiry: str = "",
    license_status: str = "",
) -> dict:
    """Add a new driver. Returns the created driver dict."""
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO drivers (name, doc_type, doc_number, email, phone,
               license_number, license_categories, license_expiry, license_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, doc_type, doc_number, email, phone,
             license_number, license_categories, license_expiry, license_status),
        )
        conn.commit()
        return get_driver(doc_number)  # type: ignore[return-value]
    finally:
        conn.close()


def get_drivers() -> list[dict]:
    """List all drivers with their vehicle assignments."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM drivers ORDER BY id").fetchall()
        drivers = [dict(r) for r in rows]
        for d in drivers:
            vehicles = conn.execute(
                "SELECT vin, role, alias, assigned_at FROM driver_vehicles WHERE driver_id = ?",
                (d["id"],),
            ).fetchall()
            d["vehicles"] = [dict(v) for v in vehicles]
        return drivers
    finally:
        conn.close()


def get_driver(doc_number: str) -> dict | None:
    """Get a driver by document number."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM drivers WHERE doc_number = ?", (doc_number,)).fetchone()
        if not row:
            return None
        d = dict(row)
        vehicles = conn.execute(
            "SELECT vin, role, alias, assigned_at FROM driver_vehicles WHERE driver_id = ?",
            (d["id"],),
        ).fetchall()
        d["vehicles"] = [dict(v) for v in vehicles]
        return d
    finally:
        conn.close()


def update_driver(doc_number: str, **fields: Any) -> dict | None:
    """Update driver fields. Returns updated driver or None if not found."""
    allowed = {"name", "doc_type", "email", "phone",
               "license_number", "license_categories", "license_expiry", "license_status"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_driver(doc_number)

    conn = get_db()
    try:
        sets = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [doc_number]
        conn.execute(
            f"UPDATE drivers SET {sets}, updated_at = datetime('now') WHERE doc_number = ?",
            values,
        )
        conn.commit()
        return get_driver(doc_number)
    finally:
        conn.close()


def delete_driver(doc_number: str) -> bool:
    """Delete a driver and their vehicle assignments."""
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM drivers WHERE doc_number = ?", (doc_number,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM driver_vehicles WHERE driver_id = ?", (row["id"],))
        conn.execute("DELETE FROM drivers WHERE id = ?", (row["id"],))
        conn.commit()
        return True
    finally:
        conn.close()


# ── Vehicle assignments ──────────────────────────────────────────────────────


def assign_vehicle(doc_number: str, vin: str, role: str = "owner", alias: str = "") -> bool:
    """Assign a vehicle to a driver with a role."""
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM drivers WHERE doc_number = ?", (doc_number,)).fetchone()
        if not row:
            return False
        conn.execute(
            "INSERT OR REPLACE INTO driver_vehicles (driver_id, vin, role, alias) VALUES (?, ?, ?, ?)",
            (row["id"], vin, role, alias),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def unassign_vehicle(doc_number: str, vin: str) -> bool:
    """Remove a vehicle assignment from a driver."""
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM drivers WHERE doc_number = ?", (doc_number,)).fetchone()
        if not row:
            return False
        conn.execute(
            "DELETE FROM driver_vehicles WHERE driver_id = ? AND vin = ?",
            (row["id"], vin),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_vehicle_drivers(vin: str) -> list[dict]:
    """Get all drivers assigned to a vehicle."""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT d.*, dv.role, dv.alias, dv.assigned_at as vehicle_assigned_at
               FROM drivers d
               JOIN driver_vehicles dv ON d.id = dv.driver_id
               WHERE dv.vin = ?
               ORDER BY dv.role = 'owner' DESC, dv.assigned_at""",
            (vin,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_primary_driver(vin: str) -> dict | None:
    """Get the owner or first driver for a vehicle."""
    drivers = get_vehicle_drivers(vin)
    if not drivers:
        return None
    # Prefer owner role
    for d in drivers:
        if d.get("role") == "owner":
            return d
    return drivers[0]
