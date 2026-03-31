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

    def get_efficiency(self, limit: int = 20) -> list[dict[str, Any]]:
        """Per-trip energy efficiency (kWh/100 km and Wh/mi)."""
        sql = """
            SELECT
                d.start_date,
                ROUND(d.distance::numeric, 1)                        AS distance_km,
                ROUND(d.energy_used::numeric, 2)                     AS energy_kwh,
                ROUND((d.energy_used / NULLIF(d.distance, 0) * 100)::numeric, 1)
                                                                     AS wh_per_km,
                ROUND((d.energy_used / NULLIF(d.distance * 1.60934, 0) * 100)::numeric, 1)
                                                                     AS kwh_per_100mi,
                d.start_battery_level,
                d.end_battery_level,
                a1.display_name                                      AS start_address,
                a2.display_name                                      AS end_address
            FROM drives d
            LEFT JOIN addresses a1 ON a1.id = d.start_address_id
            LEFT JOIN addresses a2 ON a2.id = d.end_address_id
            WHERE d.car_id = %s
              AND d.distance > 0
              AND d.energy_used > 0
            ORDER BY d.start_date DESC
            LIMIT %s
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, limit))
            rows = cur.fetchall()
        return [dict(r) for r in rows]

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

    def get_vampire_drain(self, days: int = 30) -> dict[str, Any]:
        """Estimate vampire drain from periods between drives."""
        sql = """
            WITH ordered_drives AS (
                SELECT
                    start_date,
                    end_date,
                    start_battery_level,
                    end_battery_level,
                    LEAD(start_battery_level) OVER (ORDER BY start_date)  AS next_start_level,
                    LEAD(start_date)           OVER (ORDER BY start_date)  AS next_start_date
                FROM drives
                WHERE car_id = %s
                  AND start_date >= NOW() - INTERVAL '%s days'
            )
            SELECT
                DATE(end_date)                                              AS date,
                ROUND(AVG(
                    GREATEST(0, end_battery_level - next_start_level)
                )::numeric, 2)                                              AS avg_drain_pct,
                ROUND(AVG(
                    EXTRACT(EPOCH FROM (next_start_date - end_date)) / 3600.0
                )::numeric, 1)                                              AS avg_parked_hours,
                ROUND(AVG(
                    GREATEST(0, end_battery_level - next_start_level) /
                    NULLIF(EXTRACT(EPOCH FROM (next_start_date - end_date)) / 3600.0, 0)
                )::numeric, 4)                                              AS pct_per_hour,
                COUNT(*)                                                    AS periods
            FROM ordered_drives
            WHERE next_start_level IS NOT NULL
              AND next_start_date IS NOT NULL
              AND EXTRACT(EPOCH FROM (next_start_date - end_date)) / 3600.0 BETWEEN 0.5 AND 72
            GROUP BY DATE(end_date)
            ORDER BY date DESC
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, days))
            rows = [dict(r) for r in cur.fetchall()]

        if not rows:
            return {"days_analyzed": days, "daily": [], "avg_pct_per_hour": None}

        avg_per_hour = None
        valid = [float(r["pct_per_hour"]) for r in rows if r["pct_per_hour"] is not None]
        if valid:
            import statistics
            avg_per_hour = round(statistics.mean(valid), 4)

        return {
            "days_analyzed": days,
            "avg_pct_per_hour": avg_per_hour,
            "daily": rows,
        }

    def get_top_locations(self, limit: int = 10) -> list[dict[str, Any]]:
        """Most visited start/end locations from drives."""
        sql = """
            SELECT
                a.display_name                                          AS location,
                a.latitude,
                a.longitude,
                COUNT(*)                                                AS visit_count,
                ROUND(MAX(d.end_battery_level)::numeric, 0)            AS max_arrival_pct,
                ROUND(MIN(d.end_battery_level)::numeric, 0)            AS min_arrival_pct
            FROM drives d
            JOIN addresses a ON a.id = d.end_address_id
            WHERE d.car_id = %s
              AND a.display_name IS NOT NULL
            GROUP BY a.display_name, a.latitude, a.longitude
            ORDER BY visit_count DESC
            LIMIT %s
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_monthly_report(self, month: str) -> dict[str, Any]:
        """Driving and charging summary for a given month (YYYY-MM)."""
        sql_drives = """
            SELECT
                COUNT(*)                                    AS trips,
                ROUND(SUM(distance)::numeric, 1)            AS total_km,
                ROUND(SUM(duration_min)::numeric, 0)        AS total_drive_min,
                ROUND(SUM(energy_used)::numeric, 2)         AS total_kwh_used,
                ROUND(AVG(distance)::numeric, 1)            AS avg_km_per_trip,
                ROUND(MAX(distance)::numeric, 1)            AS longest_trip_km,
                ROUND(AVG(
                    energy_used / NULLIF(distance, 0) * 100
                )::numeric, 1)                              AS avg_wh_per_km
            FROM drives
            WHERE car_id = %s
              AND DATE_TRUNC('month', start_date) = DATE_TRUNC('month', %s::date)
        """
        sql_charging = """
            SELECT
                COUNT(*)                                            AS sessions,
                ROUND(SUM(charge_energy_added)::numeric, 2)         AS total_kwh_charged,
                ROUND(SUM(cost)::numeric, 2)                        AS total_cost,
                ROUND(AVG(charge_energy_added)::numeric, 2)         AS avg_kwh_per_session,
                COUNT(*) FILTER (WHERE charger_power >= 50)         AS dc_fast_sessions,
                COUNT(*) FILTER (WHERE charger_power < 50)          AS ac_sessions
            FROM charging_processes
            WHERE car_id = %s
              AND DATE_TRUNC('month', start_date) = DATE_TRUNC('month', %s::date)
        """
        # month is YYYY-MM, convert to first day for SQL
        month_date = f"{month}-01"
        with self._cursor() as cur:
            cur.execute(sql_drives, (self._car_id, month_date))
            drive_row = dict(cur.fetchone() or {})
        with self._cursor() as cur:
            cur.execute(sql_charging, (self._car_id, month_date))
            charge_row = dict(cur.fetchone() or {})

        return {
            "month": month,
            "driving": drive_row,
            "charging": charge_row,
        }

    def get_daily_energy(self, days: int = 30) -> list[dict[str, Any]]:
        """Per-day kWh added from charging sessions over the last N days."""
        sql = """
            SELECT
                DATE(cp.start_date)                             AS day,
                ROUND(SUM(cp.charge_energy_added)::numeric, 1) AS kwh_added,
                COUNT(*)                                        AS sessions,
                ROUND(SUM(cp.cost)::numeric, 2)                 AS total_cost
            FROM charging_processes cp
            WHERE cp.car_id = %s
              AND cp.start_date >= NOW() - (%s || ' days')::interval
            GROUP BY DATE(cp.start_date)
            ORDER BY day ASC
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, str(days)))
            return [dict(r) for r in cur.fetchall()]

    def get_drive_days(self, days: int = 365) -> list[dict[str, Any]]:
        """Per-day driving activity over the last N days (date, km, drives)."""
        sql = """
            SELECT
                DATE(start_date)                        AS day,
                COUNT(*)                                AS drives,
                ROUND(SUM(distance)::numeric, 1)        AS km
            FROM drives
            WHERE car_id = %s
              AND start_date >= NOW() - (%s || ' days')::interval
              AND distance IS NOT NULL
            GROUP BY DATE(start_date)
            ORDER BY day ASC
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, str(days)))
            return [dict(r) for r in cur.fetchall()]

    def ping(self) -> bool:
        """Return True if DB connection is alive."""
        try:
            with self._cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False
