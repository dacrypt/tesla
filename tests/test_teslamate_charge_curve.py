"""Tests for the TeslaMate charge-curve backend methods.

Uses a fake cursor so no real DB (and no `psycopg2` installation) is needed.
Fixture data lives in `tests/fixtures/charge_curve/` and is shared with the
golden-stats test.
"""

from __future__ import annotations

import json
import math
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "charge_curve"


def _load_samples() -> list[dict]:
    """Load the synthetic 1200-sample charge session fixture."""
    with open(FIXTURE_DIR / "session_y1200.json") as f:
        raw = json.load(f)
    # Convert ISO strings to datetime objects (as psycopg2 would).
    for r in raw:
        r["date"] = datetime.fromisoformat(r["date"])
    return raw


def _load_expected() -> dict:
    with open(FIXTURE_DIR / "expected.json") as f:
        return json.load(f)


def _select_fixture_row_subset(rows: list[dict], columns: list[str]) -> list[dict]:
    """Return a new row list containing only the requested columns."""
    return [{c: r.get(c) for c in columns} for r in rows]


class _FakeCursor:
    """A minimal psycopg2 RealDictCursor double.

    Pattern-matches on the SQL text to decide which rows to return, so we can
    exercise the whole `get_charge_curve` / `get_curve_stats` flow with a
    single fixture.
    """

    def __init__(self, samples: list[dict]) -> None:
        self._samples = samples
        self._result: list[dict] = []

    def execute(self, sql: str, params: tuple | None = None) -> None:
        s = " ".join(sql.split())  # collapse whitespace for easier matching
        params = params or ()

        if "SELECT COUNT(*)" in s and "charges" in s:
            self._result = [{"n": len(self._samples)}]
            return

        if "ROW_NUMBER() OVER (ORDER BY date)" in s and "charges" in s:
            # Stride-based downsample. process_id is params[0], stride is params[1].
            stride = int(params[1])
            cols = [
                "date",
                "battery_level",
                "charger_power",
                "charger_actual_current",
                "charger_voltage",
                "charger_phases",
                "ideal_battery_range_km",
            ]
            picked = [r for i, r in enumerate(self._samples) if i % stride == 0]
            self._result = _select_fixture_row_subset(picked, cols)
            return

        if "SELECT end_date FROM charging_processes" in s:
            # Default: completed session (uses dataset end timestamp).
            self._result = [{"end_date": self._samples[-1]["date"]}]
            return

        if "MAX(charger_power)" in s and "AVG(charger_power)" in s:
            powers = [r["charger_power"] for r in self._samples]
            filt = [r["charger_power"] for r in self._samples if 20 <= r["battery_level"] <= 80]
            duration = int((self._samples[-1]["date"] - self._samples[0]["date"]).total_seconds())
            phases = sorted(
                {r["charger_phases"] for r in self._samples if r["charger_phases"] is not None}
            )
            self._result = [
                {
                    "peak_kw": max(powers),
                    "avg_kw_20_80": (sum(filt) / len(filt)) if filt else None,
                    "n_samples": len(self._samples),
                    "phases_used": phases,
                    "duration_s": duration,
                }
            ]
            return

        if "SELECT date, charger_power, battery_level" in s:
            cols = ["date", "charger_power", "battery_level"]
            self._result = _select_fixture_row_subset(self._samples, cols)
            return

        if "SELECT 1" in s:
            self._result = [{"?column?": 1}]
            return

        raise AssertionError(f"Unexpected SQL in fake cursor: {sql}")

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def close(self) -> None:
        pass


def _make_backend_with_rows(samples: list[dict]):
    """Build a TeslaMateBacked with its `_cursor` context patched to a fake."""
    from tesla_cli.core.backends.teslaMate import TeslaMateBacked

    backend = TeslaMateBacked("postgresql://fake", car_id=1)

    @contextmanager
    def _fake_cursor():
        cur = _FakeCursor(samples)
        try:
            yield cur
        finally:
            cur.close()

    backend._cursor = _fake_cursor  # type: ignore[method-assign]
    return backend


@pytest.fixture
def tm_backend():
    """Return a TeslaMateBacked wired to the 1200-sample fixture."""
    return _make_backend_with_rows(_load_samples())


# ── Charge curve downsampling ────────────────────────────────────────────────


def test_get_charge_curve_downsample(tm_backend):
    """1200 rows with max_samples=500 -> stride=3, downsampled=True."""
    curve = tm_backend.get_charge_curve(process_id=1, max_samples=500)
    assert curve.total_samples == 1200
    assert curve.downsampled is True
    assert curve.stride == 3
    assert len(curve.samples) <= 500
    # With stride=3, ceil(1200/3)=400 rows.
    assert len(curve.samples) == 400


def test_get_charge_curve_no_downsample_when_small(tm_backend):
    """1200 rows with max_samples=2000 -> stride=1, downsampled=False."""
    curve = tm_backend.get_charge_curve(process_id=1, max_samples=2000)
    assert curve.total_samples == 1200
    assert curve.downsampled is False
    assert curve.stride == 1
    assert len(curve.samples) == 1200


def test_get_charge_curve_empty():
    """Zero rows -> empty curve, not downsampled."""
    backend = _make_backend_with_rows([])
    curve = backend.get_charge_curve(process_id=999, max_samples=500)
    assert curve.total_samples == 0
    assert curve.samples == []
    assert curve.downsampled is False


# ── Curve stats vs. golden fixture ───────────────────────────────────────────


def test_get_curve_stats_matches_golden(tm_backend):
    expected = _load_expected()
    stats = tm_backend.get_curve_stats(process_id=1)
    assert stats is not None

    assert stats.peak_kw == pytest.approx(expected["peak_kw"], abs=1e-6)
    assert stats.avg_kw_20_80 == pytest.approx(expected["avg_kw_20_80"], abs=1e-6)
    assert stats.taper_knee_soc == expected["taper_knee_soc"]
    assert stats.time_above_100kw_s == expected["time_above_100kw_s"]
    assert stats.energy_above_100kw_kwh == pytest.approx(
        expected["energy_above_100kw_kwh"], abs=1e-6
    )
    assert stats.phases_used == expected["phases_used"]
    assert stats.duration_s == expected["duration_s"]
    assert stats.kwh_added == pytest.approx(expected["kwh_added"], abs=1e-6)


def test_stats_not_influenced_by_downsampling(tm_backend):
    """Stats must run over full series regardless of curve sampling."""
    _curve_small = tm_backend.get_charge_curve(process_id=1, max_samples=100)
    _curve_large = tm_backend.get_charge_curve(process_id=1, max_samples=500)
    stats = tm_backend.get_curve_stats(process_id=1)
    assert stats is not None

    expected = _load_expected()
    assert stats.peak_kw == pytest.approx(expected["peak_kw"], abs=1e-6)
    assert stats.kwh_added == pytest.approx(expected["kwh_added"], abs=1e-6)
    assert stats.time_above_100kw_s == expected["time_above_100kw_s"]
    assert stats.taper_knee_soc == expected["taper_knee_soc"]


def test_stride_ceiling_never_exceeds_max_samples(tm_backend):
    """The stride math must never produce more than `max_samples` rows."""
    for m in (50, 100, 250, 499, 500, 501, 999, 1000, 1199, 1201):
        curve = tm_backend.get_charge_curve(process_id=1, max_samples=m)
        assert len(curve.samples) <= m, f"max_samples={m} produced {len(curve.samples)}"
        # Sanity: stride must be the documented formula.
        assert curve.stride == max(1, math.ceil(1200 / m))
