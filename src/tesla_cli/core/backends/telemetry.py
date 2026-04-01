"""Telemetry backend — reads historical data from local SQLite database.

Drop-in replacement for the old TeslaMate PostgreSQL backend.
Same query API, same return types, but reads from our own SQLite telemetry DB.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from tesla_cli.core.config import CONFIG_DIR

DEFAULT_DB_PATH = CONFIG_DIR / "telemetry.db"


class TelemetryBackend:
    """Read-only query interface for the telemetry SQLite database."""

    def __init__(self, db_path: str | Path | None = None, car_id: int = 1) -> None:
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._car_id = car_id
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    @contextmanager
    def _cursor(self):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def ping(self) -> bool:
        try:
            with self._cursor() as cur:
                cur.execute("SELECT 1")
                return True
        except Exception:
            return False

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total_drives,
                    ROUND(COALESCE(SUM(distance), 0), 0) AS total_km,
                    ROUND(COALESCE(SUM(
                        MAX(0, COALESCE(start_ideal_range_km, 0) - COALESCE(end_ideal_range_km, 0)) * 0.16
                    ), 0), 1) AS total_kwh,
                    ROUND(COALESCE(AVG(distance), 0), 1) AS avg_km_per_trip,
                    ROUND(COALESCE(MAX(distance), 0), 1) AS longest_trip_km,
                    MIN(start_date) AS first_drive,
                    MAX(end_date) AS last_drive
                FROM drives WHERE car_id = ? AND end_date IS NOT NULL
            """, (self._car_id,))
            row = cur.fetchone()
        return dict(row) if row else {}

    def get_charging_stats(self) -> dict[str, Any]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total_sessions,
                    ROUND(COALESCE(SUM(charge_energy_added), 0), 1) AS total_kwh_added,
                    ROUND(COALESCE(SUM(cost), 0), 2) AS total_cost,
                    ROUND(COALESCE(AVG(charge_energy_added), 0), 1) AS avg_kwh_per_session,
                    MAX(start_date) AS last_session
                FROM charges WHERE car_id = ?
            """, (self._car_id,))
            row = cur.fetchone()
        return dict(row) if row else {}

    def get_trips(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT
                    id, start_date, end_date,
                    start_address, end_address,
                    ROUND(distance, 1) AS distance_km,
                    duration_min,
                    ROUND(start_ideal_range_km, 0) AS start_range_km,
                    ROUND(end_ideal_range_km, 0) AS end_range_km,
                    ROUND(MAX(0, COALESCE(start_ideal_range_km, 0) - COALESCE(end_ideal_range_km, 0)) * 0.16, 2) AS energy_kwh
                FROM drives
                WHERE car_id = ? AND end_date IS NOT NULL
                ORDER BY start_date DESC LIMIT ?
            """, (self._car_id, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_charging_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT
                    id, start_date, end_date,
                    ROUND(charge_energy_added, 2) AS energy_added_kwh,
                    ROUND(cost, 2) AS cost,
                    start_battery_level, end_battery_level,
                    address AS location
                FROM charges
                WHERE car_id = ?
                ORDER BY start_date DESC LIMIT ?
            """, (self._car_id, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_efficiency(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT
                    start_date, ROUND(distance, 1) AS distance_km, duration_min,
                    ROUND(MAX(0, COALESCE(start_ideal_range_km,0) - COALESCE(end_ideal_range_km,0)) * 0.16, 2) AS energy_kwh,
                    ROUND(MAX(0, COALESCE(start_ideal_range_km,0) - COALESCE(end_ideal_range_km,0)) * 0.16
                        / NULLIF(distance, 0) * 1000, 1) AS wh_per_km,
                    start_address, end_address
                FROM drives
                WHERE car_id = ? AND end_date IS NOT NULL AND distance > 0
                    AND start_ideal_range_km > end_ideal_range_km
                ORDER BY start_date DESC LIMIT ?
            """, (self._car_id, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_updates(self) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT id, start_date, end_date, version
                FROM updates WHERE car_id = ? ORDER BY start_date DESC
            """, (self._car_id,))
            return [dict(r) for r in cur.fetchall()]

    def get_cars(self) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM cars ORDER BY id")
            return [dict(r) for r in cur.fetchall()]

    def get_vampire_drain(self, days: int = 30) -> dict[str, Any]:
        with self._cursor() as cur:
            cur.execute("""
                WITH ordered AS (
                    SELECT end_date, end_ideal_range_km,
                        LEAD(start_ideal_range_km) OVER (ORDER BY start_date) AS next_start_range,
                        LEAD(start_date) OVER (ORDER BY start_date) AS next_start_date
                    FROM drives
                    WHERE car_id = ? AND end_date IS NOT NULL
                      AND start_date >= datetime('now', ?)
                )
                SELECT
                    DATE(end_date) AS date,
                    ROUND(AVG(MAX(0, end_ideal_range_km - COALESCE(next_start_range, end_ideal_range_km))), 2) AS avg_drain_km,
                    ROUND(AVG((JULIANDAY(next_start_date) - JULIANDAY(end_date)) * 24), 1) AS avg_parked_hours,
                    COUNT(*) AS periods
                FROM ordered
                WHERE next_start_range IS NOT NULL
                  AND (JULIANDAY(next_start_date) - JULIANDAY(end_date)) * 24 BETWEEN 0.5 AND 72
                GROUP BY DATE(end_date) ORDER BY date DESC
            """, (self._car_id, f"-{days} days"))
            rows = [dict(r) for r in cur.fetchall()]
        return {"days_analyzed": days, "daily": rows}

    def get_top_locations(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT end_address AS location, COUNT(*) AS visit_count,
                    ROUND(AVG(end_ideal_range_km), 0) AS avg_arrival_range_km
                FROM drives
                WHERE car_id = ? AND end_address IS NOT NULL AND end_date IS NOT NULL
                GROUP BY end_address ORDER BY visit_count DESC LIMIT ?
            """, (self._car_id, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_monthly_report(self, month: str) -> dict[str, Any]:
        month_start = f"{month}-01"
        with self._cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS trips,
                    ROUND(COALESCE(SUM(distance), 0), 1) AS total_km,
                    ROUND(COALESCE(SUM(duration_min), 0), 0) AS total_drive_min
                FROM drives
                WHERE car_id = ? AND end_date IS NOT NULL
                  AND start_date >= ? AND start_date < DATE(?, '+1 month')
            """, (self._car_id, month_start, month_start))
            driving = dict(cur.fetchone() or {})

            cur.execute("""
                SELECT COUNT(*) AS sessions,
                    ROUND(COALESCE(SUM(charge_energy_added), 0), 2) AS total_kwh_charged,
                    ROUND(COALESCE(SUM(cost), 0), 2) AS total_cost
                FROM charges
                WHERE car_id = ? AND start_date >= ? AND start_date < DATE(?, '+1 month')
            """, (self._car_id, month_start, month_start))
            charging = dict(cur.fetchone() or {})
        return {"month": month, "driving": driving, "charging": charging}

    def get_daily_energy(self, days: int = 30) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT DATE(start_date) AS date,
                    ROUND(SUM(charge_energy_added), 1) AS kwh,
                    COUNT(*) AS sessions
                FROM charges
                WHERE car_id = ? AND start_date >= datetime('now', ?)
                GROUP BY DATE(start_date) ORDER BY date ASC
            """, (self._car_id, f"-{days} days"))
            return [dict(r) for r in cur.fetchall()]

    def get_drive_days(self, days: int = 365) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT DATE(start_date) AS date, COUNT(*) AS drives,
                    ROUND(SUM(distance), 1) AS km
                FROM drives
                WHERE car_id = ? AND end_date IS NOT NULL AND distance IS NOT NULL
                  AND start_date >= datetime('now', ?)
                GROUP BY DATE(start_date) ORDER BY date ASC
            """, (self._car_id, f"-{days} days"))
            return [dict(r) for r in cur.fetchall()]

    def get_timeline(self, days: int = 30) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT 'drive' AS type, start_date, end_date,
                    ROUND(distance, 1) AS distance_km, NULL AS energy_added_kwh,
                    start_address AS summary
                FROM drives WHERE car_id = ? AND end_date IS NOT NULL
                    AND start_date >= datetime('now', ?)
                UNION ALL
                SELECT 'charge' AS type, start_date, end_date,
                    NULL AS distance_km, ROUND(charge_energy_added, 2) AS energy_added_kwh,
                    address AS summary
                FROM charges WHERE car_id = ?
                    AND start_date >= datetime('now', ?)
                UNION ALL
                SELECT 'update' AS type, start_date, NULL AS end_date,
                    NULL AS distance_km, NULL AS energy_added_kwh,
                    version AS summary
                FROM updates WHERE car_id = ?
                    AND start_date >= datetime('now', ?)
                ORDER BY start_date DESC
            """, (self._car_id, f"-{days} days", self._car_id, f"-{days} days", self._car_id, f"-{days} days"))
            return [dict(r) for r in cur.fetchall()]

    def get_trip_stats(self, days: int = 30) -> dict[str, Any]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS trips,
                    ROUND(COALESCE(SUM(distance), 0), 1) AS total_km,
                    ROUND(COALESCE(AVG(distance), 0), 1) AS avg_km,
                    ROUND(COALESCE(SUM(duration_min), 0), 0) AS total_min
                FROM drives
                WHERE car_id = ? AND end_date IS NOT NULL
                    AND start_date >= datetime('now', ?)
            """, (self._car_id, f"-{days} days"))
            summary = dict(cur.fetchone() or {})

            cur.execute("""
                SELECT start_address || ' → ' || end_address AS route,
                    COUNT(*) AS count, ROUND(AVG(distance), 0) AS avg_km
                FROM drives
                WHERE car_id = ? AND end_date IS NOT NULL
                    AND start_address IS NOT NULL AND end_address IS NOT NULL
                    AND start_date >= datetime('now', ?)
                GROUP BY route ORDER BY count DESC LIMIT 5
            """, (self._car_id, f"-{days} days"))
            top_routes = [dict(r) for r in cur.fetchall()]
        return {"summary": summary, "top_routes": top_routes, "days": days}

    def get_charging_locations(self, days: int = 90, limit: int = 10) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT address AS location, COUNT(*) AS sessions,
                    ROUND(SUM(charge_energy_added), 1) AS kwh_total,
                    MAX(start_date) AS last_visit
                FROM charges
                WHERE car_id = ? AND address IS NOT NULL
                    AND start_date >= datetime('now', ?)
                GROUP BY address ORDER BY sessions DESC LIMIT ?
            """, (self._car_id, f"-{days} days", limit))
            return [dict(r) for r in cur.fetchall()]
