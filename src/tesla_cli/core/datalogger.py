"""Native telemetry data logger — polls Tesla Fleet API and stores in SQLite.

Replaces TeslaMate with a zero-dependency, zero-Docker solution that uses
our own tokens and schema. Detects drives and charging sessions automatically.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tesla_cli.core.config import CONFIG_DIR

log = logging.getLogger("tesla-cli.datalogger")

DEFAULT_DB_PATH = CONFIG_DIR / "telemetry.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vin TEXT UNIQUE, name TEXT, model TEXT,
    trim_badging TEXT, exterior_color TEXT, efficiency REAL
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    latitude REAL, longitude REAL,
    speed INTEGER, heading INTEGER, power INTEGER,
    odometer REAL, battery_level INTEGER,
    ideal_range_km REAL, rated_range_km REAL,
    inside_temp REAL, outside_temp REAL,
    software_version TEXT,
    car_id INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS drives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL, end_date TEXT,
    start_position_id INTEGER, end_position_id INTEGER,
    start_address TEXT, end_address TEXT,
    distance REAL, duration_min INTEGER,
    start_ideal_range_km REAL, end_ideal_range_km REAL,
    speed_max INTEGER, power_max INTEGER, power_min INTEGER,
    outside_temp_avg REAL, inside_temp_avg REAL,
    car_id INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS charges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL, end_date TEXT,
    start_battery_level INTEGER, end_battery_level INTEGER,
    charge_energy_added REAL, cost REAL,
    start_ideal_range_km REAL, end_ideal_range_km REAL,
    duration_min INTEGER, address TEXT,
    charger_power INTEGER, charger_voltage INTEGER,
    car_id INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL, end_date TEXT,
    version TEXT, car_id INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS geocode_cache (
    lat_lon TEXT PRIMARY KEY,
    display_name TEXT,
    cached_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_positions_date ON positions(date);
CREATE INDEX IF NOT EXISTS idx_drives_date ON drives(start_date);
CREATE INDEX IF NOT EXISTS idx_charges_date ON charges(start_date);
"""


class DataLogger:
    """Polls Tesla Fleet API and logs telemetry to SQLite."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        backend: Any = None,
        vin: str = "",
        car_id: int = 1,
    ) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._backend = backend
        self._vin = vin
        self._car_id = car_id

        # State tracking for drive/charge detection
        self._active_drive_id: int | None = None
        self._active_charge_id: int | None = None
        self._last_software: str | None = None
        self._idle_since: float | None = None

        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def poll_once(self) -> dict | None:
        """Single poll: fetch vehicle data, store, detect events."""
        if not self._backend or not self._vin:
            return None
        try:
            data = self._backend.get_vehicle_data(self._vin)
        except Exception as exc:
            log.debug("Poll failed: %s", exc)
            return None

        now = datetime.now(timezone.utc).isoformat()
        ds = data.get("drive_state") or {}
        cs = data.get("charge_state") or {}
        cl = data.get("climate_state") or {}
        vs = data.get("vehicle_state") or {}

        # Save position
        pos_id = self._save_position(now, ds, cs, cl, vs)

        # Detect drive start/end
        self._detect_drive(now, ds, cs, pos_id)

        # Detect charge start/end
        self._detect_charge(now, cs, ds)

        # Detect software update
        self._detect_update(now, vs)

        return data

    def run(self, interval: int = 30) -> None:
        """Blocking polling loop."""
        self._running = True
        log.info("Data logger started (interval=%ds, vin=%s)", interval, self._vin[-6:] if self._vin else "?")

        # Ensure car exists
        self._ensure_car()

        while self._running:
            try:
                self.poll_once()
            except Exception as exc:
                log.warning("Poll error: %s", exc)
            time.sleep(interval)

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def get_db_stats(self) -> dict:
        """Return counts and DB file size."""
        cur = self._conn.cursor()
        stats: dict[str, Any] = {}
        for table in ("positions", "drives", "charges", "updates", "cars"):
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            stats[table] = cur.fetchone()[0]
        stats["db_size_mb"] = round(self.db_path.stat().st_size / 1_048_576, 2) if self.db_path.exists() else 0
        return stats

    # ------------------------------------------------------------------
    # Internal: save position
    # ------------------------------------------------------------------

    def _save_position(self, now: str, ds: dict, cs: dict, cl: dict, vs: dict) -> int:
        cur = self._conn.execute(
            """INSERT INTO positions
               (date, latitude, longitude, speed, heading, power, odometer,
                battery_level, ideal_range_km, rated_range_km,
                inside_temp, outside_temp, software_version, car_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                now,
                ds.get("latitude"), ds.get("longitude"),
                ds.get("speed") or 0, ds.get("heading"), ds.get("power"),
                vs.get("odometer"),
                cs.get("battery_level"),
                cs.get("ideal_battery_range") and round(cs["ideal_battery_range"] * 1.60934, 2),
                cs.get("battery_range") and round(cs["battery_range"] * 1.60934, 2),
                cl.get("inside_temp"), cl.get("outside_temp"),
                vs.get("car_version"),
                self._car_id,
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal: drive detection
    # ------------------------------------------------------------------

    def _detect_drive(self, now: str, ds: dict, cs: dict, pos_id: int) -> None:
        speed = ds.get("speed") or 0
        shift = ds.get("shift_state")
        is_driving = speed > 0 or shift in ("D", "R", "N")

        if is_driving and self._active_drive_id is None:
            # Start new drive
            self._idle_since = None
            range_km = cs.get("ideal_battery_range")
            if range_km:
                range_km = round(range_km * 1.60934, 2)
            cur = self._conn.execute(
                "INSERT INTO drives (start_date, start_position_id, start_ideal_range_km, car_id) VALUES (?,?,?,?)",
                (now, pos_id, range_km, self._car_id),
            )
            self._conn.commit()
            self._active_drive_id = cur.lastrowid
            log.info("Drive started (id=%d)", self._active_drive_id)

        elif is_driving and self._active_drive_id is not None:
            # Update active drive stats
            self._idle_since = None
            self._conn.execute(
                """UPDATE drives SET
                    end_position_id = ?,
                    speed_max = MAX(COALESCE(speed_max, 0), ?),
                    power_max = MAX(COALESCE(power_max, -999), ?),
                    power_min = MIN(COALESCE(power_min, 999), ?)
                   WHERE id = ?""",
                (pos_id, speed, ds.get("power") or 0, ds.get("power") or 0, self._active_drive_id),
            )
            self._conn.commit()

        elif not is_driving and self._active_drive_id is not None:
            # Might be stopping — wait 2 minutes of idle
            if self._idle_since is None:
                self._idle_since = time.monotonic()
            elif time.monotonic() - self._idle_since > 120:
                self._close_drive(now, ds, cs, pos_id)

    def _close_drive(self, now: str, ds: dict, cs: dict, pos_id: int) -> None:
        if self._active_drive_id is None:
            return
        range_km = cs.get("ideal_battery_range")
        if range_km:
            range_km = round(range_km * 1.60934, 2)

        # Calculate distance from odometer or positions
        row = self._conn.execute(
            "SELECT start_date, start_ideal_range_km FROM drives WHERE id = ?",
            (self._active_drive_id,),
        ).fetchone()
        start_date = row["start_date"] if row else now
        start_range = row["start_ideal_range_km"] if row else None
        distance = round(start_range - range_km, 1) if start_range and range_km else None
        duration = self._minutes_between(start_date, now)

        # Geocode start/end
        start_addr = self._geocode_position(self._active_drive_id, "start_position_id")
        end_addr = self._geocode_from_ds(ds)

        self._conn.execute(
            """UPDATE drives SET
                end_date = ?, end_position_id = ?, end_ideal_range_km = ?,
                distance = ?, duration_min = ?,
                start_address = ?, end_address = ?
               WHERE id = ?""",
            (now, pos_id, range_km, distance, duration, start_addr, end_addr, self._active_drive_id),
        )
        self._conn.commit()
        log.info("Drive ended (id=%d, %.1f km, %d min)", self._active_drive_id, distance or 0, duration or 0)
        self._active_drive_id = None
        self._idle_since = None

    # ------------------------------------------------------------------
    # Internal: charge detection
    # ------------------------------------------------------------------

    def _detect_charge(self, now: str, cs: dict, ds: dict) -> None:
        charging_state = cs.get("charging_state", "")

        if charging_state == "Charging" and self._active_charge_id is None:
            # Start charge
            self._active_charge_id = self._conn.execute(
                """INSERT INTO charges
                   (start_date, start_battery_level, start_ideal_range_km,
                    charger_power, charger_voltage, address, car_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    now,
                    cs.get("battery_level"),
                    cs.get("ideal_battery_range") and round(cs["ideal_battery_range"] * 1.60934, 2),
                    cs.get("charger_power"),
                    cs.get("charger_voltage"),
                    self._geocode_from_ds(ds),
                    self._car_id,
                ),
            ).lastrowid
            self._conn.commit()
            log.info("Charge started (id=%d)", self._active_charge_id)

        elif charging_state == "Charging" and self._active_charge_id is not None:
            # Update charge stats
            self._conn.execute(
                "UPDATE charges SET charger_power = MAX(COALESCE(charger_power, 0), ?) WHERE id = ?",
                (cs.get("charger_power") or 0, self._active_charge_id),
            )
            self._conn.commit()

        elif charging_state in ("Complete", "Disconnected", "Stopped", "") and self._active_charge_id is not None:
            # End charge
            row = self._conn.execute(
                "SELECT start_date, start_battery_level, start_ideal_range_km FROM charges WHERE id = ?",
                (self._active_charge_id,),
            ).fetchone()
            duration = self._minutes_between(row["start_date"], now) if row else None
            end_range = cs.get("ideal_battery_range")
            if end_range:
                end_range = round(end_range * 1.60934, 2)

            self._conn.execute(
                """UPDATE charges SET
                    end_date = ?, end_battery_level = ?, end_ideal_range_km = ?,
                    charge_energy_added = ?, duration_min = ?
                   WHERE id = ?""",
                (
                    now,
                    cs.get("battery_level"),
                    end_range,
                    cs.get("charge_energy_added"),
                    duration,
                    self._active_charge_id,
                ),
            )
            self._conn.commit()
            log.info("Charge ended (id=%d, +%.1f kWh)", self._active_charge_id, cs.get("charge_energy_added") or 0)
            self._active_charge_id = None

    # ------------------------------------------------------------------
    # Internal: software update detection
    # ------------------------------------------------------------------

    def _detect_update(self, now: str, vs: dict) -> None:
        version = vs.get("car_version")
        if not version or version == self._last_software:
            return

        if self._last_software is not None:
            # Version changed
            self._conn.execute(
                "INSERT INTO updates (start_date, version, car_id) VALUES (?,?,?)",
                (now, version, self._car_id),
            )
            self._conn.commit()
            log.info("Software update detected: %s → %s", self._last_software, version)

        self._last_software = version

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    def _ensure_car(self) -> None:
        """Insert car record if not exists."""
        row = self._conn.execute("SELECT id FROM cars WHERE id = ?", (self._car_id,)).fetchone()
        if not row:
            self._conn.execute(
                "INSERT INTO cars (id, vin) VALUES (?, ?)",
                (self._car_id, self._vin),
            )
            self._conn.commit()

    def _geocode_from_ds(self, ds: dict) -> str | None:
        """Reverse geocode from drive_state lat/lon."""
        lat, lon = ds.get("latitude"), ds.get("longitude")
        if lat is None or lon is None:
            return None
        return self._reverse_geocode(lat, lon)

    def _geocode_position(self, drive_id: int, pos_col: str) -> str | None:
        """Geocode a position referenced by a drive."""
        row = self._conn.execute(
            f"SELECT p.latitude, p.longitude FROM positions p "  # noqa: S608
            f"JOIN drives d ON d.{pos_col} = p.id WHERE d.id = ?",
            (drive_id,),
        ).fetchone()
        if not row or row["latitude"] is None:
            return None
        return self._reverse_geocode(row["latitude"], row["longitude"])

    def _reverse_geocode(self, lat: float, lon: float) -> str:
        """Reverse geocode with SQLite cache."""
        key = f"{lat:.4f},{lon:.4f}"
        cached = self._conn.execute(
            "SELECT display_name FROM geocode_cache WHERE lat_lon = ?", (key,)
        ).fetchone()
        if cached:
            return cached["display_name"]

        try:
            import httpx
            resp = httpx.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json", "zoom": 16},
                headers={"User-Agent": "tesla-cli/4.0"},
                timeout=5,
            )
            name = resp.json().get("display_name", f"{lat:.4f}, {lon:.4f}")
        except Exception:
            name = f"{lat:.4f}, {lon:.4f}"

        self._conn.execute(
            "INSERT OR REPLACE INTO geocode_cache (lat_lon, display_name, cached_at) VALUES (?,?,?)",
            (key, name, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        return name

    @staticmethod
    def _minutes_between(start_iso: str, end_iso: str) -> int | None:
        """Calculate minutes between two ISO datetime strings."""
        try:
            s = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            e = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
            return max(0, int((e - s).total_seconds() / 60))
        except Exception:
            return None
