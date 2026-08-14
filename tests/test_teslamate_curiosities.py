"""Tests for `TeslaMateBacked.get_charge_curve_enrichment` (Phase 3 curiosities).

Mocks psycopg2 entirely via a fake cursor that pattern-matches on the SQL
text — no DB or psycopg2 installation is required.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

# ── Fake cursor plumbing ─────────────────────────────────────────────────────


class _FakeCursor:
    """Pattern-match on SQL to return whatever the test expects."""

    def __init__(self, handlers: dict) -> None:
        self._handlers = handlers
        self._result: list[dict] = []

    def execute(self, sql: str, params: tuple | None = None) -> None:
        s = " ".join(sql.split())
        params = params or ()
        for needle, handler in self._handlers.items():
            if needle in s:
                self._result = list(handler(params))
                return
        raise AssertionError(f"Unexpected SQL: {sql!r}")

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def close(self) -> None:
        pass


def _make_backend(handlers: dict):
    from tesla_cli.core.backends.teslaMate import TeslaMateBacked

    backend = TeslaMateBacked("postgresql://fake", car_id=1)

    @contextmanager
    def _fake_cursor():
        cur = _FakeCursor(handlers)
        try:
            yield cur
        finally:
            cur.close()

    backend._cursor = _fake_cursor  # type: ignore[method-assign]
    return backend


# ── 1. Rank: personal best ───────────────────────────────────────────────────


def test_rank_personal_best():
    # 5 sessions; ours (id=1) is the fastest at 1500s.
    rank_rows = [
        {"id": 1, "sec_20_80": 1500.0, "r": 1},
        {"id": 2, "sec_20_80": 1700.0, "r": 2},
        {"id": 3, "sec_20_80": 1800.0, "r": 3},
        {"id": 4, "sec_20_80": 1900.0, "r": 4},
        {"id": 5, "sec_20_80": 2100.0, "r": 5},
    ]
    handlers = {
        "WITH per_session AS": lambda p: rank_rows,
        # Preconditioning + shared stall: empty so they degrade.
        "ORDER BY date ASC": lambda p: [],
        # ABRP cost head row: minimal.
        "FROM charging_processes cp LEFT JOIN addresses": lambda p: [
            {
                "kwh_added": 50.0,
                "actual_cost": 10.0,
                "location_name": "home",
                "lat": None,
                "lon": None,
            }
        ],
    }
    backend = _make_backend(handlers)
    enrichment = backend.get_charge_curve_enrichment(process_id=1)
    assert enrichment.rank.fastest_20_to_80_position == 1
    assert enrichment.rank.fastest_20_to_80_total == 5
    assert enrichment.rank.is_personal_best is True


# ── 2. Rank: no qualifying data ──────────────────────────────────────────────


def test_rank_no_data():
    handlers = {
        "WITH per_session AS": lambda p: [],  # session never spans 20-80%
        "ORDER BY date ASC": lambda p: [],
        "FROM charging_processes cp LEFT JOIN addresses": lambda p: [
            {
                "kwh_added": 0.0,
                "actual_cost": None,
                "location_name": None,
                "lat": None,
                "lon": None,
            }
        ],
    }
    backend = _make_backend(handlers)
    enrichment = backend.get_charge_curve_enrichment(process_id=99)
    assert enrichment.rank.fastest_20_to_80_position is None
    assert enrichment.rank.fastest_20_to_80_total is None
    assert enrichment.rank.is_personal_best is False


# ── 3. Preconditioning detected (medium confidence) ──────────────────────────


def test_preconditioning_detected_with_confidence_medium():
    base = datetime(2026, 4, 1, 10, 0, 0)
    # 4 minutes of low-medium power (~10 kW) ramping up to 150 kW after.
    rows = []
    for i in range(0, 240, 30):  # every 30s for 4 min
        rows.append({"date": base + timedelta(seconds=i), "charger_power": 10.0})
    # First sustained-high sample shortly after 4 min mark.
    rows.append({"date": base + timedelta(seconds=240), "charger_power": 150.0})
    rows.append({"date": base + timedelta(seconds=270), "charger_power": 152.0})

    handlers = {
        "WITH per_session AS": lambda p: [],
        "ORDER BY date ASC": lambda p: rows,
        "FROM charging_processes cp LEFT JOIN addresses": lambda p: [
            {
                "kwh_added": 50.0,
                "actual_cost": None,
                "location_name": None,
                "lat": None,
                "lon": None,
            }
        ],
    }
    backend = _make_backend(handlers)
    enrichment = backend.get_charge_curve_enrichment(process_id=1)
    assert enrichment.preconditioning.detected is True
    assert enrichment.preconditioning.confidence == "medium"
    assert enrichment.preconditioning.duration_minutes == pytest.approx(4, abs=1)


# ── 4. Preconditioning NOT detected (full power immediately) ─────────────────


def test_preconditioning_not_detected():
    base = datetime(2026, 4, 1, 10, 0, 0)
    rows = [
        {"date": base + timedelta(seconds=i), "charger_power": 150.0} for i in range(0, 600, 30)
    ]
    handlers = {
        "WITH per_session AS": lambda p: [],
        "ORDER BY date ASC": lambda p: rows,
        "FROM charging_processes cp LEFT JOIN addresses": lambda p: [
            {
                "kwh_added": 50.0,
                "actual_cost": None,
                "location_name": None,
                "lat": None,
                "lon": None,
            }
        ],
    }
    backend = _make_backend(handlers)
    enrichment = backend.get_charge_curve_enrichment(process_id=1)
    assert enrichment.preconditioning.detected is False
    assert enrichment.preconditioning.duration_minutes is None
    assert enrichment.preconditioning.confidence is None


# ── 5. Shared stall detected ─────────────────────────────────────────────────


def test_shared_stall_detected():
    base = datetime(2026, 4, 1, 10, 0, 0)
    drop_ts = base + timedelta(seconds=60)
    # Cruise at 150 kW SoC=50, then drop to 60 kW for the remainder.
    rows = [
        {"date": base, "battery_level": 50, "charger_power": 150.0},
        {"date": drop_ts, "battery_level": 51, "charger_power": 60.0},
        {"date": base + timedelta(seconds=90), "battery_level": 51, "charger_power": 58.0},
        {"date": base + timedelta(seconds=120), "battery_level": 52, "charger_power": 60.0},
    ]
    handlers = {
        "WITH per_session AS": lambda p: [],
        "ORDER BY date ASC": lambda p: rows,
        "FROM charging_processes cp LEFT JOIN addresses": lambda p: [
            {
                "kwh_added": 50.0,
                "actual_cost": None,
                "location_name": None,
                "lat": None,
                "lon": None,
            }
        ],
    }
    backend = _make_backend(handlers)
    enrichment = backend.get_charge_curve_enrichment(process_id=1)
    assert enrichment.shared_stall.detected is True
    assert enrichment.shared_stall.power_drop_kw == pytest.approx(90.0, abs=0.1)
    assert enrichment.shared_stall.timestamp == drop_ts


# ── 6. ABRP cost fallback when provider unavailable ──────────────────────────


def test_abrp_cost_fallback_when_provider_unavailable():
    handlers = {
        "WITH per_session AS": lambda p: [],
        "ORDER BY date ASC": lambda p: [],
        "FROM charging_processes cp LEFT JOIN addresses": lambda p: [
            {
                "kwh_added": 50.0,
                "actual_cost": 12.5,
                "location_name": "home",
                "lat": None,
                "lon": None,
            }
        ],
    }
    backend = _make_backend(handlers)
    with patch(
        "tesla_cli.core.providers.impl.abrp.AbrpProvider.is_available",
        return_value=False,
    ):
        enrichment = backend.get_charge_curve_enrichment(process_id=1)
    assert enrichment.abrp_cost.available is False
    assert enrichment.abrp_cost.estimated_cost is None
    assert enrichment.abrp_cost.actual_cost == pytest.approx(12.5)
    assert enrichment.abrp_cost.delta_pct is None
