"""TeslaMate database backend.

Connects to a running TeslaMate PostgreSQL database to read:
- Drive/trip history
- Charging sessions
- Software OTA updates
- Lifetime stats

Connection string stored in ~/.tesla-cli/config.toml under [teslaMate].
Requires psycopg2: uv pip install psycopg2-binary
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


class TeslaMateBacked:
    """Read-only TeslaMate PostgreSQL backend."""

    def __init__(self, database_url: str, car_id: int = 1) -> None:
        self._url = database_url
        self._car_id = car_id
        self._conn = None

    # ── Connection ──────────────────────────────────────────────────────────

    def _get_conn(self):
        """Return a live psycopg2 connection, creating it lazily."""
        if self._conn is None or self._conn.closed:
            try:
                import psycopg2
                import psycopg2.extras
            except ImportError as exc:
                raise ImportError(
                    "psycopg2 is required for TeslaMate integration.\n"
                    "Install it with:  uv pip install psycopg2-binary"
                ) from exc
            self._conn = psycopg2.connect(self._url)
        return self._conn

    @contextmanager
    def _cursor(self):
        import psycopg2.extras
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
        finally:
            cur.close()

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Lifetime driving stats for the configured car."""
        sql = """
            SELECT
                COUNT(*)                                    AS total_drives,
                ROUND(SUM(distance)::numeric, 0)            AS total_km,
                ROUND(SUM(energy_used)::numeric, 1)         AS total_kwh,
                ROUND(AVG(distance)::numeric, 1)            AS avg_km_per_trip,
                ROUND(MAX(distance)::numeric, 1)            AS longest_trip_km,
                MIN(start_date)                             AS first_drive,
                MAX(end_date)                               AS last_drive
            FROM drives
            WHERE car_id = %s
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id,))
            row = cur.fetchone()
        return dict(row) if row else {}

    def get_charging_stats(self) -> dict[str, Any]:
        """Lifetime charging stats for the configured car."""
        sql = """
            SELECT
                COUNT(*)                                        AS total_sessions,
                ROUND(SUM(charge_energy_added)::numeric, 1)     AS total_kwh_added,
                ROUND(SUM(cost)::numeric, 2)                    AS total_cost,
                ROUND(AVG(charge_energy_added)::numeric, 1)     AS avg_kwh_per_session,
                MAX(start_date)                                 AS last_session
            FROM charging_processes
            WHERE car_id = %s
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id,))
            row = cur.fetchone()
        return dict(row) if row else {}

    def get_trips(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recent trips sorted by date descending."""
        sql = """
            SELECT
                d.id,
                d.start_date,
                d.end_date,
                d.start_address,
                d.end_address,
                ROUND(d.distance::numeric, 1)               AS distance_km,
                d.duration_min,
                d.start_battery_level,
                d.end_battery_level,
                ROUND(d.start_ideal_range_km::numeric, 0)   AS start_range_km,
                ROUND(d.end_ideal_range_km::numeric, 0)     AS end_range_km,
                ROUND(d.energy_used::numeric, 2)            AS energy_kwh
            FROM drives d
            WHERE d.car_id = %s
            ORDER BY d.start_date DESC
            LIMIT %s
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_charging_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recent charging sessions sorted by date descending."""
        sql = """
            SELECT
                cp.id,
                cp.start_date,
                cp.end_date,
                ROUND(cp.charge_energy_added::numeric, 2)   AS energy_added_kwh,
                ROUND(cp.cost::numeric, 2)                  AS cost,
                cp.start_battery_level,
                cp.end_battery_level,
                a.display_name                              AS location
            FROM charging_processes cp
            LEFT JOIN addresses a ON cp.address_id = a.id
            WHERE cp.car_id = %s
            ORDER BY cp.start_date DESC
            LIMIT %s
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_updates(self) -> list[dict[str, Any]]:
        """Software OTA update history for the car."""
        sql = """
            SELECT id, start_date, end_date, version
            FROM updates
            WHERE car_id = %s
            ORDER BY start_date DESC
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id,))
            return [dict(r) for r in cur.fetchall()]

    def get_cars(self) -> list[dict[str, Any]]:
        """List all cars in the TeslaMate database."""
        sql = """
            SELECT id, vin, name, model, trim_badging, exterior_color,
                   wheel_type, spoiler_type, efficiency_data
            FROM cars
            ORDER BY id
        """
        with self._cursor() as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def ping(self) -> bool:
        """Return True if DB connection is alive."""
        try:
            with self._cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False
