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

    def _get_conn(self) -> object:
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
                COUNT(*)                                                    AS total_drives,
                ROUND(COALESCE(SUM(distance), 0)::numeric, 0)              AS total_km,
                ROUND(COALESCE(SUM(
                    GREATEST(0, start_ideal_range_km - end_ideal_range_km) * 0.16
                ), 0)::numeric, 1)                                          AS total_kwh,
                ROUND(COALESCE(AVG(distance), 0)::numeric, 1)              AS avg_km_per_trip,
                ROUND(COALESCE(MAX(distance), 0)::numeric, 1)              AS longest_trip_km,
                MIN(start_date)                                             AS first_drive,
                MAX(end_date)                                               AS last_drive
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
                a1.display_name                             AS start_address,
                a2.display_name                             AS end_address,
                ROUND(d.distance::numeric, 1)               AS distance_km,
                d.duration_min,
                ROUND(d.start_ideal_range_km::numeric, 0)   AS start_range_km,
                ROUND(d.end_ideal_range_km::numeric, 0)     AS end_range_km,
                ROUND(GREATEST(0, d.start_ideal_range_km - d.end_ideal_range_km)::numeric * 0.16, 2)
                                                            AS energy_kwh
            FROM drives d
            LEFT JOIN addresses a1 ON a1.id = d.start_address_id
            LEFT JOIN addresses a2 ON a2.id = d.end_address_id
            WHERE d.car_id = %s
            ORDER BY d.start_date DESC
            LIMIT %s
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_efficiency(self, limit: int = 20) -> list[dict[str, Any]]:
        """Per-trip energy efficiency (Wh/km and kWh/100mi)."""
        sql = """
            SELECT
                d.start_date,
                ROUND(d.distance::numeric, 1)                       AS distance_km,
                d.duration_min,
                ROUND(GREATEST(0, d.start_ideal_range_km - d.end_ideal_range_km)::numeric * 0.16, 2)
                                                                    AS energy_kwh,
                ROUND((GREATEST(0, d.start_ideal_range_km - d.end_ideal_range_km) * 0.16
                    / NULLIF(d.distance, 0) * 1000)::numeric, 1)   AS wh_per_km,
                ROUND((GREATEST(0, d.start_ideal_range_km - d.end_ideal_range_km) * 0.16
                    / NULLIF(d.distance * 1.60934, 0) * 100)::numeric, 1)
                                                                    AS kwh_per_100mi,
                a1.display_name                                     AS start_address,
                a2.display_name                                     AS end_address
            FROM drives d
            LEFT JOIN addresses a1 ON a1.id = d.start_address_id
            LEFT JOIN addresses a2 ON a2.id = d.end_address_id
            WHERE d.car_id = %s
              AND d.distance > 0
              AND d.start_ideal_range_km > d.end_ideal_range_km
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
                   wheel_type, spoiler_type, efficiency
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
                    end_ideal_range_km,
                    LEAD(start_ideal_range_km) OVER (ORDER BY start_date)  AS next_start_range,
                    LEAD(start_date)           OVER (ORDER BY start_date)  AS next_start_date
                FROM drives
                WHERE car_id = %s
                  AND start_date >= NOW() - INTERVAL '%s days'
            )
            SELECT
                DATE(end_date)                                              AS date,
                ROUND(AVG(
                    GREATEST(0, end_ideal_range_km - COALESCE(next_start_range, end_ideal_range_km))
                )::numeric, 2)                                              AS avg_drain_km,
                ROUND(AVG(
                    EXTRACT(EPOCH FROM (next_start_date - end_date)) / 3600.0
                )::numeric, 1)                                              AS avg_parked_hours,
                ROUND(AVG(
                    GREATEST(0, end_ideal_range_km - COALESCE(next_start_range, end_ideal_range_km)) /
                    NULLIF(EXTRACT(EPOCH FROM (next_start_date - end_date)) / 3600.0, 0)
                )::numeric, 4)                                              AS km_per_hour,
                COUNT(*)                                                    AS periods
            FROM ordered_drives
            WHERE next_start_range IS NOT NULL
              AND next_start_date IS NOT NULL
              AND EXTRACT(EPOCH FROM (next_start_date - end_date)) / 3600.0 BETWEEN 0.5 AND 72
            GROUP BY DATE(end_date)
            ORDER BY date DESC
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, days))
            rows = [dict(r) for r in cur.fetchall()]

        if not rows:
            return {"days_analyzed": days, "daily": [], "avg_km_per_hour": None}

        avg = None
        valid = [float(r["km_per_hour"]) for r in rows if r["km_per_hour"] is not None]
        if valid:
            import statistics

            avg = round(statistics.mean(valid), 4)

        return {
            "days_analyzed": days,
            "avg_km_per_hour": avg,
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
                ROUND(AVG(d.end_ideal_range_km)::numeric, 0)           AS avg_arrival_range_km
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
                ROUND(SUM(GREATEST(0, start_ideal_range_km - end_ideal_range_km) * 0.16)::numeric, 2)
                                                            AS total_kwh_used,
                ROUND(AVG(distance)::numeric, 1)            AS avg_km_per_trip,
                ROUND(MAX(distance)::numeric, 1)            AS longest_trip_km,
                ROUND(AVG(
                    GREATEST(0, start_ideal_range_km - end_ideal_range_km) * 0.16
                    / NULLIF(distance, 0) * 1000
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
                ROUND(AVG(charge_energy_added)::numeric, 2)         AS avg_kwh_per_session
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

    def get_drive_days_year(self, year: int) -> list[dict[str, Any]]:
        """Active driving days for a full calendar year."""
        sql = """
            SELECT
                DATE(start_date AT TIME ZONE 'UTC') AS day,
                COUNT(*)                             AS drives,
                COALESCE(SUM(distance), 0)           AS km
            FROM drives
            WHERE car_id  = %s
              AND start_date >= %s
              AND start_date <  %s
            GROUP BY day
            ORDER BY day
        """
        import datetime as _dt

        start = _dt.date(year, 1, 1)
        end = _dt.date(year + 1, 1, 1)
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, start, end))
            return [dict(r) for r in cur.fetchall()]

    def get_timeline(self, days: int = 30) -> list[dict[str, Any]]:
        """Unified event timeline: trips, charges, and OTA updates merged chronologically."""
        sql = """
            SELECT
                'trip'            AS type,
                d.start_date,
                d.end_date,
                ROUND(d.distance::numeric, 1)      AS value,
                COALESCE(a.display_name, 'Unknown') AS detail
            FROM drives d
            LEFT JOIN addresses a ON d.start_address_id = a.id
            WHERE d.car_id = %s
              AND d.start_date >= NOW() - INTERVAL '%s days'
            UNION ALL
            SELECT
                'charge'          AS type,
                cp.start_date,
                cp.end_date,
                ROUND(cp.charge_energy_added::numeric, 2) AS value,
                COALESCE(a.display_name, 'Unknown')       AS detail
            FROM charging_processes cp
            LEFT JOIN addresses a ON cp.address_id = a.id
            WHERE cp.car_id = %s
              AND cp.start_date >= NOW() - INTERVAL '%s days'
            UNION ALL
            SELECT
                'ota'             AS type,
                u.start_date,
                u.end_date,
                NULL              AS value,
                u.version         AS detail
            FROM updates u
            WHERE u.car_id = %s
              AND u.start_date >= NOW() - INTERVAL '%s days'
            ORDER BY start_date DESC
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, days, self._car_id, days, self._car_id, days))
            return [dict(r) for r in cur.fetchall()]

    def get_trip_stats(self, days: int = 30) -> dict[str, Any]:
        """Aggregate trip statistics over the last N days."""
        summary_sql = """
            SELECT
                COUNT(*)                                    AS total_trips,
                ROUND(SUM(distance)::numeric, 1)            AS total_km,
                ROUND(AVG(distance)::numeric, 1)            AS avg_km,
                ROUND(MAX(distance)::numeric, 1)            AS longest_km,
                ROUND(MIN(distance)::numeric, 1)            AS shortest_km,
                ROUND(AVG(EXTRACT(EPOCH FROM (end_date - start_date)) / 60)::numeric, 0) AS avg_duration_min
            FROM drives
            WHERE car_id = %s
              AND start_date >= NOW() - INTERVAL '%s days'
              AND distance IS NOT NULL
        """
        routes_sql = """
            SELECT
                COALESCE(a_s.display_name, 'Unknown') AS from_addr,
                COALESCE(a_e.display_name, 'Unknown') AS to_addr,
                COUNT(*)                               AS count
            FROM drives d
            LEFT JOIN addresses a_s ON d.start_address_id = a_s.id
            LEFT JOIN addresses a_e ON d.end_address_id   = a_e.id
            WHERE d.car_id = %s
              AND d.start_date >= NOW() - INTERVAL '%s days'
            GROUP BY from_addr, to_addr
            ORDER BY count DESC
            LIMIT 5
        """
        with self._cursor() as cur:
            cur.execute(summary_sql, (self._car_id, days))
            row = cur.fetchone()
            summary = dict(row) if row else {}
        with self._cursor() as cur:
            cur.execute(routes_sql, (self._car_id, days))
            routes = [dict(r) for r in cur.fetchall()]
        return {"summary": summary, "top_routes": routes, "days": days}

    def get_charging_locations(self, days: int = 90, limit: int = 10) -> list[dict[str, Any]]:
        """Top charging locations by session count over the last N days."""
        sql = """
            SELECT
                COALESCE(a.display_name, 'Unknown')          AS location,
                COUNT(*)                                      AS sessions,
                ROUND(SUM(cp.charge_energy_added)::numeric, 2) AS total_kwh,
                ROUND(AVG(cp.charge_energy_added)::numeric, 2) AS avg_kwh_per_session,
                MAX(cp.start_date)                            AS last_visit
            FROM charging_processes cp
            LEFT JOIN addresses a ON cp.address_id = a.id
            WHERE cp.car_id = %s
              AND cp.start_date >= NOW() - INTERVAL '%s days'
              AND cp.charge_energy_added > 0
            GROUP BY a.display_name
            ORDER BY sessions DESC
            LIMIT %s
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, days, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_battery_degradation(self, months: int = 12) -> dict[str, Any]:
        """Compute battery degradation from high-SoC charging sessions.

        Groups charges by month where end_battery_level >= 95%.
        Returns monthly max rated range to show degradation trend.
        """
        sql = """
            SELECT
                TO_CHAR(cp.end_date, 'YYYY-MM') AS month,
                MAX(cp.end_rated_range_km)       AS max_range_km,
                MAX(cp.end_battery_level)        AS max_soc,
                COUNT(*)                         AS sessions
            FROM charging_processes cp
            WHERE cp.car_id = %s
              AND cp.end_battery_level >= 95
              AND cp.end_date >= NOW() - INTERVAL '%s months'
              AND cp.end_rated_range_km IS NOT NULL
            GROUP BY TO_CHAR(cp.end_date, 'YYYY-MM')
            ORDER BY month
        """
        with self._cursor() as cur:
            cur.execute(sql, (self._car_id, months))
            rows = [dict(r) for r in cur.fetchall()]

        if not rows:
            return {"months_analyzed": months, "data_points": 0, "monthly": []}

        first_range = float(rows[0]["max_range_km"])
        last_range = float(rows[-1]["max_range_km"])
        degradation_pct = round((1 - last_range / first_range) * 100, 1) if first_range > 0 else 0

        return {
            "months_analyzed": months,
            "data_points": len(rows),
            "first_month": rows[0]["month"],
            "last_month": rows[-1]["month"],
            "first_range_km": round(first_range, 1),
            "last_range_km": round(last_range, 1),
            "degradation_pct": degradation_pct,
            "monthly": [
                {
                    "month": r["month"],
                    "max_range_km": round(float(r["max_range_km"]), 1),
                    "max_soc": r["max_soc"],
                    "sessions": r["sessions"],
                }
                for r in rows
            ],
        }

    def get_drive_path(self, drive_id: int) -> list[dict[str, Any]]:
        """Get GPS positions for a specific drive from TeslaMate.

        Returns list of {latitude, longitude, elevation, speed, timestamp} dicts.
        """
        sql = """
            SELECT
                latitude,
                longitude,
                elevation,
                speed,
                date AS timestamp
            FROM positions
            WHERE drive_id = %s
            ORDER BY date ASC
        """
        with self._cursor() as cur:
            cur.execute(sql, (drive_id,))
            return [dict(r) for r in cur.fetchall()]

    def ping(self) -> bool:
        """Return True if DB connection is alive."""
        try:
            with self._cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False
