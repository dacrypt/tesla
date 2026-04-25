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
import math
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from tesla_cli.core.models.charge import (
    ChargeCurve,
    ChargeCurveStats,
    ChargeSample,
)

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
                cp.id                                       AS process_id,
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

    # ── Charge curves ────────────────────────────────────────────────────────

    def get_charging_process_end_date(self, process_id: int) -> datetime | None:
        """Return `end_date` of a charging process (None if still in progress or absent)."""
        sql = "SELECT end_date FROM charging_processes WHERE id = %s"
        with self._cursor() as cur:
            cur.execute(sql, (process_id,))
            row = cur.fetchone()
        if not row:
            return None
        return row.get("end_date")

    def get_charge_curve(self, process_id: int, max_samples: int = 500) -> ChargeCurve:
        """Return a (possibly downsampled) charge curve for a charging process.

        Uses modulo-based sampling over a ROW_NUMBER() window to avoid pulling
        the full series when the table has >max_samples rows.
        """
        count_sql = "SELECT COUNT(*) AS n FROM charges WHERE charging_process_id = %s"
        with self._cursor() as cur:
            cur.execute(count_sql, (process_id,))
            count_row = cur.fetchone()
        total = int((count_row or {}).get("n") or 0)
        if total == 0:
            return ChargeCurve(samples=[], downsampled=False, total_samples=0, stride=1)

        stride = max(1, math.ceil(total / max_samples))

        sample_sql = """
            SELECT date, battery_level, charger_power, charger_actual_current,
                   charger_voltage, charger_phases, ideal_battery_range_km
            FROM (
              SELECT date, battery_level, charger_power, charger_actual_current,
                     charger_voltage, charger_phases, ideal_battery_range_km,
                     ROW_NUMBER() OVER (ORDER BY date) AS rn
              FROM charges
              WHERE charging_process_id = %s
            ) s
            WHERE (rn - 1) %% %s = 0
            ORDER BY date
        """
        with self._cursor() as cur:
            cur.execute(sample_sql, (process_id, stride))
            rows = cur.fetchall()

        samples: list[ChargeSample] = []
        for r in rows:
            samples.append(
                ChargeSample(
                    ts=r["date"],
                    soc=int(r["battery_level"]) if r.get("battery_level") is not None else 0,
                    power_kw=float(r["charger_power"])
                    if r.get("charger_power") is not None
                    else 0.0,
                    current_a=(
                        float(r["charger_actual_current"])
                        if r.get("charger_actual_current") is not None
                        else None
                    ),
                    voltage_v=(
                        float(r["charger_voltage"])
                        if r.get("charger_voltage") is not None
                        else None
                    ),
                    phases=(
                        int(r["charger_phases"]) if r.get("charger_phases") is not None else None
                    ),
                    ideal_range_km=(
                        float(r["ideal_battery_range_km"])
                        if r.get("ideal_battery_range_km") is not None
                        else None
                    ),
                )
            )
        return ChargeCurve(
            samples=samples,
            downsampled=stride > 1,
            total_samples=total,
            stride=stride,
        )

    def get_curve_stats(self, process_id: int) -> ChargeCurveStats | None:
        """Compute curve statistics over the FULL `charges` rows for a process.

        Runs directly against the full series regardless of any downsampling
        applied by `get_charge_curve`, so stats are stable.
        """
        agg_sql = """
            SELECT
              MAX(charger_power) AS peak_kw,
              AVG(charger_power) FILTER (WHERE battery_level BETWEEN 20 AND 80) AS avg_kw_20_80,
              COUNT(*) AS n_samples,
              ARRAY_AGG(DISTINCT charger_phases) FILTER (WHERE charger_phases IS NOT NULL)
                AS phases_used,
              EXTRACT(EPOCH FROM (MAX(date) - MIN(date)))::int AS duration_s
            FROM charges
            WHERE charging_process_id = %s
        """
        with self._cursor() as cur:
            cur.execute(agg_sql, (process_id,))
            agg = cur.fetchone()

        if not agg or not agg.get("n_samples"):
            return None

        # Full ordered stream for trapezoidal integration and knee detection.
        # Postgres lacks a concise primitive for piecewise-linear integration
        # across a threshold, so we stream the full series and integrate in
        # Python. This is the only query in this method that is not aggregate.
        stream_sql = (
            "SELECT date, charger_power, battery_level FROM charges "
            "WHERE charging_process_id=%s ORDER BY date"
        )
        with self._cursor() as cur:
            cur.execute(stream_sql, (process_id,))
            rows = cur.fetchall()

        kwh_added = 0.0
        time_above_100kw_s = 0.0
        energy_above_100kw_kwh = 0.0
        peak_kw = 0.0
        peak_idx = 0
        for i, r in enumerate(rows):
            p = float(r.get("charger_power") or 0.0)
            if p > peak_kw:
                peak_kw = p
                peak_idx = i

        for a, b in zip(rows, rows[1:], strict=False):
            pa = float(a.get("charger_power") or 0.0)
            pb = float(b.get("charger_power") or 0.0)
            dt_s = (b["date"] - a["date"]).total_seconds()
            if dt_s <= 0:
                continue
            p_avg = (pa + pb) / 2.0
            kwh_added += p_avg * dt_s / 3600.0
            if min(pa, pb) >= 100.0:
                time_above_100kw_s += dt_s
                energy_above_100kw_kwh += p_avg * dt_s / 3600.0

        # Knee: first SoC (after peak) where power < 0.8 * peak_kw
        knee_soc: int | None = None
        threshold = 0.8 * peak_kw
        if peak_kw > 0:
            for r in rows[peak_idx:]:
                p = float(r.get("charger_power") or 0.0)
                if p < threshold:
                    lvl = r.get("battery_level")
                    if lvl is not None:
                        knee_soc = int(lvl)
                        break

        phases_raw = agg.get("phases_used") or []
        phases_used = sorted(int(p) for p in phases_raw if p is not None)

        return ChargeCurveStats(
            peak_kw=float(agg.get("peak_kw") or 0.0),
            avg_kw_20_80=(
                float(agg["avg_kw_20_80"]) if agg.get("avg_kw_20_80") is not None else None
            ),
            taper_knee_soc=knee_soc,
            time_above_100kw_s=int(round(time_above_100kw_s)),
            energy_above_100kw_kwh=round(energy_above_100kw_kwh, 6),
            phases_used=phases_used,
            duration_s=int(agg.get("duration_s") or 0),
            kwh_added=round(kwh_added, 6),
        )

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
                  AND start_date >= NOW() - (%s || ' days')::interval
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
              AND d.start_date >= NOW() - (%s || ' days')::interval
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
              AND cp.start_date >= NOW() - (%s || ' days')::interval
            UNION ALL
            SELECT
                'ota'             AS type,
                u.start_date,
                u.end_date,
                NULL              AS value,
                u.version         AS detail
            FROM updates u
            WHERE u.car_id = %s
              AND u.start_date >= NOW() - (%s || ' days')::interval
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
              AND start_date >= NOW() - (%s || ' days')::interval
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
              AND d.start_date >= NOW() - (%s || ' days')::interval
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
              AND cp.start_date >= NOW() - (%s || ' days')::interval
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
              AND cp.end_date >= NOW() - (%s || ' months')::interval
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

    def get_geo_locations(self, sample: int = 5) -> list[dict[str, Any]]:
        """Return sampled GPS positions across all recorded drives.

        Samples every Nth position to keep payload manageable.

        Args:
            sample: keep 1 row out of every N (default 5)

        Returns list of {lat, lon} dicts.
        """
        sql = """
            SELECT latitude AS lat, longitude AS lon
            FROM (
                SELECT latitude, longitude,
                       ROW_NUMBER() OVER (ORDER BY date ASC) AS rn
                FROM positions
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            ) sub
            WHERE rn %% %s = 0
            ORDER BY rn ASC
        """
        with self._cursor() as cur:
            cur.execute(sql, (sample,))
            return [dict(r) for r in cur.fetchall()]

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

    def get_calibration_dataset(
        self,
        days: int = 90,
        vin: str | None = None,
        battery_kwh: float = 75.0,
    ) -> list[dict[str, Any]]:
        """Return drive segments for consumption-model calibration.

        Each segment is a dict with:
            avg_speed_kmh, elevation_delta_m, distance_km, energy_kwh, outside_temp_c

        Energy is approximated as (start_ideal_range_km - end_ideal_range_km) *
        (battery_kwh / max_rated_range_km). TeslaMate does not expose per-drive
        energy directly; this is the conventional proxy. Document this in the
        notebook when interpreting R²/MAPE.
        """
        sql = """
            SELECT
                d.distance,
                d.duration_min,
                d.outside_temp_avg,
                d.start_ideal_range_km,
                d.end_ideal_range_km,
                (SELECT AVG(p.speed) FROM positions p
                   WHERE p.drive_id = d.id AND p.speed IS NOT NULL) AS avg_speed,
                (SELECT COALESCE(MAX(p.elevation), 0) - COALESCE(MIN(p.elevation), 0)
                   FROM positions p WHERE p.drive_id = d.id) AS elev_range,
                (SELECT AVG(p.outside_temp) FROM positions p
                   WHERE p.drive_id = d.id AND p.outside_temp IS NOT NULL) AS avg_outside_temp
            FROM drives d
            WHERE d.end_date > NOW() - (%s || ' days')::interval
              AND (%s IS NULL OR d.car_id IN (SELECT id FROM cars WHERE vin = %s))
              AND d.distance > 5
            ORDER BY d.start_date DESC
            LIMIT 500
        """
        with self._cursor() as cur:
            cur.execute(sql, (str(days), vin, vin))
            rows = [dict(r) for r in cur.fetchall()]

        out: list[dict[str, Any]] = []
        for r in rows:
            distance = r.get("distance")
            duration = r.get("duration_min") or 0
            if distance is None or distance <= 0:
                continue
            avg_speed = r.get("avg_speed")
            if avg_speed is None and duration > 0:
                avg_speed = float(distance) / (float(duration) / 60.0)
            if avg_speed is None:
                continue
            start_r = r.get("start_ideal_range_km") or 0
            end_r = r.get("end_ideal_range_km") or 0
            ideal_full_km = 500.0  # Model Y LR ideal-range proxy
            energy_kwh = max(0.0, float(start_r) - float(end_r)) * (battery_kwh / ideal_full_km)
            if energy_kwh <= 0:
                continue
            temp = r.get("outside_temp_avg")
            if temp is None:
                temp = r.get("avg_outside_temp")
            out.append(
                {
                    "avg_speed_kmh": float(avg_speed),
                    "elevation_delta_m": float(r.get("elev_range") or 0.0),
                    "distance_km": float(distance),
                    "energy_kwh": float(energy_kwh),
                    "outside_temp_c": float(temp) if temp is not None else None,
                }
            )
        return out

    def ping(self) -> bool:
        """Return True if DB connection is alive."""
        try:
            with self._cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            logger.warning("TeslaMate ping failed", exc_info=True)
            return False
