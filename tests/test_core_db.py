"""Tests for tesla_cli.core.db (SQLite drivers / vehicle assignments).

DB_PATH, CONFIG_DIR and the one-time migration flag are redirected per test,
so nothing touches ~/.tesla-cli.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from tesla_cli.core import db
from tesla_cli.core.config import Config

VIN_A = "5YJ3E1EA1PF000001"
VIN_B = "7SAYGDEF1TF123456"


def _cfg(cedula: str = "", vin: str = "") -> Config:
    cfg = Config()
    cfg.general.cedula = cedula
    cfg.general.default_vin = vin
    return cfg


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr(db, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(db, "DB_PATH", cfg_dir / "tesla.db")
    monkeypatch.setattr(db, "_migrated", False)
    cfg = _cfg()
    with patch("tesla_cli.core.config.load_config", return_value=cfg):
        yield cfg_dir / "tesla.db", cfg


def test_get_db_creates_file_and_tables(tmp_db):
    path, _ = tmp_db
    conn = db.get_db()
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert path.exists()
    assert {"drivers", "driver_vehicles"} <= tables
    assert db._migrated is True


def test_add_and_get_driver(tmp_db):
    d = db.add_driver("123", name="Ana", email="a@x.co", license_categories="B1")
    assert d["doc_number"] == "123"
    assert d["name"] == "Ana"
    assert d["doc_type"] == "CC"
    assert d["license_categories"] == "B1"
    assert d["vehicles"] == []
    assert db.get_driver("123")["id"] == d["id"]
    assert db.get_driver("nope") is None


def test_duplicate_doc_number_rejected(tmp_db):
    db.add_driver("123")
    with pytest.raises(sqlite3.IntegrityError):
        db.add_driver("123")


def test_get_drivers_with_vehicles(tmp_db):
    db.add_driver("1", name="A")
    db.add_driver("2", name="B")
    assert db.assign_vehicle("1", VIN_A, role="owner", alias="Blue")
    drivers = db.get_drivers()
    assert [d["name"] for d in drivers] == ["A", "B"]
    assert drivers[0]["vehicles"][0]["vin"] == VIN_A
    assert drivers[0]["vehicles"][0]["alias"] == "Blue"
    assert drivers[1]["vehicles"] == []


def test_update_driver_allowed_fields_only(tmp_db):
    db.add_driver("1", name="Old")
    # Unknown columns are ignored (they never reach the f-string SQL), None means "keep".
    out = db.update_driver("1", name="New", phone="555", id=999, created_at="x", email=None)
    assert out["name"] == "New"
    assert out["phone"] == "555"
    assert out["id"] != 999
    assert out["created_at"] != "x"
    assert out["email"] == ""


def test_update_driver_no_changes_returns_current(tmp_db):
    db.add_driver("1", name="Same")
    assert db.update_driver("1", bogus="x")["name"] == "Same"
    assert db.update_driver("missing") is None
    assert db.update_driver("missing", name="X") is None


def test_delete_driver_cascades_assignments(tmp_db):
    db.add_driver("1")
    db.assign_vehicle("1", VIN_A)
    assert db.delete_driver("1") is True
    assert db.get_driver("1") is None
    assert db.get_vehicle_drivers(VIN_A) == []
    assert db.delete_driver("1") is False


def test_assign_unknown_driver(tmp_db):
    assert db.assign_vehicle("ghost", VIN_A) is False
    assert db.unassign_vehicle("ghost", VIN_A) is False


def test_reassign_replaces_role(tmp_db):
    db.add_driver("1")
    db.assign_vehicle("1", VIN_A, role="driver")
    db.assign_vehicle("1", VIN_A, role="owner", alias="Mine")
    vehicles = db.get_driver("1")["vehicles"]
    assert len(vehicles) == 1
    assert vehicles[0]["role"] == "owner"
    assert vehicles[0]["alias"] == "Mine"


def test_unassign_vehicle(tmp_db):
    db.add_driver("1")
    db.assign_vehicle("1", VIN_A)
    db.assign_vehicle("1", VIN_B)
    assert db.unassign_vehicle("1", VIN_A) is True
    assert [v["vin"] for v in db.get_driver("1")["vehicles"]] == [VIN_B]


def test_vehicle_drivers_owner_first_and_primary(tmp_db):
    db.add_driver("d1", name="Driver")
    db.add_driver("o1", name="Owner")
    db.assign_vehicle("d1", VIN_A, role="driver")
    db.assign_vehicle("o1", VIN_A, role="owner")
    drivers = db.get_vehicle_drivers(VIN_A)
    assert [d["name"] for d in drivers] == ["Owner", "Driver"]
    assert drivers[0]["role"] == "owner"
    assert "vehicle_assigned_at" in drivers[0]
    assert db.get_primary_driver(VIN_A)["name"] == "Owner"


def test_primary_driver_without_owner(tmp_db):
    db.add_driver("d1", name="Only")
    db.assign_vehicle("d1", VIN_A, role="driver")
    assert db.get_primary_driver(VIN_A)["name"] == "Only"
    assert db.get_primary_driver(VIN_B) is None


# ── cedula migration ───────────────────────────────────────────────────────


def test_migration_creates_driver_and_assignment(tmp_db):
    _, cfg = tmp_db
    cfg.general.cedula = "1020304050"
    cfg.general.default_vin = VIN_A
    drivers = db.get_drivers()
    assert len(drivers) == 1
    assert drivers[0]["doc_number"] == "1020304050"
    assert drivers[0]["vehicles"][0]["vin"] == VIN_A
    assert drivers[0]["vehicles"][0]["role"] == "owner"


def test_migration_without_vin(tmp_db):
    _, cfg = tmp_db
    cfg.general.cedula = "99"
    assert db.get_driver("99")["vehicles"] == []


def test_migration_runs_once_per_process(tmp_db):
    _, cfg = tmp_db
    db.get_db().close()  # migrates with no cedula
    cfg.general.cedula = "77"
    assert db.get_driver("77") is None


def test_migration_skips_existing(tmp_db):
    _, cfg = tmp_db
    db.add_driver("55", name="Pre")
    db._migrated = False
    cfg.general.cedula = "55"
    drivers = db.get_drivers()
    assert len(drivers) == 1
    assert drivers[0]["name"] == "Pre"


def test_migration_errors_are_swallowed(tmp_db):
    with patch("tesla_cli.core.config.load_config", side_effect=RuntimeError("bad cfg")):
        conn = db.get_db()
        conn.close()
    assert db._migrated is True
